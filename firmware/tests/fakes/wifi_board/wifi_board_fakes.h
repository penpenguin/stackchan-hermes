#pragma once

#include <cassert>
#include <cstdint>
#include <functional>
#include <string>
#include <utility>
#include <vector>

enum class NetworkEvent { Scanning, Connecting, Connected, Disconnected, WifiConfigModeEnter, WifiConfigModeExit };
enum class PowerSaveLevel { LOW_POWER, BALANCED, PERFORMANCE };
using NetworkEventCallback = std::function<void(NetworkEvent, const std::string&)>;
class AudioCodec {};
class NetworkInterface {};
class EspNetwork : public NetworkInterface {};
class Board {
public:
    virtual ~Board() = default;
    virtual std::string GetBoardType() = 0;
    virtual void StartNetwork() = 0;
    virtual NetworkInterface* GetNetwork() = 0;
    virtual void SetNetworkEventCallback(NetworkEventCallback) = 0;
    virtual const char* GetNetworkStateIcon() = 0;
    virtual void SetPowerSaveLevel(PowerSaveLevel) = 0;
    virtual AudioCodec* GetAudioCodec() = 0;
};

struct FakeTimer {
    void (*callback)(void*);
    void* arg;
    bool active = false;
    void fire() { active = false; callback(arg); }
};
using esp_timer_handle_t = FakeTimer*;
struct esp_timer_create_args_t {
    void (*callback)(void*);
    void* arg;
    int dispatch_method;
    const char* name;
    bool skip_unhandled_events;
};
constexpr int ESP_TIMER_TASK = 0;
inline int esp_timer_create(const esp_timer_create_args_t* args, esp_timer_handle_t* timer) {
    *timer = new FakeTimer{args->callback, args->arg};
    return 0;
}
inline int esp_timer_start_once(esp_timer_handle_t timer, uint64_t) { timer->active = true; return 0; }
inline int esp_timer_stop(esp_timer_handle_t timer) { timer->active = false; return 0; }
inline int esp_timer_delete(esp_timer_handle_t timer) { delete timer; return 0; }
inline int pdMS_TO_TICKS(int value) { return value; }
inline void vTaskDelay(int) {}
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define FONT_AWESOME_WIFI "wifi"
#define FONT_AWESOME_WIFI_SLASH "offline"
#define FONT_AWESOME_WIFI_FAIR "fair"
#define FONT_AWESOME_WIFI_WEAK "weak"
namespace Lang { inline const char* CODE = "en-US"; }

class SsidManager {
public:
    static SsidManager& GetInstance() { static SsidManager instance; return instance; }
    const std::vector<std::string>& GetSsidList() { return ssids; }
    std::vector<std::string> ssids;
};

enum class WifiEvent { Scanning, Connecting, Connected, Disconnected, ConfigModeEnter, ConfigModeExit };
enum class WifiPowerSaveLevel { LOW_POWER, BALANCED, PERFORMANCE };
struct WifiManagerConfig { std::string ssid_prefix, language; };
class WifiManager {
public:
    static WifiManager& GetInstance() { static WifiManager instance; return instance; }
    bool Initialize(const WifiManagerConfig&) { return true; }
    void SetEventCallback(std::function<void(WifiEvent, const std::string&)> value) { callback = value; }
    void notify(WifiEvent event) { if (callback) { callback(event, ""); } }
    void StartStation() {
        assert(!ap);
        if (!station) { ++stationStarts; station = true; }
    }
    void StopStation() {
        if (auto hook = std::exchange(beforeStationStop, nullptr)) { hook(); }
        if (!station) { return; }
        station = connected = false;
        notify(WifiEvent::Disconnected);
    }
    void StartConfigAp() {
        if (auto hook = std::exchange(beforeApStart, nullptr)) { hook(); }
        if (ap) { return; }
        StopStation();
        ap = true;
        ++apStarts;
        notify(WifiEvent::ConfigModeEnter);
    }
    void StopConfigAp() {
        if (!ap) { return; }
        ap = false;
        notify(WifiEvent::ConfigModeExit);
    }
    bool IsConfigMode() const { return ap; }
    bool IsConnected() const { return station && connected; }
    int GetRssi() const { return -50; }
    void SetPowerSaveLevel(WifiPowerSaveLevel) {}
    void reset() { *this = WifiManager{}; SsidManager::GetInstance().ssids.clear(); }
    bool ap = false, station = false, connected = false;
    int apStarts = 0, stationStarts = 0;
    std::function<void()> beforeApStart, beforeStationStop;
    std::function<void(WifiEvent, const std::string&)> callback;
};
