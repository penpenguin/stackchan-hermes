#pragma once

#include <cstdint>
#include <vector>
#include <hal/local_activity.h>

namespace stackchan::local {

struct EspNowControlPose {
    std::int16_t yaw, pitch, speed;
    bool laser;
};

template<class Apply>
bool applyEspNowControlPacket(const std::vector<std::uint8_t>& data, std::uint8_t receiverId, Apply apply)
{
    // Existing wire format: target id, three little-endian int16 values, laser flag.
    if (data.size() < 8 || (data[0] != 0 && data[0] != receiverId)) { return false; }
    const auto read = [&](int offset) {
        return static_cast<std::int16_t>(data[offset] | (data[offset + 1] << 8));
    };
    apply(EspNowControlPose{read(1), read(3), read(5), data[7] != 0});
    hal_bridge::note_activity();
    return true;
}

}  // namespace stackchan::local
