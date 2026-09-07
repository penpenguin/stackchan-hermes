#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <string>
#include <stackchan_bridge_client/websocket_pong.h>

class WebSocket {
public:
    inline static std::function<bool(const char*)> connectHandler;
    inline static std::function<void()> destroyHandler;

    ~WebSocket()
    {
        stackchan::bridge_client::clearWebSocketPongCallback(this);
        if (destroyHandler) {
            destroyHandler();
        }
        if (connected_ && disconnectedCallback_) {
            disconnectedCallback_();
        }
    }

    void SetHeader(const char*, const char*) {}
    void SetReceiveBufferSize(std::size_t) {}
    bool IsConnected() const { return connected_; }

    bool Connect(const char* url)
    {
        connected_ = connectHandler && connectHandler(url);
        if (connected_ && connectedCallback_) {
            connectedCallback_();
        }
        return connected_;
    }

    bool Send(const std::string&) { return connected_; }
    bool Send(const void*, std::size_t, bool, bool) { return connected_; }
    void Ping() {}
    void Close() { connected_ = false; }

    void OnConnected(std::function<void()> callback)
    {
        connectedCallback_ = std::move(callback);
    }

    void OnDisconnected(std::function<void()> callback)
    {
        disconnectedCallback_ = std::move(callback);
    }
    void OnData(std::function<void(const char*, std::size_t, bool)>) {}
    void OnError(std::function<void(int)>) {}

private:
    bool connected_ = false;
    std::function<void()> connectedCallback_;
    std::function<void()> disconnectedCallback_;
};
