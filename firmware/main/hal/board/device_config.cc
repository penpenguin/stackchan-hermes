/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "device_config.h"
#include <settings.h>
#include <algorithm>
#include <string_view>

static constexpr std::string_view _xiaozhi_config_nvs_ns                           = "xiaozhi";
static constexpr std::string_view _xiaozhi_config_idle_shutdown_time_key           = "idle_sec";
static constexpr std::string_view _xiaozhi_config_allow_shutdown_when_charging_key = "ext_pwr";
static constexpr std::string_view _xiaozhi_config_idle_random_movement_key         = "idle_lv";

namespace hal_bridge {

DeviceConfig_t get_device_config()
{
    DeviceConfig_t config;

    Settings settings(_xiaozhi_config_nvs_ns.data(), false);
    config.idleShutdownTimeSeconds = settings.GetInt(_xiaozhi_config_idle_shutdown_time_key.data(),
                                                     static_cast<int>(config.idleShutdownTimeSeconds));
    config.allowShutdownWhenCharging =
        settings.GetBool(_xiaozhi_config_allow_shutdown_when_charging_key.data(), config.allowShutdownWhenCharging);
    Settings motionSettings("motion", false);
    const int idle_level = motionSettings.GetInt("idle_level",
        settings.GetInt(_xiaozhi_config_idle_random_movement_key.data(), config.idleRandomMovementLevel));
    config.idleRandomMovementLevel = idle_level >= 0 && idle_level <= 3 ? idle_level : 0;

    config.idleShutdownTimeSeconds = std::min(config.idleShutdownTimeSeconds, uint32_t{3600});
    return config;
}

void set_device_config(const DeviceConfig_t& config)
{
    Settings settings(_xiaozhi_config_nvs_ns.data(), true);
    settings.SetInt(_xiaozhi_config_idle_shutdown_time_key.data(), config.idleShutdownTimeSeconds);
    settings.SetBool(_xiaozhi_config_allow_shutdown_when_charging_key.data(), config.allowShutdownWhenCharging);
    settings.SetInt(_xiaozhi_config_idle_random_movement_key.data(), config.idleRandomMovementLevel);
    Settings motionSettings("motion", true);
    motionSettings.SetInt("idle_level", config.idleRandomMovementLevel);
}

}  // namespace hal_bridge
