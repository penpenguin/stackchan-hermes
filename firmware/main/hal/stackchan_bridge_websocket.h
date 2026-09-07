#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <thread>

#include <stackchan_bridge_client/session.h>

class NetworkInterface;
class WebSocket;

namespace stackchan::hermes {

class OfficialWebSocketTransport final : public bridge_client::WebSocketTransport {
public:
    explicit OfficialWebSocketTransport(NetworkInterface& network);
    ~OfficialWebSocketTransport() override;

    void setHeader(const std::string& name, const std::string& value) override;
    void setReceiveBufferSize(std::size_t size) override;
    void onConnected(std::function<void()> callback) override;
    void onDisconnected(std::function<void()> callback) override;
    void onData(std::function<void(const char*, std::size_t, bool)> callback) override;
    void onError(std::function<void(int)> callback) override;
    void onPong(std::function<void()> callback) override;
    bool connect(const std::string& url) override;
    bool sendText(const std::string& text) override;
    bool sendBinary(const std::uint8_t* data, std::size_t size) override;
    void ping() override;
    void close() override;
    void poll() override;

private:
    struct ConnectionCallbacks {
        std::function<void()> connected;
        std::function<void()> disconnected;
        std::function<void(const char*, std::size_t, bool)> data;
        std::function<void(int)> error;
        std::function<void()> pong;
    };

    struct PendingCallback {
        std::uint64_t generation = 0;
        bool requiresOpenConnection = false;
        std::function<void()> callback;
    };

    std::shared_ptr<WebSocket> socketSnapshot();
    void enqueueCallback(
        std::uint64_t generation,
        bool requiresOpenConnection,
        std::function<void()> callback
    );
    void runConnection(
        std::string url,
        std::uint64_t generation,
        ConnectionCallbacks callbacks
    ) noexcept;

    NetworkInterface& network_;
    std::shared_ptr<WebSocket> socket_;
    std::mutex socketMutex_;
    std::map<std::string, std::string> headers_;
    std::size_t receiveBufferSize_ = 2048;
    std::function<void()> connectedCallback_;
    std::function<void()> disconnectedCallback_;
    std::function<void(const char*, std::size_t, bool)> dataCallback_;
    std::function<void(int)> errorCallback_;
    std::function<void()> pongCallback_;
    std::thread connectionWorker_;
    std::atomic<bool> connectionRunning_{false};
    std::atomic<bool> closeRequested_{false};
    std::atomic<bool> shuttingDown_{false};
    std::atomic<std::uint64_t> connectionGeneration_{0};
    std::deque<PendingCallback> pendingCallbacks_;
    std::mutex pendingCallbacksMutex_;
    std::atomic<bool> pendingCallbackOverflow_{false};
};

}  // namespace stackchan::hermes
