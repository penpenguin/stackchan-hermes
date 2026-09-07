#include "stackchan_bridge_mdns.h"

#include <cstring>
#include <memory>
#include <string>

#include <esp_err.h>
#include <esp_netif.h>
#include <mdns.h>
#include <stackchan_bridge_client/discovery.h>

namespace stackchan::hermes {
namespace {

std::string txtValue(const mdns_result_t& result, const char* key)
{
    if (result.txt == nullptr || result.txt_value_len == nullptr) {
        return {};
    }
    for (std::size_t index = 0; index < result.txt_count; ++index) {
        const auto& item = result.txt[index];
        if (item.key != nullptr && item.value != nullptr && std::strcmp(item.key, key) == 0) {
            return std::string(item.value, result.txt_value_len[index]);
        }
    }
    return {};
}

std::string compatibleUrl(const mdns_result_t& result)
{
    for (const mdns_ip_addr_t* address = result.addr; address != nullptr;
         address = address->next) {
        if (address->addr.type != ESP_IPADDR_TYPE_V4) {
            continue;
        }
        char ipv4[IP4ADDR_STRLEN_MAX]{};
        if (esp_ip4addr_ntoa(&address->addr.u_addr.ip4, ipv4, sizeof(ipv4)) == nullptr) {
            continue;
        }
        bridge_client::MdnsBridgeService service;
        service.ipv4Address = ipv4;
        service.port = result.port;
        service.protocolVersion = txtValue(result, "protocol_version");
        service.authRequired = txtValue(result, "auth_required");
        const std::string url = bridge_client::buildMdnsBridgeWebSocketUrl(service);
        if (!url.empty()) {
            return url;
        }
    }
    return {};
}

}  // namespace

std::string discoverStackchanHermesBridgeUrl()
{
    if (mdns_init() != ESP_OK) {
        return {};
    }

    mdns_result_t* results = nullptr;
    const esp_err_t queryResult =
        mdns_query_ptr("_stackchan-hermes", "_tcp", 2000, 4, &results);
    std::unique_ptr<mdns_result_t, decltype(&mdns_query_results_free)> ownedResults(
        results,
        &mdns_query_results_free
    );
    if (queryResult != ESP_OK) {
        return {};
    }

    std::string discoveredUrl;
    for (const mdns_result_t* result = ownedResults.get(); result != nullptr;
         result = result->next) {
        discoveredUrl = compatibleUrl(*result);
        if (!discoveredUrl.empty()) {
            break;
        }
    }
    return discoveredUrl;
}

}  // namespace stackchan::hermes
