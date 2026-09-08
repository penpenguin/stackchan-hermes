#pragma once
#include <cassert>
#include <functional>

using esp_err_t = int;
using esp_timer_handle_t = bool*;
constexpr int ESP_OK = 0;
constexpr int ESP_FAIL = -1;
constexpr int ESP_ERR_INVALID_STATE = 0x103;
constexpr int WIFI_MODE_STA = 1;
constexpr int WIFI_SECOND_CHAN_NONE = 0;

class WifiManager {
public:
    static WifiManager& GetInstance() { static WifiManager wifi; return wifi; }
    bool Initialize() {
        if (!initializeOk) { return false; }
        if (!initialized) { ++initializations; initialized = true; }
        return true;
    }
    template<class Callback> void SetEventCallback(Callback) { callback = nullptr; }
    void StopStation() {
        assert(!timer && !callback);
        station = false;
        started = false;
    }
    void StopConfigAp() {
        ap = false;
        started = false;
        if (callback) { callback(); }
    }
    void reset() { *this = WifiManager{}; }
    bool initialized = false, initializeOk = true;
    bool station = false, ap = false, started = false, timer = false;
    int initializations = 0, channel = 0;
    std::function<void()> callback;
};

inline esp_err_t esp_timer_stop(esp_timer_handle_t timer) {
    const bool wasRunning = *timer;
    *timer = false;
    return wasRunning ? ESP_OK : ESP_ERR_INVALID_STATE;
}
inline esp_err_t esp_wifi_set_mode(int mode) {
    auto& w = WifiManager::GetInstance();
    assert(w.initialized && !w.station && !w.ap && mode == WIFI_MODE_STA);
    return ESP_OK;
}
inline esp_err_t esp_wifi_start() {
    WifiManager::GetInstance().started = true;
    return ESP_OK;
}
inline esp_err_t esp_wifi_set_channel(int channel, int) {
    assert(WifiManager::GetInstance().started);
    WifiManager::GetInstance().channel = channel;
    return ESP_OK;
}
