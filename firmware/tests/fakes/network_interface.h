#pragma once

#include <memory>

#include <web_socket.h>

class NetworkInterface {
public:
    virtual ~NetworkInterface() = default;
    virtual std::unique_ptr<WebSocket> CreateWebSocket(int connectId = -1) = 0;
};
