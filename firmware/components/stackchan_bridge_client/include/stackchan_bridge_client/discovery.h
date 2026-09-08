#pragma once

#include <cstdint>
#include <string>

namespace stackchan::bridge_client {

struct MdnsBridgeService {
    std::string ipv4Address;
    std::uint16_t port = 0;
    std::string protocolVersion;
    std::string authRequired;
    // Host byte order, supplied by the receiving interface when available.
    std::uint32_t interfaceAddress = 0;
    std::uint32_t interfaceNetmask = 0;
};

std::string buildMdnsBridgeWebSocketUrl(const MdnsBridgeService& service);

}  // namespace stackchan::bridge_client
