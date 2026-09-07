#pragma once

#include <cstdint>
#include <string>

namespace stackchan::bridge_client {

struct MdnsBridgeService {
    std::string ipv4Address;
    std::uint16_t port = 0;
    std::string protocolVersion;
    std::string authRequired;
};

std::string buildMdnsBridgeWebSocketUrl(const MdnsBridgeService& service);

}  // namespace stackchan::bridge_client
