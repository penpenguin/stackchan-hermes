#include <hal/board/device_config.h>
#include <settings.h>
#include <cassert>

int main()
{
    using namespace hal_bridge;
    assert(get_device_config().idleRandomMovementLevel == 2);
    Settings legacy("xiaozhi", true);
    legacy.SetInt("idle_lv", 1);
    legacy.SetInt("idle_sec", 1200);
    legacy.SetBool("ext_pwr", true);
    assert(get_device_config().idleRandomMovementLevel == 1);

    Settings motion("motion", true);
    motion.SetInt("idle_level", 0); // A USB setting overrides the legacy value.
    auto config = get_device_config();
    assert(config.idleRandomMovementLevel == 0);
    assert(config.idleShutdownTimeSeconds == 1200 && config.allowShutdownWhenCharging);

    config.idleRandomMovementLevel = 3;
    set_device_config(config); // Local UI confirmation must survive a fresh settings read.
    assert(motion.GetInt("idle_level") == 3);
    assert(legacy.GetInt("idle_lv") == 3);
    assert(get_device_config().idleRandomMovementLevel == 3);

    motion.SetInt("idle_level", 1); // Later USB edits remain authoritative.
    config = get_device_config();
    assert(config.idleRandomMovementLevel == 1);
    config.idleShutdownTimeSeconds = 900;
    set_device_config(config); // Saving power options must keep the effective movement level.
    assert(get_device_config().idleRandomMovementLevel == 1);
    assert(get_device_config().idleShutdownTimeSeconds == 900);

    Settings::values.clear();
    config.idleRandomMovementLevel = 2;
    set_device_config(config);
    assert(motion.GetInt("idle_level", -1) == 2);
    assert(get_device_config().idleRandomMovementLevel == 2);
    for (int invalid : {-1, 4, 256}) {
        motion.SetInt("idle_level", invalid);
        assert(get_device_config().idleRandomMovementLevel == 0);
    }
}
