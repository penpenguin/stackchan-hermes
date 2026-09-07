#include "head_touch_debouncer.h"

#include <cstdlib>
#include <iostream>

namespace {

void expect(bool condition, const char* message)
{
    if (!condition) {
        std::cerr << message << '\n';
        std::exit(1);
    }
}

void testStartupTransientDoesNotEmitTouch()
{
    HeadTouchDebouncer debouncer(3);

    expect(
        debouncer.update(true) == HeadTouchTransition::None,
        "startup touch sample emitted a press"
    );
    expect(
        debouncer.update(false) == HeadTouchTransition::None,
        "startup release sample emitted a release"
    );
    expect(
        debouncer.update(false) == HeadTouchTransition::None,
        "startup idle qualification emitted an event"
    );
    expect(
        debouncer.update(false) == HeadTouchTransition::None,
        "arming the idle baseline emitted an event"
    );
    expect(debouncer.isArmed(), "stable idle baseline did not arm touch input");
}

void testStableTouchEmitsOnePressAndOneRelease()
{
    HeadTouchDebouncer debouncer(3);

    for (int sample = 0; sample < 3; ++sample) {
        expect(
            debouncer.update(false) == HeadTouchTransition::None,
            "idle baseline emitted an event"
        );
    }
    expect(debouncer.update(true) == HeadTouchTransition::None, "first touch sample emitted a press");
    expect(debouncer.update(true) == HeadTouchTransition::None, "second touch sample emitted a press");
    expect(
        debouncer.update(true) == HeadTouchTransition::Pressed,
        "stable touch did not emit a press"
    );
    expect(
        debouncer.update(true) == HeadTouchTransition::None,
        "held touch emitted a duplicate press"
    );
    expect(
        debouncer.update(false) == HeadTouchTransition::None,
        "first release sample emitted a release"
    );
    expect(
        debouncer.update(false) == HeadTouchTransition::None,
        "second release sample emitted a release"
    );
    expect(
        debouncer.update(false) == HeadTouchTransition::Released,
        "stable release did not emit a release"
    );
    expect(
        debouncer.update(false) == HeadTouchTransition::None,
        "idle input emitted a duplicate release"
    );
}

void testHeldStartupTouchMustReleaseBeforeArming()
{
    HeadTouchDebouncer debouncer(3);

    for (int sample = 0; sample < 10; ++sample) {
        expect(
            debouncer.update(true) == HeadTouchTransition::None,
            "held startup touch emitted an event"
        );
    }
    expect(!debouncer.isArmed(), "held startup touch armed input");
    for (int sample = 0; sample < 3; ++sample) {
        expect(
            debouncer.update(false) == HeadTouchTransition::None,
            "startup release emitted an event"
        );
    }
    expect(debouncer.isArmed(), "release after startup touch did not arm input");
}

void testTransientTouchAfterArmingDoesNotEmitTouch()
{
    HeadTouchDebouncer debouncer(3);

    for (int sample = 0; sample < 3; ++sample) {
        debouncer.update(false);
    }
    expect(debouncer.update(true) == HeadTouchTransition::None, "first noise sample emitted a press");
    expect(debouncer.update(true) == HeadTouchTransition::None, "second noise sample emitted a press");
    expect(
        debouncer.update(false) == HeadTouchTransition::None,
        "rejected touch noise emitted a release"
    );
    expect(!debouncer.isTouched(), "rejected touch noise changed the stable state");
}

void testReleaseBounceMustReturnToStableIdleBeforeAnotherPress()
{
    HeadTouchDebouncer debouncer(3);

    for (int sample = 0; sample < 3; ++sample) {
        debouncer.update(false);
    }
    for (int sample = 0; sample < 2; ++sample) {
        expect(
            debouncer.update(true) == HeadTouchTransition::None,
            "touch became stable too early"
        );
    }
    expect(
        debouncer.update(true) == HeadTouchTransition::Pressed,
        "stable touch did not emit the first press"
    );
    for (int sample = 0; sample < 2; ++sample) {
        expect(
            debouncer.update(false) == HeadTouchTransition::None,
            "release became stable too early"
        );
    }
    expect(
        debouncer.update(false) == HeadTouchTransition::Released,
        "stable release did not emit the first release"
    );

    for (int sample = 0; sample < 6; ++sample) {
        expect(
            debouncer.update(true) == HeadTouchTransition::None,
            "release bounce emitted a duplicate press"
        );
    }
    expect(!debouncer.isArmed(), "release bounce rearmed touch input");

    for (int sample = 0; sample < 3; ++sample) {
        expect(
            debouncer.update(false) == HeadTouchTransition::None,
            "stable idle rearming emitted an event"
        );
    }
    expect(debouncer.isArmed(), "stable idle did not rearm touch input");
    for (int sample = 0; sample < 2; ++sample) {
        expect(
            debouncer.update(true) == HeadTouchTransition::None,
            "second deliberate touch became stable too early"
        );
    }
    expect(
        debouncer.update(true) == HeadTouchTransition::Pressed,
        "second deliberate touch was not accepted after stable idle"
    );
}

void testLongerPressQualificationRejectsShortNoContactBurst()
{
    HeadTouchDebouncer debouncer(6, 3);

    for (int sample = 0; sample < 3; ++sample) {
        expect(
            debouncer.update(false) == HeadTouchTransition::None,
            "idle baseline emitted an event"
        );
    }
    expect(debouncer.isArmed(), "release threshold did not arm touch input");

    for (int sample = 0; sample < 5; ++sample) {
        expect(
            debouncer.update(true) == HeadTouchTransition::None,
            "short no-contact burst emitted a press"
        );
    }
    expect(
        debouncer.update(false) == HeadTouchTransition::None,
        "rejected no-contact burst emitted a release"
    );
    expect(!debouncer.isTouched(), "rejected no-contact burst changed the stable state");

    for (int sample = 0; sample < 5; ++sample) {
        expect(
            debouncer.update(true) == HeadTouchTransition::None,
            "deliberate touch became stable too early"
        );
    }
    expect(
        debouncer.update(true) == HeadTouchTransition::Pressed,
        "longer deliberate touch did not emit a press"
    );
    for (int sample = 0; sample < 2; ++sample) {
        expect(
            debouncer.update(false) == HeadTouchTransition::None,
            "release became stable too early"
        );
    }
    expect(
        debouncer.update(false) == HeadTouchTransition::Released,
        "release threshold did not emit a release"
    );
}

}  // namespace

int main()
{
    testStartupTransientDoesNotEmitTouch();
    testStableTouchEmitsOnePressAndOneRelease();
    testHeldStartupTouchMustReleaseBeforeArming();
    testTransientTouchAfterArmingDoesNotEmitTouch();
    testReleaseBounceMustReturnToStableIdleBeforeAnotherPress();
    testLongerPressQualificationRejectsShortNoContactBurst();
    return 0;
}
