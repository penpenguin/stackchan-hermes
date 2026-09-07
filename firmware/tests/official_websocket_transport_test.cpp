#include <atomic>
#include <chrono>
#include <cstdlib>
#include <future>
#include <iostream>
#include <memory>
#include <string>
#include <thread>

#include <network_interface.h>
#include <web_socket.h>

#include "stackchan_bridge_websocket.h"

namespace {

using namespace std::chrono_literals;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

class FakeNetworkInterface final : public NetworkInterface {
public:
    std::unique_ptr<WebSocket> CreateWebSocket(int) override
    {
        auto created = std::make_unique<WebSocket>();
        socket = created.get();
        return created;
    }
    WebSocket* socket = nullptr;
};

bool pollUntilReady(
    stackchan::hermes::OfficialWebSocketTransport& transport,
    std::future<void>& completion
)
{
    const auto deadline = std::chrono::steady_clock::now() + 1s;
    while (std::chrono::steady_clock::now() < deadline) {
        transport.poll();
        if (completion.wait_for(0ms) == std::future_status::ready) {
            return true;
        }
        std::this_thread::sleep_for(1ms);
    }
    return false;
}

void testConnectReturnsBeforeTheSocketHandshakeCompletes()
{
    std::promise<void> handshakeEntered;
    std::promise<void> releaseHandshake;
    auto release = releaseHandshake.get_future().share();
    WebSocket::connectHandler = [&](const char*) {
        handshakeEntered.set_value();
        release.wait();
        return true;
    };

    FakeNetworkInterface network;
    stackchan::hermes::OfficialWebSocketTransport transport(network);
    auto connectCall = std::async(std::launch::async, [&]() {
        return transport.connect("ws://192.0.2.1:8765/v1/devices/device-1/ws");
    });

    expect(
        handshakeEntered.get_future().wait_for(1s) == std::future_status::ready,
        "socket handshake did not start"
    );
    const bool returnedBeforeHandshake =
        connectCall.wait_for(50ms) == std::future_status::ready;
    releaseHandshake.set_value();
    expect(connectCall.get(), "transport did not accept the connection attempt");
    expect(returnedBeforeHandshake, "connect blocked on the socket handshake");
}

void testReconnectReturnsBeforeThePreviousSocketIsDestroyed()
{
    WebSocket::destroyHandler = {};
    WebSocket::connectHandler = [](const char*) {
        return true;
    };
    FakeNetworkInterface network;
    stackchan::hermes::OfficialWebSocketTransport transport(network);
    std::promise<void> firstConnection;
    std::promise<void> secondConnection;
    auto firstConnectionFuture = firstConnection.get_future();
    auto secondConnectionFuture = secondConnection.get_future();
    std::atomic<int> connections{0};
    transport.onConnected([&]() {
        const int connection = connections.fetch_add(1);
        if (connection == 0) {
            firstConnection.set_value();
        } else if (connection == 1) {
            secondConnection.set_value();
        }
    });
    std::atomic<int> disconnects{0};
    transport.onDisconnected([&]() {
        disconnects.fetch_add(1);
    });
    expect(
        transport.connect("ws://192.0.2.1:8765/v1/device/ws"),
        "first connection attempt was rejected"
    );
    expect(
        pollUntilReady(transport, firstConnectionFuture),
        "first connection did not finish"
    );

    std::promise<void> destructionEntered;
    std::promise<void> releaseDestruction;
    auto release = releaseDestruction.get_future().share();
    std::atomic<int> destructions{0};
    WebSocket::destroyHandler = [&]() {
        if (destructions.fetch_add(1) == 0) {
            destructionEntered.set_value();
            release.wait();
        }
    };
    auto reconnectCall = std::async(std::launch::async, [&]() {
        return transport.connect("ws://192.0.2.2:8765/v1/device/ws");
    });

    expect(
        destructionEntered.get_future().wait_for(1s) == std::future_status::ready,
        "previous socket destruction did not start"
    );
    const bool returnedBeforeDestruction =
        reconnectCall.wait_for(50ms) == std::future_status::ready;
    releaseDestruction.set_value();
    expect(reconnectCall.get(), "reconnection attempt was rejected");
    expect(returnedBeforeDestruction, "reconnect blocked destroying the previous socket");
    expect(
        pollUntilReady(transport, secondConnectionFuture),
        "replacement connection did not finish"
    );
    expect(disconnects.load() == 0, "replaced socket emitted a stale disconnect callback");
    WebSocket::destroyHandler = {};
}

void testConnectionCallbackIsSerializedOntoThePollingThread()
{
    std::promise<void> handshakeReturned;
    auto handshakeReturnedFuture = handshakeReturned.get_future();
    std::thread::id connectionThread;
    WebSocket::connectHandler = [&](const char*) {
        connectionThread = std::this_thread::get_id();
        handshakeReturned.set_value();
        return true;
    };

    FakeNetworkInterface network;
    stackchan::hermes::OfficialWebSocketTransport transport(network);
    std::atomic<int> callbackCalls{0};
    std::thread::id callbackThread;
    std::promise<void> callbackCompleted;
    auto callbackCompletedFuture = callbackCompleted.get_future();
    transport.onConnected([&]() {
        callbackThread = std::this_thread::get_id();
        callbackCalls.fetch_add(1);
        callbackCompleted.set_value();
    });

    expect(
        transport.connect("ws://192.0.2.1:8765/v1/device/ws"),
        "connection attempt was rejected"
    );
    expect(
        handshakeReturnedFuture.wait_for(1s) == std::future_status::ready,
        "socket handshake did not return"
    );
    std::this_thread::sleep_for(20ms);
    expect(callbackCalls.load() == 0, "connection callback ran on the socket worker");

    const std::thread::id pollingThread = std::this_thread::get_id();
    expect(
        pollUntilReady(transport, callbackCompletedFuture),
        "polling did not dispatch the connection callback"
    );
    expect(callbackCalls.load() == 1, "connection callback was dispatched more than once");
    expect(callbackThread == pollingThread, "connection callback used a different thread");
    expect(callbackThread != connectionThread, "connection callback remained on socket worker");
}

void testPongCallbacksUseThePollingThreadAndIgnoreClosedConnections()
{
    WebSocket::destroyHandler = {};
    WebSocket::connectHandler = [](const char*) { return true; };
    FakeNetworkInterface network;
    stackchan::hermes::OfficialWebSocketTransport transport(network);
    std::promise<void> connected;
    auto connectedFuture = connected.get_future();
    transport.onConnected([&]() { connected.set_value(); });
    int pongCount = 0;
    const auto pollingThread = std::this_thread::get_id();
    transport.onPong([&]() {
        expect(std::this_thread::get_id() == pollingThread, "pong bypassed polling thread");
        ++pongCount;
    });
    expect(transport.connect("ws://example.test/ws"), "connection rejected");
    expect(pollUntilReady(transport, connectedFuture), "connection did not complete");
    auto received = std::async(std::launch::async, [&]() {
        stackchan::bridge_client::notifyWebSocketPong(network.socket);
    });
    received.get();
    expect(pongCount == 0, "pong callback ran on receive thread");
    transport.poll();
    expect(pongCount == 1, "poll did not dispatch pong");
    stackchan::bridge_client::notifyWebSocketPong(network.socket);
    transport.close();
    transport.poll();
    expect(pongCount == 1, "closed connection dispatched a queued pong");
}

}  // namespace

int main()
{
    testConnectReturnsBeforeTheSocketHandshakeCompletes();
    testReconnectReturnsBeforeThePreviousSocketIsDestroyed();
    testConnectionCallbackIsSerializedOntoThePollingThread();
    testPongCallbacksUseThePollingThreadAndIgnoreClosedConnections();
    return 0;
}
