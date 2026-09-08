#include <cassert>
#include <hal/espnow_wifi.h>

int main()
{
    auto& wifi = WifiManager::GetInstance();
    // Initial setup already created the shared event loop, driver and station netif.
    wifi.Initialize();
    wifi.station = true;
    wifi.callback = []() { assert(false && "handoff must not reconnect Wi-Fi"); };
    assert(stackchan::local::prepareEspNowWifi(6, &wifi.timer) == ESP_OK);
    assert(wifi.initializations == 1);
    assert(!wifi.station && !wifi.ap && !wifi.callback && !wifi.timer);
    assert(wifi.started && wifi.channel == 6);

    // Leaving the setup hotspot must suppress its normal reconnect callback as well.
    wifi.ap = true;
    wifi.timer = true;
    wifi.callback = []() { assert(false && "AP exit must not restart station"); };
    assert(stackchan::local::prepareEspNowWifi(13, &wifi.timer) == ESP_OK);
    assert(wifi.initializations == 1 && wifi.channel == 13);

    wifi.reset();
    assert(stackchan::local::prepareEspNowWifi(0, &wifi.timer) == ESP_OK);
    assert(wifi.initializations == 1 && wifi.channel == 1);
    assert(stackchan::local::prepareEspNowWifi(255, &wifi.timer) == ESP_OK);
    assert(wifi.initializations == 1 && wifi.channel == 13);

    wifi.reset();
    wifi.initializeOk = false;
    assert(stackchan::local::prepareEspNowWifi(1, &wifi.timer) != ESP_OK);
    assert(!wifi.started);
}
