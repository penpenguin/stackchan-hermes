#include <cstdlib>
#include <array>
#include <cstdint>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include <network_interface.h>
#include <web_socket.h>
#include <stackchan_bridge_client/websocket_handshake.h>
#include <stackchan_bridge_client/websocket_pong.h>

namespace {
std::vector<std::size_t> randomRequests;
std::uint8_t nextRandomByte = 0;
bool acceptHandshake = true;

void expect(bool condition, const char* message)
{
    if (!condition) {
        std::cerr << message << '\n';
        std::exit(1);
    }
}

class RecordingTcp final : public Tcp {
public:
    bool Connect(const std::string&, int) override { return true; }
    void Disconnect() override {}
    int GetLastError() override { return 0; }
    int Send(const std::string& data) override
    {
        frames.push_back(data);
        if (respondToHandshake && data.rfind("GET ", 0) == 0) {
            stream_callback_("HTTP/1.1 101 Switching Protocols\r\n\r\n");
        }
        return static_cast<int>(data.size());
    }
    void receivePing() { stream_callback_(std::string("\x89\x01p", 3)); }
    void receivePong(bool empty) {
        stream_callback_(empty ? std::string("\x8a\x00", 2) : std::string("\x8a\x01p", 3));
    }
    void receiveDisconnect() { disconnect_callback_(); }
    bool respondToHandshake = true;
    std::vector<std::string> frames;
};

class RecordingNetwork final : public NetworkInterface {
public:
    std::unique_ptr<Tcp> CreateTcp(int) override
    {
        auto socket = std::make_unique<RecordingTcp>();
        socket->respondToHandshake = respondToHandshake;
        tcp = socket.get();
        return socket;
    }
    std::unique_ptr<Tcp> CreateSsl(int id) override { return CreateTcp(id); }
    RecordingTcp* tcp = nullptr;
    bool respondToHandshake = true;
};

void expectMaskedFrame(
    const std::string& frame, std::uint8_t opcode,
    std::uint8_t firstMaskByte, const std::string& payload
)
{
    expect(frame.size() == payload.size() + 6, "unexpected masked frame size");
    expect(static_cast<std::uint8_t>(frame[0]) == (0x80U | opcode), "wrong opcode");
    expect(static_cast<std::uint8_t>(frame[1]) == (0x80U | payload.size()), "missing mask bit");
    for (std::size_t index = 0; index < 4; ++index) {
        expect(static_cast<std::uint8_t>(frame[index + 2]) == firstMaskByte + index,
               "frame did not use a fresh system-random mask");
    }
    for (std::size_t index = 0; index < payload.size(); ++index) {
        expect((frame[index + 6] ^ frame[index % 4 + 2]) == payload[index], "wrong masked payload");
    }
}

void testPongObserversAreBoundedAndReleasedOnDestruction()
{
    using namespace stackchan::bridge_client;
    RecordingNetwork network;
    std::array<std::unique_ptr<WebSocket>, 8> sockets;
    int calls = 0;
    for (auto& socket : sockets) {
        socket = std::make_unique<WebSocket>(&network, 1);
        expect(setWebSocketPongCallback(socket.get(), [&]() { ++calls; }),
               "observer capacity was smaller than eight sockets");
    }
    WebSocket overflow(&network, 1);
    expect(!setWebSocketPongCallback(&overflow, []() {}), "observer storage was not bounded");
    expect(setWebSocketPongCallback(sockets.front().get(), [&]() { calls += 10; }),
           "replacing an existing observer consumed a new slot");
    notifyWebSocketPong(sockets.front().get());
    notifyWebSocketPong(sockets.back().get());
    expect(calls == 11, "pong notification crossed socket ownership");
    sockets.front().reset();
    expect(setWebSocketPongCallback(&overflow, []() {}), "destruction did not release observer slot");
}
}  // namespace

