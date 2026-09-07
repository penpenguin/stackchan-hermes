#include <cstdlib>
#include <iostream>

#include <stackchan_bridge_client/motion_safety.h>

namespace {

using stackchan::bridge_client::K151MotionSafety;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testDriverSpeedIsBoundedToTheOfficialK151Profile()
{
    expect(K151MotionSafety::clampDriverSpeed(-1) == 0, "negative driver speed was not clamped");
    expect(K151MotionSafety::clampDriverSpeed(150) == 150, "safe driver speed was changed");
    expect(K151MotionSafety::clampDriverSpeed(300) == 300, "maximum driver speed was changed");
    expect(K151MotionSafety::clampDriverSpeed(301) == 300, "excess driver speed was not clamped");
}

}  // namespace

int main()
{
    testDriverSpeedIsBoundedToTheOfficialK151Profile();
    return 0;
}
