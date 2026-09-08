#pragma once

#include <algorithm>
#include <esp_timer.h>
#include <esp_wifi.h>
#include <wifi_manager.h>

namespace stackchan::local {

inline esp_err_t prepareEspNowWifi(int channel, esp_timer_handle_t connectTimer)
{
    // The manager owns the event loop and driver, including after first-time setup.
    auto& wifi = WifiManager::GetInstance();
    if (!wifi.Initialize()) { return ESP_FAIL; }

    if (connectTimer) {
        const auto result = esp_timer_stop(connectTimer);
        if (result != ESP_OK && result != ESP_ERR_INVALID_STATE) { return result; }
    }
    // AP exit normally reconnects the station. ESP-NOW owns the selected channel
    // until leaving its app reboots, so stop that callback before stopping Wi-Fi.
    wifi.SetEventCallback(nullptr);
    wifi.StopStation();
    wifi.StopConfigAp();

    auto result = esp_wifi_set_mode(WIFI_MODE_STA);
    if (result != ESP_OK) { return result; }
    result = esp_wifi_start();
    if (result != ESP_OK) { return result; }
    return esp_wifi_set_channel(std::clamp(channel, 1, 13), WIFI_SECOND_CHAN_NONE);
}

}  // namespace stackchan::local
