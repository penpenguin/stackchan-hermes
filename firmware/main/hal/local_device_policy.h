#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace stackchan::local {

inline int restoreAppIndex(std::string_view name, const std::vector<std::string>& installed)
{
    if (!name.empty()) {
        for (std::size_t index = 0; index < installed.size(); ++index) {
            if (name == installed[index]) {
                return static_cast<int>(index);
            }
        }
    }
    return -1;
}

enum class IdlePowerState { Awake, Sleeping, Shutdown };

inline bool powerSaveEnabled(bool externalPower, bool discharging, bool allowWhenCharging)
{
    return discharging || (externalPower && allowWhenCharging);
}

inline IdlePowerState idlePowerState(
    std::uint32_t idleSeconds, std::uint32_t shutdownSeconds, bool enabled, bool busy)
{
    if (!enabled || busy) {
        return IdlePowerState::Awake;
    }
    if (shutdownSeconds > 0 && idleSeconds >= shutdownSeconds) {
        return IdlePowerState::Shutdown;
    }
    return idleSeconds >= 300 ? IdlePowerState::Sleeping : IdlePowerState::Awake;
}

}  // namespace stackchan::local
