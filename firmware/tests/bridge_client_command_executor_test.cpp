#include <cstdlib>
#include <iostream>
#include <string>

#include <stackchan_bridge_client/command_executor.h>

namespace {

using stackchan::bridge_client::Command;
using stackchan::bridge_client::CommandName;
using stackchan::bridge_client::CommandResultField;
using stackchan::bridge_client::CommandTargetResult;
using stackchan::bridge_client::DeviceCommandTarget;
using stackchan::bridge_client::DeviceInfo;
using stackchan::bridge_client::DeviceStatus;
using stackchan::bridge_client::HeadAngles;
using stackchan::bridge_client::executeCommand;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

const CommandResultField* findField(
    const std::vector<CommandResultField>& fields,
    const std::string& name
)
{
    for (const auto& field : fields) {
        if (field.name == name) {
            return &field;
        }
    }
    return nullptr;
}

class FakeTarget final : public DeviceCommandTarget {
public:
    DeviceInfo getInfo() const override
    {
        DeviceInfo info;
        info.deviceId = "stackchan-001";
        info.deviceName = "StackChan";
        info.firmwareVersion = "1.5.1";
        info.hardwareModel = "M5STACK-K151";
        return info;
    }

    DeviceStatus getStatus() const override
    {
        DeviceStatus status;
        status.deviceId = "stackchan-001";
        status.firmwareVersion = "1.5.1";
        status.hardwareModel = "M5STACK-K151";
        status.state = "IDLE";
        status.batteryPercent = 82;
        status.volume = 75;
        status.brightness = 80;
        status.wifiRssiDbm = -54;
        return status;
    }

    bool setHeadAngles(double yaw, double pitch, int speed) override
    {
        ++setHeadAnglesCalls;
        lastYaw = yaw;
        lastPitch = pitch;
        lastMotionSpeed = speed;
        return true;
    }

    bool homeHead(int speed) override
    {
        ++homeHeadCalls;
        lastHomeSpeed = speed;
        return true;
    }

    bool getHeadAngles(HeadAngles& output) const override
    {
        output.yaw = 12.5;
        output.pitch = 34.5;
        return headAnglesAvailable;
    }

    bool cancelSpeech(const std::string& turnId) override
    {
        cancelledTurnId = turnId;
        return true;
    }

    CommandTargetResult startCapture(const std::string& captureId, int quality, int timeoutMs) override
    {
        lastCaptureId = captureId;
        lastCaptureQuality = quality;
        return captureResult;
    }

    bool setVolume(int volume) override
    {
        lastVolume = volume;
        return true;
    }

    bool setBrightness(int brightness) override
    {
        lastBrightness = brightness;
        return true;
    }

    bool showText(const std::string& text, int durationMs, int priority) override
    {
        lastText = text;
        lastTextDurationMs = durationMs;
        lastTextPriority = priority;
        return true;
    }

    bool setExpression(const std::string& expression) override
    {
        lastExpression = expression;
        return true;
    }

    bool setBlink(bool enabled) override
    {
        lastBlink = enabled;
        blinkCalls++;
        return true;
    }

    int ledCount() const override
    {
        return 12;
    }

    bool setLed(int index, int red, int green, int blue) override
    {
        lastLedIndex = index;
        lastRed = red;
        lastGreen = green;
        lastBlue = blue;
        return true;
    }

    bool setAllLeds(int red, int green, int blue) override
    {
        lastLedIndex = -2;
        lastRed = red;
        lastGreen = green;
        lastBlue = blue;
        return true;
    }

    bool clearLeds() override
    {
        clearLedCalls++;
        return true;
    }

