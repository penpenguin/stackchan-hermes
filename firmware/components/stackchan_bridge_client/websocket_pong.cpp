#include <stackchan_bridge_client/websocket_pong.h>

#include <array>
#include <mutex>
#include <utility>

namespace stackchan::bridge_client {
namespace {
struct PongObserver {
    WebSocket* socket = nullptr;
    std::function<void()> callback;
};
std::array<PongObserver, 8> observers;
std::mutex observersMutex;
}  // namespace

bool setWebSocketPongCallback(WebSocket* socket, std::function<void()> callback)
{
    if (socket == nullptr || !callback) {
        return false;
    }
    std::lock_guard<std::mutex> lock(observersMutex);
    for (auto& observer : observers) {
        if (observer.socket == socket) {
            observer.callback = std::move(callback);
            return true;
        }
    }
    for (auto& observer : observers) {
        if (observer.socket == nullptr) {
            observer = {socket, std::move(callback)};
            return true;
        }
    }
    return false;
}

void clearWebSocketPongCallback(WebSocket* socket)
{
    std::lock_guard<std::mutex> lock(observersMutex);
    for (auto& observer : observers) {
        if (observer.socket == socket) {
            observer = {};
        }
    }
}

void notifyWebSocketPong(WebSocket* socket)
{
    std::function<void()> callback;
    {
        std::lock_guard<std::mutex> lock(observersMutex);
        for (const auto& observer : observers) {
            if (observer.socket == socket) {
                callback = observer.callback;
                break;
            }
        }
    }
    if (callback) {
        callback();
    }
}

}  // namespace stackchan::bridge_client
