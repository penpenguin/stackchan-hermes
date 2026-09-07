#include <stackchan_bridge_client/discovery.h>

#include <string_view>

namespace stackchan::bridge_client {
namespace {

bool isIpv4Address(std::string_view address)
{
    if (address.empty() || address.size() > 15) {
        return false;
    }
    std::size_t offset = 0;
    for (int octet = 0; octet < 4; ++octet) {
        const std::size_t separator = address.find('.', offset);
        const std::size_t end = separator == std::string_view::npos
            ? address.size()
            : separator;
        if (end == offset || end - offset > 3) {
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
    }
    return true;
}

}  // namespace

std::string buildMdnsBridgeWebSocketUrl(const MdnsBridgeService& service)
{
    if (!isIpv4Address(service.ipv4Address) || service.port == 0
        || service.protocolVersion != "1" || service.authRequired != "true") {
        return {};
    }
    return "ws://" + service.ipv4Address + ":" + std::to_string(service.port)
        + "/v1/device/ws";
}

}  // namespace stackchan::bridge_client
