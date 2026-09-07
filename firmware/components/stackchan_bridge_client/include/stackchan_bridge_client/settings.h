#pragma once

#include <string>

namespace stackchan::bridge_client {

enum class BridgeEndpointSource {
    None,
    Nvs,
    Mdns,
    NvsFallback,
    Kconfig,
};

struct BridgeEndpointSources {
    std::string nvsUrl;
    std::string mdnsUrl;
    std::string nvsFallbackUrl;
    std::string kconfigUrl;
    bool discoveryEnabled = true;
};

struct BridgeEndpointResult {
    bool ok = false;
    BridgeEndpointSource source = BridgeEndpointSource::None;
    std::string url;
};

BridgeEndpointResult resolveBridgeEndpoint(const BridgeEndpointSources& sources);

}  // namespace stackchan::bridge_client
