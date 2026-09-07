/*
 * SPDX-FileCopyrightText: 2026 OpenAI
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once

namespace stackchan::motion {

class ServoOutputSafety {
public:
    explicit constexpr ServoOutputSafety(bool locked) : locked_(locked)
    {
    }

    constexpr bool locked() const
    {
        return locked_;
    }

    template <typename Writer> bool writePosition(Writer writer) const
    {
        return writeMotion(writer);
    }

    template <typename Writer> bool writeVelocity(Writer writer) const
    {
        return writeMotion(writer);
    }

    template <typename Writer> bool writeTorque(bool enabled, Writer writer) const
    {
        if (locked_ && enabled) {
            return false;
        }
        writer();
        return true;
    }

private:
    template <typename Writer> bool writeMotion(Writer writer) const
    {
        if (locked_) {
            return false;
        }
        writer();
        return true;
    }

    bool locked_;
};

}  // namespace stackchan::motion
