#include <cstdlib>
#include <iostream>
#include <string>

#include <stackchan_bridge_client/discovery.h>
#include <stackchan_bridge_client/settings.h>

namespace {

using stackchan::bridge_client::MdnsBridgeService;
using stackchan::bridge_client::buildMdnsBridgeWebSocketUrl;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

MdnsBridgeService validService()
{
    return MdnsBridgeService{"192.168.2.20", 8765, "1", "true"};
}

void testCompatibleAuthenticatedServiceBuildsBoundedUrl()
{
    expect(
        buildMdnsBridgeWebSocketUrl(validService())
            == "ws://192.168.2.20:8765/v1/device/ws",
        "compatible mDNS service did not build the Bridge URL"
    );
}

void testUnsupportedProtocolIsRejected()
{
    auto service = validService();
    service.protocolVersion = "2";
    expect(buildMdnsBridgeWebSocketUrl(service).empty(), "unsupported mDNS protocol was used");
}

void testServiceWithoutRequiredAuthenticationIsRejected()
{
    auto service = validService();
    service.authRequired = "false";
    expect(buildMdnsBridgeWebSocketUrl(service).empty(), "unauthenticated service was used");
}

void testInvalidAddressAndPortAreRejected()
{
    for (const std::string address : {
             std::string{},
             std::string{"256.0.2.20"},
             std::string{"192.0.2"},
             std::string{"192.0.2.20/path"},
         }) {
        auto service = validService();
        service.ipv4Address = address;
        expect(buildMdnsBridgeWebSocketUrl(service).empty(), "invalid mDNS IPv4 was used");
    }
    auto service = validService();
    service.port = 0;
    expect(buildMdnsBridgeWebSocketUrl(service).empty(), "zero mDNS port was used");
}

}  // namespace

int main()
{
    using namespace stackchan::bridge_client;
    BridgeEndpointSources sources;
    sources.mdnsUrl = buildMdnsBridgeWebSocketUrl({"8.8.8.8", 8765, "1", "true"});
    expect(!resolveBridgeEndpoint(sources).ok, "rejected mDNS advertisement selected an endpoint");
    sources.nvsFallbackUrl = "wss://configured.example.test:8443/v1/device/ws";
    expect(resolveBridgeEndpoint(sources).source == BridgeEndpointSource::NvsFallback,
           "rejected mDNS advertisement bypassed the explicit fallback");
    sources.nvsUrl = sources.nvsFallbackUrl;
    expect(resolveBridgeEndpoint(sources).source == BridgeEndpointSource::Nvs,
           "explicit external Bridge URL was rejected");
    sources.nvsUrl.clear();
    sources.kconfigUrl = sources.nvsFallbackUrl;
    sources.nvsFallbackUrl.clear();
    expect(resolveBridgeEndpoint(sources).source == BridgeEndpointSource::Kconfig,
           "explicit build-time external Bridge URL was rejected");
    auto directed = validService();
    directed.interfaceAddress = 0xc0a80201;  // 192.168.2.1
    directed.interfaceNetmask = 0xffffff00;
    for (auto* address : {"192.168.2.0", "192.168.2.255"}) {
        directed.ipv4Address = address;
        expect(buildMdnsBridgeWebSocketUrl(directed).empty(), "interface network/broadcast was used");
    }
    directed.interfaceNetmask = 0xfffffe00;  // .2.255 and .3.0 are unicast on this /23.
    expect(!buildMdnsBridgeWebSocketUrl(directed).empty(), "valid /23 unicast was rejected");
    directed.ipv4Address = "192.168.3.0";
    expect(!buildMdnsBridgeWebSocketUrl(directed).empty(), "valid /23 unicast was rejected");
    for (const auto* address : {"8.8.8.8", "192.0.2.20", "172.15.0.1", "172.32.0.1",
                                "127.0.0.1", "0.0.0.0", "224.0.0.1", "255.255.255.255",
                                "10.0.0.0", "10.255.255.255", "172.16.0.0", "172.31.255.255",
                                "192.168.0.0", "192.168.255.255", "169.254.0.1", "169.254.255.1",
                                "010.1.2.3"}) {
        auto service = validService();
        service.ipv4Address = address;
        expect(buildMdnsBridgeWebSocketUrl(service).empty(), "non-local/unicast mDNS IPv4 was used");
    }
    for (const auto* address : {"10.0.0.1", "10.255.255.254", "172.16.0.1", "172.31.255.254",
                                "192.168.0.1", "192.168.255.254", "169.254.1.0", "169.254.254.255"}) {
        auto service = validService();
        service.ipv4Address = address;
        expect(!buildMdnsBridgeWebSocketUrl(service).empty(), "local unicast mDNS IPv4 was rejected");
    }
    testCompatibleAuthenticatedServiceBuildsBoundedUrl();
    testUnsupportedProtocolIsRejected();
    testServiceWithoutRequiredAuthenticationIsRejected();
    testInvalidAddressAndPortAreRejected();
    return 0;
}
