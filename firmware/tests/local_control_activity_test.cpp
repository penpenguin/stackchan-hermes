#include <cassert>
#include <cstdint>
#include <hal/local_device_policy.h>
#include <hal/espnow_control.h>
#include <stackchan/json/json_helper.h>

static std::uint32_t nowMs = 0, lastActivityMs = 0;
namespace hal_bridge {
void note_activity() { lastActivityMs = nowMs; }
}

int main()
{
    using namespace stackchan;
    avatar::Avatar face;
    motion::Motion motion;
    addon::NeonLight left, right;

    // Each accepted BLE command family keeps battery-powered operation awake.
    for (auto family : {0, 1, 2}) {
        lastActivityMs = 0;
        for (nowMs = 60000; nowMs <= 1200000; nowMs += 60000) {
            if (family == 0) {
                avatar::update_from_json(&face, R"({"mouth":{"weight":10}})");
            } else if (family == 1) {
                motion::update_from_json(&motion, R"({"yawServo":{"angle":0,"speed":150}})");
            } else {
                addon::update_neon_light_from_json(&left, &right, R"({"leftRgbColor":"#ff0000"})");
            }
            assert(lastActivityMs == nowMs);
            assert(local::idlePowerState((nowMs - lastActivityMs) / 1000, 600, true, false)
                   == local::IdlePowerState::Awake);
        }
    }
    assert(face.lips.updates == 20 && motion.yaw.updates == 20 && left.updates == 20);

    // Junk, incomplete fields and packets with no operation must not postpone sleep.
    const auto lastAccepted = lastActivityMs;
    nowMs += 600000;
    for (const char* json : std::initializer_list<const char*>{nullptr, "", "{", "{}", "[]", R"({"other":1})",
                            R"({"mouth":{"x":1},"yawServo":{},"leftRgbColor":false})"}) {
        avatar::update_from_json(&face, json);
        motion::update_from_json(&motion, json);
        addon::update_neon_light_from_json(&left, &right, json);
    }
    assert(lastActivityMs == lastAccepted);
    assert(local::idlePowerState((nowMs - lastActivityMs) / 1000, 600, true, false)
           == local::IdlePowerState::Shutdown);

    motion::update_from_json(&motion, R"({"pitchServo":{"rotate":0}})");
    assert(lastActivityMs == nowMs);
    assert(local::idlePowerState(300, 600, true, false) == local::IdlePowerState::Sleeping);
    assert(local::idlePowerState(600, 600, true, false) == local::IdlePowerState::Shutdown);

    const std::vector<std::uint8_t> pose = {7, 0x9c, 0xff, 0xc2, 0x01, 0x58, 0x02, 1};
    int applied = 0;
    const auto apply = [&](const local::EspNowControlPose& command) {
        assert(command.yaw == -100 && command.pitch == 450 && command.speed == 600);
        assert(command.laser);
        ++applied;
    };
    const auto beforePacket = lastActivityMs;
    nowMs += 600000;
    assert(!local::applyEspNowControlPacket(pose, 8, apply));
    assert(!local::applyEspNowControlPacket({7, 0, 0}, 7, apply));
    assert(applied == 0 && lastActivityMs == beforePacket);
    assert(local::applyEspNowControlPacket(pose, 7, apply));
    assert(applied == 1 && lastActivityMs == nowMs);
    auto broadcast = pose;
    broadcast[0] = 0;
    for (int repeat = 0; repeat < 20; ++repeat) {
        nowMs += 60000;
        assert(local::applyEspNowControlPacket(broadcast, 8, apply));
        assert(local::idlePowerState((nowMs - lastActivityMs) / 1000, 600, true, false)
               == local::IdlePowerState::Awake);
    }
    assert(applied == 21);
}
