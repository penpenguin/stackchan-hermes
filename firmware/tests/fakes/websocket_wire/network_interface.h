#pragma once

#include <memory>
#include <tcp.h>

class NetworkInterface {
public:
    virtual ~NetworkInterface() = default;
    virtual std::unique_ptr<Tcp> CreateTcp(int connectId) = 0;
    virtual std::unique_ptr<Tcp> CreateSsl(int connectId) = 0;
};
