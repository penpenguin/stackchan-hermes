#include <stackchan_bridge_client/settings.h>

#include <cctype>

namespace stackchan::bridge_client {
namespace {

bool isValidPort(const std::string& port)
{
    if (port.empty()) {
        return false;
    }
    unsigned value = 0;
    for (const unsigned char character : port) {
        if (!std::isdigit(character)) {
            return false;
        }
        value = value * 10 + static_cast<unsigned>(character - '0');
        if (value > 65535) {
            return false;
        }
    }
    return value >= 1;
}

bool isValidHost(const std::string& host)
{
    if (host.empty()) {
        return false;
    }
    for (const unsigned char character : host) {
        if (character <= 0x20 || character >= 0x7f || character == '/' || character == '\\'
            || character == '@' || character == '?' || character == '#' || character == '['
            || character == ']') {
            return false;
        }
    }
    return true;
}

bool isValidAuthority(const std::string& authority)
{
    if (authority.empty()) {
        return false;
    }
    if (authority.front() == '[') {
        return false;
    }

    const std::size_t colon = authority.find(':');
    if (colon == std::string::npos) {
        return isValidHost(authority);
    }
    return authority.find(':', colon + 1) == std::string::npos
        && isValidHost(authority.substr(0, colon)) && isValidPort(authority.substr(colon + 1));
}

bool isBridgeWebSocketUrl(const std::string& url)
{
    constexpr char kPath[] = "/v1/device/ws";
    constexpr std::size_t kMaxUrlBytes = 512;
    if (url.size() > kMaxUrlBytes) {
        return false;
    }
    const std::size_t schemeLength = url.rfind("ws://", 0) == 0 ? 5
        : url.rfind("wss://", 0) == 0                         ? 6
                                                               : 0;
    const std::size_t pathLength = sizeof(kPath) - 1;
    if (schemeLength == 0 || url.size() < pathLength) {
        return false;
    }
    const std::size_t pathOffset = url.size() - pathLength;
    return pathOffset > schemeLength && url.compare(pathOffset, pathLength, kPath) == 0
        && isValidAuthority(url.substr(schemeLength, pathOffset - schemeLength));
}

}  // namespace

BridgeEndpointResult resolveBridgeEndpoint(const BridgeEndpointSources& sources)
{
    const std::string* url = nullptr;
    BridgeEndpointSource source = BridgeEndpointSource::None;
    if (!sources.nvsUrl.empty()) {
        url    = &sources.nvsUrl;
        source = BridgeEndpointSource::Nvs;
    } else if (sources.discoveryEnabled && !sources.mdnsUrl.empty()) {
        url    = &sources.mdnsUrl;
        source = BridgeEndpointSource::Mdns;
    } else if (!sources.nvsFallbackUrl.empty()) {
        url    = &sources.nvsFallbackUrl;
        source = BridgeEndpointSource::NvsFallback;
    } else if (!sources.kconfigUrl.empty()) {
        url    = &sources.kconfigUrl;
        source = BridgeEndpointSource::Kconfig;
    }

    if (url == nullptr || !isBridgeWebSocketUrl(*url)) {
        return BridgeEndpointResult{};
    }
    return BridgeEndpointResult{true, source, *url};
}

}  // namespace stackchan::bridge_client
