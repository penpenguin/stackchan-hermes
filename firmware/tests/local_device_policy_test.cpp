#include <cassert>
#include <hal/local_device_policy.h>
#include <hal/local_tasks.h>

int main()
{
    using namespace stackchan::local;
    assert(restoreAppIndex("SETUP", {"AVATAR", "DANCE", "SETUP"}) == 2);
    assert(restoreAppIndex("SETUP", {"SETUP", "AVATAR"}) == 0);
    assert(restoreAppIndex("", {"AVATAR", "SETUP"}) == -1);
    assert(restoreAppIndex("6", {"AVATAR", "SETUP"}) == -1);
    assert(restoreAppIndex("AI.Agent", {"AVATAR", "SETUP"}) == -1);
    assert(restoreAppIndex("APP CENTER", {"AVATAR", "SETUP"}) == -1);
    assert(idlePowerState(299, 600, true, false) == IdlePowerState::Awake);
    assert(idlePowerState(300, 600, true, false) == IdlePowerState::Sleeping);
    assert(idlePowerState(600, 600, true, false) == IdlePowerState::Shutdown);
    assert(idlePowerState(600, 600, false, false) == IdlePowerState::Awake);
    assert(idlePowerState(600, 600, true, true) == IdlePowerState::Awake);
    assert(idlePowerState(99999, 0, true, false) == IdlePowerState::Sleeping);
    assert(idlePowerState(0, 600, true, false) == IdlePowerState::Awake);
    assert(!powerSaveEnabled(true, false, false));
    assert(powerSaveEnabled(true, false, true));
    assert(powerSaveEnabled(false, true, false));

    LocalTasks tasks;
    int played = 0;
    assert(tasks.schedule([&]() { ++played; }));
    assert(played == 0);
    tasks.runOne();
    assert(played == 1);
    tasks.runOne();
    assert(played == 1);
    for (int i = 0; i < 8; ++i) { assert(tasks.schedule([&]() { ++played; })); }
    assert(!tasks.schedule([&]() { played = -100; }));
    for (int i = 0; i < 8; ++i) { tasks.runOne(); }
    assert(played == 9);
    assert(tasks.schedule([&]() { assert(tasks.schedule([&]() { ++played; })); }));
    tasks.runOne();
    tasks.runOne();
    assert(played == 10);
}
