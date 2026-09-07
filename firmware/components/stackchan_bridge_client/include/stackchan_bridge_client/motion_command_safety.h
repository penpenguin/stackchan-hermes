// SPDX-FileCopyrightText: 2026 OpenAI
// SPDX-License-Identifier: MIT

#pragma once

namespace stackchan::bridge_client {

enum class MotionCommandSource {
    Local,
    AuthenticatedBridge,
};

class MotionCommandSafety {
public:
    constexpr void setLocalMotionLocked(bool locked)
    {
        localMotionLocked_ = locked;
    }

    constexpr bool localMotionLocked() const
    {
        return localMotionLocked_;
    }

    constexpr bool allowsMotion(MotionCommandSource source) const
    {
        return !localMotionLocked_ || source == MotionCommandSource::AuthenticatedBridge;
    }

    constexpr bool allowsTorque(bool enabled, MotionCommandSource source) const
    {
        return !enabled || allowsMotion(source);
    }

private:
    bool localMotionLocked_ = false;
};

}  // namespace stackchan::bridge_client