    int setHeadAnglesCalls = 0;
    int homeHeadCalls = 0;
    double lastYaw = 0;
    double lastPitch = 0;
    int lastMotionSpeed = -1;
    int lastHomeSpeed = -1;
    int lastVolume = -1;
    int lastBrightness = -1;
    std::string lastText;
    int lastTextDurationMs = -1;
    int lastTextPriority = -1;
    std::string lastExpression;
    bool lastBlink = false;
    int blinkCalls = 0;
    int lastLedIndex = -1;
    int lastRed = -1;
    int lastGreen = -1;
    int lastBlue = -1;
    int clearLedCalls = 0;
    bool headAnglesAvailable = true;
    std::string cancelledTurnId;
    CommandTargetResult captureResult = CommandTargetResult::Success;
    std::string lastCaptureId;
    int lastCaptureQuality = -1;
};

void testGetStatusReturnsABoundedBoardSnapshot()
{
    FakeTarget target;
    Command command;
    command.name = CommandName::DeviceGetStatus;

    const auto result = executeCommand(command, target);

    expect(result.ok, "status execution failed");
    expect(result.fields.size() == 8, "status field count changed");
    expect(
        std::get<std::string>(findField(result.fields, "state")->value) == "IDLE",
        "state was not returned"
    );
    expect(
        std::get<std::int64_t>(findField(result.fields, "battery_percent")->value) == 82,
        "battery was not returned"
    );
}

void testVerifiedK151MotionBoundsReachHalWithSafeDefaults()
{
    FakeTarget target;
    Command command;
    command.name = CommandName::HeadSetAngles;
    command.arguments.yaw = -45;
    command.arguments.pitch = 5;

    const auto defaultSpeedResult = executeCommand(command, target);

    expect(defaultSpeedResult.ok, "lower-bound K151 motion was rejected");
    expect(target.setHeadAnglesCalls == 1, "safe K151 motion did not reach the HAL");
    expect(target.lastYaw == -45 && target.lastPitch == 5, "safe angles were changed");
    expect(target.lastMotionSpeed == 15, "safe default speed was not applied");

    command.arguments.yaw = 45;
    command.arguments.pitch = 85;
    command.arguments.hasSpeed = true;
    command.arguments.speed = 30;

    const auto explicitSpeedResult = executeCommand(command, target);

    expect(explicitSpeedResult.ok, "upper-bound K151 motion was rejected");
    expect(target.setHeadAnglesCalls == 2, "upper-bound K151 motion did not reach the HAL");
    expect(target.lastYaw == 45 && target.lastPitch == 85, "upper-bound angles were changed");
    expect(target.lastMotionSpeed == 30, "safe explicit speed was changed");

    Command home;
    home.name = CommandName::HeadHome;
    const auto homeResult = executeCommand(home, target);
    expect(homeResult.ok, "safe K151 home was rejected");
    expect(target.homeHeadCalls == 1, "safe K151 home did not reach the HAL");
    expect(target.lastHomeSpeed == 15, "home did not use the safe default speed");
}

void testK151MotionOutsideThePhysicalProfileIsRejectedBeforeHal()
{
    struct Example {
        double yaw;
        double pitch;
        int speed;
    };
    const Example examples[] = {
        {-45.1, 45, 15},
        {45.1, 45, 15},
        {0, 4.9, 15},
        {0, 85.1, 15},
        {0, 45, 0},
        {0, 45, 31},
    };

    FakeTarget target;
    for (const auto& example : examples) {
        Command command;
        command.name = CommandName::HeadSetAngles;
        command.arguments.yaw = example.yaw;
        command.arguments.pitch = example.pitch;
        command.arguments.hasSpeed = true;
        command.arguments.speed = example.speed;

        const auto result = executeCommand(command, target);

        expect(!result.ok, "out-of-range K151 motion unexpectedly succeeded");
        expect(
            result.errorCode == stackchan::bridge_client::CommandErrorCode::InvalidArgument,
            "out-of-range K151 motion returned the wrong error"
        );
        expect(target.setHeadAnglesCalls == 0, "out-of-range K151 motion reached the HAL");
    }

    Command home;
    home.name = CommandName::HeadHome;
    home.arguments.hasSpeed = true;
    home.arguments.speed = 31;
    const auto homeResult = executeCommand(home, target);
    expect(!homeResult.ok, "out-of-range K151 home unexpectedly succeeded");
    expect(
        homeResult.errorCode == stackchan::bridge_client::CommandErrorCode::InvalidArgument,
        "out-of-range K151 home returned the wrong error"
    );
    expect(target.homeHeadCalls == 0, "out-of-range K151 home reached the HAL");
}

void testBoundedSettingsReachTheTarget()
{
    FakeTarget target;

    Command volume;
    volume.name = CommandName::AudioSetVolume;
    volume.arguments.volume = 37;
    const auto volumeResult = executeCommand(volume, target);

    Command brightness;
    brightness.name = CommandName::DisplaySetBrightness;
    brightness.arguments.brightness = 64;
    const auto brightnessResult = executeCommand(brightness, target);

    expect(volumeResult.ok, "volume command failed");
    expect(volumeResult.fields.empty(), "volume result was not empty");
    expect(target.lastVolume == 37, "volume did not reach the target");
    expect(brightnessResult.ok, "brightness command failed");
    expect(brightnessResult.fields.empty(), "brightness result was not empty");
    expect(target.lastBrightness == 64, "brightness did not reach the target");
}

void testOutOfRangeSettingsAreRejectedBeforeHal()
{
    FakeTarget target;

    for (const int volume : {-1, 101}) {
        Command command;
        command.name = CommandName::AudioSetVolume;
        command.arguments.volume = volume;
        const auto result = executeCommand(command, target);
        expect(!result.ok, "out-of-range volume unexpectedly succeeded");
        expect(
            result.errorCode
                == stackchan::bridge_client::CommandErrorCode::InvalidArgument,
            "out-of-range volume returned the wrong error"
        );
        expect(target.lastVolume == -1, "out-of-range volume reached the HAL");
    }

    for (const int brightness : {-1, 101}) {
        Command command;
        command.name = CommandName::DisplaySetBrightness;
        command.arguments.brightness = brightness;
        const auto result = executeCommand(command, target);
        expect(!result.ok, "out-of-range brightness unexpectedly succeeded");
        expect(
            result.errorCode
                == stackchan::bridge_client::CommandErrorCode::InvalidArgument,
            "out-of-range brightness returned the wrong error"
        );
        expect(target.lastBrightness == -1, "out-of-range brightness reached the HAL");
    }
}

void testBoundedTextPresentationReachesTheTarget()
{
    FakeTarget target;
    Command command;
    command.name = CommandName::DisplayShowText;
    command.arguments.text = "こんにちは";
    command.arguments.durationMs = 2'000;
    command.arguments.priority = 4;

    const auto result = executeCommand(command, target);

    expect(result.ok, "display text command failed");
    expect(target.lastText == "こんにちは", "display text was changed");
    expect(target.lastTextDurationMs == 2'000, "display duration was changed");
    expect(target.lastTextPriority == 4, "display priority was changed");
}

void testInvalidTextPresentationIsRejectedBeforeHal()
{
    FakeTarget target;
    struct Example {
        const char* text;
        int durationMs;
        int priority;
    };
    const Example examples[] = {
        {"", 2'000, 4},
        {"line\nbreak", 2'000, 4},
        {"safe", 99, 4},
        {"safe", 2'000, 11},
    };
    for (const auto& example : examples) {
        Command command;
        command.name = CommandName::DisplayShowText;
        command.arguments.text = example.text;
        command.arguments.durationMs = example.durationMs;
        command.arguments.priority = example.priority;
        const auto result = executeCommand(command, target);
        expect(!result.ok, "invalid display text unexpectedly succeeded");
        expect(
            result.errorCode
                == stackchan::bridge_client::CommandErrorCode::InvalidArgument,
            "invalid display text returned the wrong error"
        );
        expect(target.lastText.empty(), "invalid display text reached the HAL");
    }
}

void testAvatarControlsReachTheTarget()
{
    FakeTarget target;

    Command expression;
    expression.name = CommandName::AvatarSetExpression;
    expression.arguments.expression = "thinking";
    const auto expressionResult = executeCommand(expression, target);

    Command blink;
    blink.name = CommandName::AvatarSetBlink;
    blink.arguments.enabled = true;
    const auto blinkResult = executeCommand(blink, target);

    expect(expressionResult.ok, "avatar expression command failed");
    expect(target.lastExpression == "thinking", "avatar expression was changed");
    expect(blinkResult.ok, "avatar blink command failed");
    expect(target.blinkCalls == 1 && target.lastBlink, "avatar blink was changed");
}

void testUnknownAvatarExpressionIsRejectedBeforeHal()
{
    FakeTarget target;
    Command command;
    command.name = CommandName::AvatarSetExpression;
    command.arguments.expression = "angry";

    const auto result = executeCommand(command, target);

    expect(!result.ok, "unknown avatar expression unexpectedly succeeded");
    expect(
        result.errorCode == stackchan::bridge_client::CommandErrorCode::InvalidArgument,
        "unknown avatar expression returned the wrong error"
    );
    expect(target.lastExpression.empty(), "unknown avatar expression reached the HAL");
}

void testLedControlsReachTheTarget()
{
    FakeTarget target;

    Command set;
    set.name = CommandName::LedSet;
    set.arguments.index = 3;
    set.arguments.red = 10;
    set.arguments.green = 20;
    set.arguments.blue = 30;
    const auto setResult = executeCommand(set, target);
    expect(setResult.ok, "single LED command failed");
    expect(
        target.lastLedIndex == 3 && target.lastRed == 10 && target.lastGreen == 20
            && target.lastBlue == 30,
        "single LED values were changed"
    );

    Command setAll;
    setAll.name = CommandName::LedSetAll;
    setAll.arguments.red = 40;
    setAll.arguments.green = 50;
    setAll.arguments.blue = 60;
    const auto setAllResult = executeCommand(setAll, target);
    expect(setAllResult.ok, "all LED command failed");
    expect(
        target.lastLedIndex == -2 && target.lastRed == 40 && target.lastGreen == 50
            && target.lastBlue == 60,
        "all LED values were changed"
    );

    Command clear;
    clear.name = CommandName::LedClear;
    const auto clearResult = executeCommand(clear, target);
    expect(clearResult.ok, "clear LED command failed");
    expect(target.clearLedCalls == 1, "clear LED did not reach the target");
}

void testLedIndexOutsideAdvertisedCountIsRejectedBeforeHal()
{
    FakeTarget target;
    Command command;
    command.name = CommandName::LedSet;
    command.arguments.index = 12;
    command.arguments.red = 1;
    command.arguments.green = 2;
    command.arguments.blue = 3;

    const auto result = executeCommand(command, target);

    expect(!result.ok, "out-of-range LED index unexpectedly succeeded");
    expect(
        result.errorCode == stackchan::bridge_client::CommandErrorCode::InvalidArgument,
        "out-of-range LED index returned the wrong error"
    );
    expect(target.lastLedIndex == -1, "out-of-range LED index reached the HAL");
}

void testReadOnlyDeviceAndHeadCommandsReturnScalarSnapshots()
{
    FakeTarget target;

    Command info;
    info.name = CommandName::DeviceGetInfo;
    const auto infoResult = executeCommand(info, target);
    expect(infoResult.ok, "device info command failed");
    expect(
        std::get<std::string>(findField(infoResult.fields, "device_name")->value)
            == "StackChan",
        "device name was not returned"
    );

    Command angles;
    angles.name = CommandName::HeadGetAngles;
    const auto anglesResult = executeCommand(angles, target);
    expect(anglesResult.ok, "head angle command failed");
    expect(
        std::get<double>(findField(anglesResult.fields, "yaw")->value) == 12.5,
        "yaw was not returned"
    );
    expect(
        std::get<double>(findField(anglesResult.fields, "pitch")->value) == 34.5,
        "pitch was not returned"
    );
}

void testSpeechCancellationRetainsTurnOwnership()
{
    FakeTarget target;
    Command command;
    command.name = CommandName::SpeechCancel;
    command.turnId = "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7";

    const auto result = executeCommand(command, target);

    expect(result.ok, "speech cancellation failed");
    expect(
        target.cancelledTurnId == "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "speech cancellation lost turn ownership"
    );
}

void testCameraCaptureStartsOnceAndReportsBusy()
{
    FakeTarget target;
    Command command;
    command.name = CommandName::CameraCapture;
    command.arguments.captureId = "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7";
    command.arguments.captureTimeoutMs = 10000;
    command.arguments.quality = 80;

    const auto accepted = executeCommand(command, target);
    expect(accepted.ok, "available camera capture was not accepted");
    expect(
        target.lastCaptureId == "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7"
            && target.lastCaptureQuality == 80,
        "camera capture values were changed"
    );

    target.captureResult = CommandTargetResult::DeviceBusy;
    const auto busy = executeCommand(command, target);
    expect(!busy.ok, "concurrent camera capture unexpectedly succeeded");
    expect(
        busy.errorCode == stackchan::bridge_client::CommandErrorCode::DeviceBusy,
        "concurrent camera capture returned the wrong error"
    );
}

void testInvalidCameraCaptureIsRejectedBeforeHal()
{
    FakeTarget target;
    struct Example {
        const char* captureId;
        int quality;
    };
    const Example examples[] = {
        {"not-a-uuid", 80},
        {"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7", 9},
        {"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7", 96},
    };
    for (const auto& example : examples) {
        Command command;
        command.name = CommandName::CameraCapture;
        command.arguments.captureId = example.captureId;
        command.arguments.captureTimeoutMs = 10000;
    command.arguments.quality = example.quality;
        const auto result = executeCommand(command, target);
        expect(!result.ok, "invalid camera capture unexpectedly succeeded");
        expect(
            result.errorCode
                == stackchan::bridge_client::CommandErrorCode::InvalidArgument,
            "invalid camera capture returned the wrong error"
        );
        expect(target.lastCaptureId.empty(), "invalid camera capture reached the HAL");
    }
}

}  // namespace


int main()
{
    testGetStatusReturnsABoundedBoardSnapshot();
    testVerifiedK151MotionBoundsReachHalWithSafeDefaults();
    testK151MotionOutsideThePhysicalProfileIsRejectedBeforeHal();
    testBoundedSettingsReachTheTarget();
    testOutOfRangeSettingsAreRejectedBeforeHal();
    testBoundedTextPresentationReachesTheTarget();
    testInvalidTextPresentationIsRejectedBeforeHal();
    testAvatarControlsReachTheTarget();
    testUnknownAvatarExpressionIsRejectedBeforeHal();
    testLedControlsReachTheTarget();
    testLedIndexOutsideAdvertisedCountIsRejectedBeforeHal();
    testReadOnlyDeviceAndHeadCommandsReturnScalarSnapshots();
    testSpeechCancellationRetainsTurnOwnership();
    testCameraCaptureStartsOnceAndReportsBusy();
    testInvalidCameraCaptureIsRejectedBeforeHal();
    return 0;
}
