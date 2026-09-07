/*
 * SPDX-FileCopyrightText: 2026 OpenAI
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once

#include <cstdint>

enum class HeadTouchTransition { None, Pressed, Released };

class HeadTouchDebouncer {
public:
    explicit HeadTouchDebouncer(std::uint8_t stableSamples)
        : HeadTouchDebouncer(stableSamples, stableSamples)
    {
    }

    HeadTouchDebouncer(std::uint8_t pressSamples, std::uint8_t releaseSamples)
        : pressSamples_(pressSamples == 0 ? 1 : pressSamples),
          releaseSamples_(releaseSamples == 0 ? 1 : releaseSamples)
    {
    }

    HeadTouchTransition update(bool touched)
    {
        if (!armed_) {
            if (touched) {
                idleSamples_ = 0;
                return HeadTouchTransition::None;
            }
            if (++idleSamples_ >= releaseSamples_) {
                armed_ = true;
            }
            return HeadTouchTransition::None;
        }

        if (touched == stableTouched_) {
            candidateSamples_ = 0;
            return HeadTouchTransition::None;
        }

        const std::uint8_t requiredSamples = touched ? pressSamples_ : releaseSamples_;
        if (candidateSamples_ < requiredSamples) {
            ++candidateSamples_;
        }
        if (candidateSamples_ < requiredSamples) {
            return HeadTouchTransition::None;
        }

        stableTouched_ = touched;
        candidateSamples_ = 0;
        if (!stableTouched_) {
            armed_ = false;
            idleSamples_ = 0;
        }
        return stableTouched_ ? HeadTouchTransition::Pressed : HeadTouchTransition::Released;
    }

    bool isArmed() const
    {
        return armed_;
    }

    bool isTouched() const
    {
        return stableTouched_;
    }

private:
    std::uint8_t pressSamples_;
    std::uint8_t releaseSamples_;
    std::uint8_t idleSamples_ = 0;
    std::uint8_t candidateSamples_ = 0;
    bool armed_ = false;
    bool stableTouched_ = false;
};
