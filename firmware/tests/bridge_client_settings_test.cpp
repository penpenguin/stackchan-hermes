#include <cstdlib>
#include <iostream>

#include <stackchan_bridge_client/settings.h>

namespace {

using stackchan::bridge_client::BridgeEndpointSource;
using stackchan::bridge_client::BridgeEndpointSources;
using stackchan::bridge_client::resolveBridgeEndpoint;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testNvsBridgeUrlHasHighestPrecedence()
{
    BridgeEndpointSources sources;
    sources.nvsUrl     = "ws://192.0.2.10:8765/v1/device/ws";
    sources.mdnsUrl    = "ws://stackchan-mdns.local:8765/v1/device/ws";
    sources.kconfigUrl = "ws://192.0.2.30:8765/v1/device/ws";

    const auto result = resolveBridgeEndpoint(sources);
    expect(result.ok, "NVS endpoint did not resolve");
    expect(result.source == BridgeEndpointSource::Nvs, "NVS was not preferred");
    expect(result.url == sources.nvsUrl, "wrong endpoint was selected");
}

void testMdnsBridgeUrlIsUsedWhenNvsIsEmpty()
{
    BridgeEndpointSources sources;
    sources.mdnsUrl    = "ws://stackchan-mdns.local:8765/v1/device/ws";
    sources.kconfigUrl = "ws://192.0.2.30:8765/v1/device/ws";

    const auto result = resolveBridgeEndpoint(sources);
    expect(result.ok, "mDNS endpoint did not resolve");
    expect(result.source == BridgeEndpointSource::Mdns, "mDNS was not selected");
    expect(result.url == sources.mdnsUrl, "wrong endpoint was selected");
}

void testKconfigBridgeUrlIsUsedAsFallback()
{
    BridgeEndpointSources sources;
    sources.kconfigUrl = "ws://192.0.2.30:8765/v1/device/ws";

    const auto result = resolveBridgeEndpoint(sources);
    expect(result.ok, "Kconfig endpoint did not resolve");
    expect(result.source == BridgeEndpointSource::Kconfig, "Kconfig was not selected");
    expect(result.url == sources.kconfigUrl, "wrong endpoint was selected");
}

void testProvisionedFallbackUrlPrecedesKconfig()
{
    BridgeEndpointSources sources;
    sources.nvsFallbackUrl = "wss://fallback.local/v1/device/ws";
    sources.kconfigUrl = "ws://192.0.2.30:8765/v1/device/ws";

    const auto result = resolveBridgeEndpoint(sources);
    expect(result.ok, "provisioned fallback endpoint did not resolve");
    expect(
        result.source == BridgeEndpointSource::NvsFallback,
        "provisioned fallback source changed"
    );
    expect(result.url == sources.nvsFallbackUrl, "wrong fallback endpoint was selected");
}

void testDisabledDiscoverySkipsMdnsCandidate()
{
    BridgeEndpointSources sources;
    sources.discoveryEnabled = false;
    sources.mdnsUrl = "ws://stackchan-mdns.local:8765/v1/device/ws";
    sources.kconfigUrl = "ws://192.0.2.30:8765/v1/device/ws";

    const auto result = resolveBridgeEndpoint(sources);
    expect(result.ok, "disabled discovery lost fixed fallback");
    expect(result.source == BridgeEndpointSource::Kconfig, "disabled discovery used mDNS");
}

void testMissingBridgeUrlIsAnExplicitError()
{
    const auto result = resolveBridgeEndpoint(BridgeEndpointSources{});
    expect(!result.ok, "missing endpoint unexpectedly resolved");
    expect(result.source == BridgeEndpointSource::None, "missing endpoint has a source");
    expect(result.url.empty(), "missing endpoint has a URL");
}

void testHttpBridgeUrlIsRejected()
{
    BridgeEndpointSources sources;
    sources.nvsUrl = "http://192.0.2.10:8765/v1/device/ws";

    const auto result = resolveBridgeEndpoint(sources);
    expect(!result.ok, "HTTP endpoint unexpectedly resolved");
    expect(result.source == BridgeEndpointSource::None, "invalid endpoint has a source");
    expect(result.url.empty(), "invalid endpoint has a URL");
}

void testWrongWebSocketPathIsRejected()
{
    BridgeEndpointSources sources;
    sources.nvsUrl = "ws://192.0.2.10:8765/not-the-device-endpoint";

    const auto result = resolveBridgeEndpoint(sources);
    expect(!result.ok, "wrong WebSocket path unexpectedly resolved");
}

void testBridgeUrlWithoutHostIsRejected()
{
    BridgeEndpointSources sources;
    sources.nvsUrl = "ws:///v1/device/ws";

    const auto result = resolveBridgeEndpoint(sources);
    expect(!result.ok, "hostless WebSocket URL unexpectedly resolved");
}

void testBridgeUrlWithUserInfoIsRejected()
{
    BridgeEndpointSources sources;
    sources.nvsUrl = "ws://device:secret@192.0.2.10:8765/v1/device/ws";  // pragma: allowlist secret

    const auto result = resolveBridgeEndpoint(sources);
    expect(!result.ok, "WebSocket URL with user info unexpectedly resolved");
}

void testBridgeUrlWithQueryIsRejected()
{
    BridgeEndpointSources sources;
    sources.nvsUrl = "ws://192.0.2.10:8765?redirect=/v1/device/ws";

    const auto result = resolveBridgeEndpoint(sources);
    expect(!result.ok, "WebSocket URL with query unexpectedly resolved");
}

void testBridgeUrlWithFragmentIsRejected()
{
    BridgeEndpointSources sources;
    sources.nvsUrl = "ws://192.0.2.10:8765#fragment/v1/device/ws";

    const auto result = resolveBridgeEndpoint(sources);
    expect(!result.ok, "WebSocket URL with fragment unexpectedly resolved");
}

void testOversizedBridgeUrlIsRejected()
{
    BridgeEndpointSources sources;
    sources.nvsUrl = "ws://" + std::string(500, 'a') + "/v1/device/ws";

    const auto result = resolveBridgeEndpoint(sources);
    expect(!result.ok, "oversized WebSocket URL unexpectedly resolved");
}

void testInvalidBridgePortsAreRejected()
{
    for (const auto& url : {
             "ws://192.0.2.10:/v1/device/ws",
             "ws://192.0.2.10:notaport/v1/device/ws",
             "ws://192.0.2.10:0/v1/device/ws",
             "ws://192.0.2.10:65536/v1/device/ws",
             "ws://192.0.2.10:999999999999999999999/v1/device/ws",
         }) {
        BridgeEndpointSources sources;
        sources.nvsUrl = url;
        const auto result = resolveBridgeEndpoint(sources);
        expect(!result.ok, "invalid WebSocket port unexpectedly resolved");
    }
}

void testBoundaryBridgePortsAreAccepted()
{
    for (const auto& url : {
             "ws://bridge.local:1/v1/device/ws",
             "wss://bridge.local:65535/v1/device/ws",
         }) {
        BridgeEndpointSources sources;
        sources.nvsUrl = url;
        const auto result = resolveBridgeEndpoint(sources);
        expect(result.ok, "valid boundary WebSocket port was rejected");
    }
}

void testBracketedIpv6IsRejectedUntilTheTransportSupportsIt()
{
    for (const auto& url : {
             "ws://[2001:db8::1]/v1/device/ws",
             "ws://[2001:db8::1]:8765/v1/device/ws",
         }) {
        BridgeEndpointSources sources;
        sources.nvsUrl = url;
        const auto result = resolveBridgeEndpoint(sources);
        expect(!result.ok, "unsupported IPv6 WebSocket URL unexpectedly resolved");
    }
}

void testInvalidHigherPrecedenceUrlDoesNotSilentlyFallBack()
{
    BridgeEndpointSources sources;
    sources.nvsUrl  = "http://192.0.2.10:8765/v1/device/ws";
    sources.mdnsUrl = "ws://stackchan-mdns.local:8765/v1/device/ws";

    const auto result = resolveBridgeEndpoint(sources);
    expect(!result.ok, "invalid NVS URL silently fell back to mDNS");
}

}  // namespace

int main()
{
    testNvsBridgeUrlHasHighestPrecedence();
    testMdnsBridgeUrlIsUsedWhenNvsIsEmpty();
    testKconfigBridgeUrlIsUsedAsFallback();
    testProvisionedFallbackUrlPrecedesKconfig();
    testDisabledDiscoverySkipsMdnsCandidate();
    testMissingBridgeUrlIsAnExplicitError();
    testHttpBridgeUrlIsRejected();
    testWrongWebSocketPathIsRejected();
    testBridgeUrlWithoutHostIsRejected();
    testBridgeUrlWithUserInfoIsRejected();
    testBridgeUrlWithQueryIsRejected();
    testBridgeUrlWithFragmentIsRejected();
    testOversizedBridgeUrlIsRejected();
    testInvalidBridgePortsAreRejected();
    testBoundaryBridgePortsAreAccepted();
    testBracketedIpv6IsRejectedUntilTheTransportSupportsIt();
    testInvalidHigherPrecedenceUrlDoesNotSilentlyFallBack();
    return 0;
}
