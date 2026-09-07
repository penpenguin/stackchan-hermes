#include <cstdlib>
#include <iostream>

#include <stackchan_bridge_client/motion_command_safety.h>

namespace {

using stackchan::bridge_client::MotionCommandSafety;
using stackchan::bridge_client::MotionCommandSource;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testLocalMotionLockAllowsOnlyAuthenticatedBridgeMotion()
{
    MotionCommandSafety safety;
    safety.setLocalMotionLocked(true);

    expect(!safety.allowsMotion(MotionCommandSource::Local), "local motion bypassed the candidate lock");
    expect(safety.allowsMotion(MotionCommandSource::AuthenticatedBridge), "authenticated Bridge motion was blocked");
    expect(!safety.allowsTorque(true, MotionCommandSource::Local), "local torque enable bypassed the candidate lock");
    expect(safety.allowsTorque(false, MotionCommandSource::Local), "local torque disable was blocked");
}

void testUnlockedPolicyRetainsOfficialLocalMotion()
{
    MotionCommandSafety safety;

    expect(safety.allowsMotion(MotionCommandSource::Local), "official local motion was blocked by default");
    expect(safety.allowsTorque(true, MotionCommandSource::Local), "official local torque enable was blocked by default");
}

}  // namespace

int main()
{
    testLocalMotionLockAllowsOnlyAuthenticatedBridgeMotion();
    testUnlockedPolicyRetainsOfficialLocalMotion();
    return 0;
}
