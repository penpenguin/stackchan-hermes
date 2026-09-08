#include <stackchan_bridge_client/discovery.h>

#include <string_view>
#include <cstdint>

namespace stackchan::bridge_client {
namespace {

bool isLocalUnicastIpv4Address(const MdnsBridgeService& service)
{
    const std::string_view address = service.ipv4Address;
    if (address.empty() || address.size() > 15) {
        return false;
    }
    std::size_t offset = 0;
    std::uint32_t ip = 0;
    for (int octet = 0; octet < 4; ++octet) {
        const std::size_t separator = address.find('.', offset);
        const std::size_t end = separator == std::string_view::npos
            ? address.size()
            : separator;
        if (end == offset || end - offset > 3
            || (end - offset > 1 && address[offset] == '0')) {
            return false;
        }
        int value = 0;
        for (std::size_t index = offset; index < end; ++index) {
            const char character = address[index];
            if (character < '0' || character > '9') {
                return false;
            }
            value = value * 10 + character - '0';
        }
        if (value > 255 || (octet < 3 && separator == std::string_view::npos)
            || (octet == 3 && separator != std::string_view::npos)) {
            return false;
        }
        offset = end + 1;
        ip = (ip << 8) | static_cast<std::uint32_t>(value);
    }
    const auto mask = service.interfaceNetmask;
    const auto hostMask = ~mask;
    if (mask != 0 && hostMask > 1 && (ip & mask) == (service.interfaceAddress & mask)
        && ((ip & hostMask) == 0 || (ip & hostMask) == hostMask)) {
        return false;
    }
    // Exclude private prefix boundaries. Link-local reserves the first/last /24.
    return (ip > 0x0a000000 && ip < 0x0affffff)
        || (ip > 0xac100000 && ip < 0xac1fffff)
        || (ip > 0xc0a80000 && ip < 0xc0a8ffff)
        || (ip >= 0xa9fe0100 && ip <= 0xa9fefeff);
}

}  // namespace

std::string buildMdnsBridgeWebSocketUrl(const MdnsBridgeService& service)
{
    if (!isLocalUnicastIpv4Address(service) || service.port == 0
        || service.protocolVersion != "1" || service.authRequired != "true") {
        return {};
    }
    return "ws://" + service.ipv4Address + ":" + std::to_string(service.port)
        + "/v1/device/ws";
}

}  // namespace stackchan::bridge_client
