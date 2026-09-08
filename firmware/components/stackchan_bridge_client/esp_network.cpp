// SPDX-License-Identifier: Apache-2.0
// Derived from 78/esp-ml307@3.6.5 src/esp/esp_network.cc (locked component).
// Modified for StackChan Hermes: retain Bridge transports, remove MQTT/UDP factories.
// Original license: third_party/esp-ml307-LICENSE.
#include <esp_network.h>
#include <src/esp/esp_tcp.h>
#include <src/esp/esp_ssl.h>
#include <http_client.h>
#include <web_socket.h>

EspNetwork::EspNetwork() = default;
EspNetwork::~EspNetwork() = default;

std::unique_ptr<Http> EspNetwork::CreateHttp(int connect_id)
{
    return std::make_unique<HttpClient>(this, connect_id);
}

std::unique_ptr<Tcp> EspNetwork::CreateTcp(int)
{
    return std::make_unique<EspTcp>();
}

std::unique_ptr<Tcp> EspNetwork::CreateSsl(int)
{
    return std::make_unique<EspSsl>();
}

std::unique_ptr<Udp> EspNetwork::CreateUdp(int)
{
    return nullptr;
}

std::unique_ptr<Mqtt> EspNetwork::CreateMqtt(int)
{
    return nullptr;
}

std::unique_ptr<WebSocket> EspNetwork::CreateWebSocket(int connect_id)
{
    return std::make_unique<WebSocket>(this, connect_id);
}
