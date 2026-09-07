#include <cstdlib>
#include <iostream>

#include <hal/servo_output_safety.h>

namespace {

using stackchan::motion::ServoOutputSafety;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testLockedGateRejectsMotionAndTorqueEnable()
{
    ServoOutputSafety safety(true);
    int writes = 0;

    expect(!safety.writePosition([&]() { ++writes; }), "locked gate accepted a position write");
    expect(!safety.writeVelocity([&]() { ++writes; }), "locked gate accepted a velocity write");
    expect(!safety.writeTorque(true, [&]() { ++writes; }), "locked gate accepted torque enable");
    expect(writes == 0, "locked gate invoked an unsafe hardware writer");
}

void testLockedGateAllowsTorqueDisable()
{
    ServoOutputSafety safety(true);
    int writes = 0;

    expect(safety.writeTorque(false, [&]() { ++writes; }), "locked gate rejected torque disable");
    expect(writes == 1, "locked gate did not invoke the torque-disable writer");
}

void testUnlockedGateAllowsAllOutputs()
{
    ServoOutputSafety safety(false);
    int writes = 0;

    expect(safety.writePosition([&]() { ++writes; }), "unlocked gate rejected a position write");
    expect(safety.writeVelocity([&]() { ++writes; }), "unlocked gate rejected a velocity write");
    expect(safety.writeTorque(true, [&]() { ++writes; }), "unlocked gate rejected torque enable");
    expect(writes == 3, "unlocked gate skipped a hardware writer");
}

}  // namespace

int main()
{
    testLockedGateRejectsMotionAndTorqueEnable();
    testLockedGateAllowsTorqueDisable();
    testUnlockedGateAllowsAllOutputs();
    return 0;
}