extern "C" void esp_fill_random(void* buffer, std::size_t size)
{
    randomRequests.push_back(size);
    auto* bytes = static_cast<std::uint8_t*>(buffer);
    for (std::size_t index = 0; index < size; ++index) {
        bytes[index] = nextRandomByte++;
    }
}

namespace stackchan::bridge_client {
// Validation has its own tests; this fixture controls its result for wire/lifecycle checks.
bool validateWebSocketHandshakeResponse(std::string_view, std::string_view)
{
    return acceptHandshake;
}
}

int main()
{
    testPongObserversAreBoundedAndReleasedOnDestruction();
    RecordingNetwork network;
    WebSocket socket(&network, 1);
    int pongCount = 0;
    int dataCount = 0;
    socket.OnData([&](const char*, std::size_t, bool) { ++dataCount; });
    expect(stackchan::bridge_client::setWebSocketPongCallback(&socket, [&]() { ++pongCount; }),
           "pong callback registration failed");
    expect(socket.Connect("ws://example.test/v1/device/ws"), "handshake failed");
    expect(randomRequests == std::vector<std::size_t>{16}, "handshake bypassed system randomness");
    expect(network.tcp->frames[0].find("Sec-WebSocket-Key: AAECAwQFBgcICQoLDA0ODw==\r\n")
               != std::string::npos, "handshake key did not encode random bytes");
    expect(socket.Send(std::string("hello")), "text send failed");
    expect(socket.Send("audio", 5, true), "binary send failed");
    socket.Ping();
    network.tcp->receivePong(false);
    expect(pongCount == 0, "unmatched pong was reported as a heartbeat reply");
    network.tcp->receivePong(true);
    expect(pongCount == 1, "empty heartbeat pong was not reported");
    expect(dataCount == 0, "pong was exposed as application data");
    network.tcp->receivePing();
    socket.Close();
    expect(randomRequests == std::vector<std::size_t>({16, 4, 4, 4, 4, 4}),
           "each data/control frame must request a fresh mask");
    expectMaskedFrame(network.tcp->frames[1], 0x01, 16, "hello");
    expectMaskedFrame(network.tcp->frames[2], 0x02, 20, "audio");
    expectMaskedFrame(network.tcp->frames[3], 0x09, 24, "");
    expectMaskedFrame(network.tcp->frames[4], 0x0A, 28, "p");
    expectMaskedFrame(network.tcp->frames[5], 0x08, 32, "");

    for (bool firstAccepted : {true, false}) {
        RecordingNetwork reconnectNetwork;
        WebSocket reconnectSocket(&reconnectNetwork, 2);
        int connectedCallbacks = 0;
        reconnectSocket.OnConnected([&connectedCallbacks]() { ++connectedCallbacks; });
        acceptHandshake = firstAccepted;
        expect(reconnectSocket.Connect("ws://example.test/ws") == firstAccepted,
               "initial handshake did not respect validation");
        reconnectNetwork.tcp->receiveDisconnect();

        reconnectNetwork.respondToHandshake = false;
        expect(!reconnectSocket.Connect("ws://example.test/ws"),
               "reconnect succeeded without a new handshake response");
        expect(websocket_test::lastWaitBits == 0,
               "reconnect inherited success/failure event bits");
        expect(!reconnectSocket.IsConnected(), "pending handshake exposed a connected socket");
        expect(connectedCallbacks == static_cast<int>(firstAccepted),
               "pending handshake invoked the connected callback");

        reconnectNetwork.respondToHandshake = true;
        acceptHandshake = false;
        expect(!reconnectSocket.Connect("ws://example.test/ws"),
               "reconnect ignored a rejected handshake response");
        expect(!reconnectSocket.IsConnected(), "rejected handshake exposed a connected socket");
        acceptHandshake = true;
        expect(reconnectSocket.Connect("ws://example.test/ws"),
               "a new valid handshake did not recover after rejection");
        expect(connectedCallbacks == static_cast<int>(firstAccepted) + 1,
               "only freshly validated handshakes may invoke connected callbacks");
    }
}
