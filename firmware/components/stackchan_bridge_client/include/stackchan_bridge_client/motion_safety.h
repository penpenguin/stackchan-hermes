// SPDX-FileCopyrightText: 2026 OpenAI
// SPDX-License-Identifier: MIT

#pragma once

namespace stackchan::bridge_client {

struct K151MotionSafety {
    static constexpr double kYawMinimumDegrees = -45.0;
    static constexpr double kYawMaximumDegrees = 45.0;
    static constexpr double kPitchMinimumDegrees = 5.0;
    static constexpr double kPitchMaximumDegrees = 85.0;
    static constexpr int kSpeedMinimum = 1;
    static constexpr int kSpeedMaximum = 30;
    static constexpr int kDefaultSpeed = 15;
    static constexpr int kDriverSpeedMaximum = kSpeedMaximum * 10;
    static constexpr double kHomeYawDegrees = 0.0;
    static constexpr double kHomePitchDegrees = 45.0;

    static constexpr bool contains(double yaw, double pitch, int speed)
    {
        return yaw >= kYawMinimumDegrees && yaw <= kYawMaximumDegrees
            && pitch >= kPitchMinimumDegrees && pitch <= kPitchMaximumDegrees
            && speed >= kSpeedMinimum && speed <= kSpeedMaximum;
    }

    static constexpr bool containsSpeed(int speed)
    {
        return speed >= kSpeedMinimum && speed <= kSpeedMaximum;
    }

    static constexpr int clampDriverSpeed(int speed)
    {
        if (speed < 0) {
            return 0;
        }
        if (speed > kDriverSpeedMaximum) {
            return kDriverSpeedMaximum;
        }
        return speed;
    }
};

}  // namespace stackchan::bridge_client
