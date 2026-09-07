#include <cstdlib>
#include <iostream>
#include <string>

#include <stackchan_bridge_client/discovery.h>

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
    return MdnsBridgeService{"192.0.2.20", 8765, "1", "true"};
}

void testCompatibleAuthenticatedServiceBuildsBoundedUrl()
{
    expect(
        buildMdnsBridgeWebSocketUrl(validService())
            == "ws://192.0.2.20:8765/v1/device/ws",
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
    testCompatibleAuthenticatedServiceBuildsBoundedUrl();
    testUnsupportedProtocolIsRejected();
    testServiceWithoutRequiredAuthenticationIsRejected();
    testInvalidAddressAndPortAreRejected();
    return 0;
}
