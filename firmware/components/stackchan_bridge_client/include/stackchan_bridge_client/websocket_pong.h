#pragma once

#include <functional>

class WebSocket;

namespace stackchan::bridge_client {

// Observe control replies without changing the pinned WebSocket class ABI.
// At most eight live sockets can register; destruction must clear the registration.
bool setWebSocketPongCallback(WebSocket* socket, std::function<void()> callback);
void clearWebSocketPongCallback(WebSocket* socket);
void notifyWebSocketPong(WebSocket* socket);

}  // namespace stackchan::bridge_client
