#include <stackchan_bridge_client/command_executor.h>
#include <stackchan_bridge_client/motion_safety.h>

#include <array>
#include <cstdint>
#include <utility>

namespace stackchan::bridge_client {
namespace {

CommandExecutionResult invalidState(const std::string& message)
{
    CommandExecutionResult result;
    result.errorCode = CommandErrorCode::InvalidState;
    result.errorMessage = message;
    return result;
}

CommandExecutionResult invalidArgument(const std::string& message)
{
    CommandExecutionResult result;
    result.errorCode = CommandErrorCode::InvalidArgument;
    result.errorMessage = message;
    return result;
}

CommandExecutionResult deviceBusy(const std::string& message)
{
    CommandExecutionResult result;
    result.errorCode = CommandErrorCode::DeviceBusy;
    result.errorMessage = message;
    return result;
}

CommandExecutionResult success()
{
    CommandExecutionResult result;
    result.ok = true;
    return result;
}

CommandExecutionResult getStatus(const DeviceCommandTarget& target)
{
    const DeviceStatus status = target.getStatus();

    CommandExecutionResult result;
    result.ok = true;
    result.fields = {
        {"device_id", status.deviceId},
        {"firmware_version", status.firmwareVersion},
        {"hardware_model", status.hardwareModel},
        {"state", status.state},
        {"battery_percent", static_cast<std::int64_t>(status.batteryPercent)},
        {"volume", static_cast<std::int64_t>(status.volume)},
        {"brightness", static_cast<std::int64_t>(status.brightness)},
        {"wifi_rssi_dbm", static_cast<std::int64_t>(status.wifiRssiDbm)},
    };
    return result;
}

CommandExecutionResult getInfo(const DeviceCommandTarget& target)
{
    const DeviceInfo info = target.getInfo();

    CommandExecutionResult result;
    result.ok = true;
    result.fields = {
        {"device_id", info.deviceId},
        {"device_name", info.deviceName},
        {"firmware_version", info.firmwareVersion},
        {"hardware_model", info.hardwareModel},
    };
    return result;
}

bool isSupportedExpression(const std::string& expression)
{
    constexpr std::array<const char*, 6> kExpressions = {
        "idle", "happy", "thinking", "sad", "surprised", "embarrassed",
    };
    for (const char* candidate : kExpressions) {
        if (expression == candidate) {
            return true;
        }
    }
    return false;
}

bool isRgbValue(int value)
{
    return value >= 0 && value <= 255;
}

bool isUtf8Continuation(unsigned char value)
{
    return value >= 0x80 && value <= 0xBF;
}

bool isValidBoundedText(const std::string& value, std::size_t maximumCodePoints)
{
    if (value.empty()) {
        return false;
    }
    std::size_t codePoints = 0;
    for (std::size_t index = 0; index < value.size();) {
        const auto first = static_cast<unsigned char>(value[index]);
        std::size_t length = 0;
        if (first <= 0x7F) {
            if (first < 0x20 || first == 0x7F) {
                return false;
            }
            length = 1;
        } else if (first >= 0xC2 && first <= 0xDF) {
            length = 2;
        } else if (first >= 0xE0 && first <= 0xEF) {
            length = 3;
        } else if (first >= 0xF0 && first <= 0xF4) {
            length = 4;
        } else {
            return false;
        }
        if (index + length > value.size()) {
            return false;
        }
        for (std::size_t offset = 1; offset < length; ++offset) {
            if (!isUtf8Continuation(static_cast<unsigned char>(value[index + offset]))) {
                return false;
            }
        }
        if (length == 3) {
            const auto second = static_cast<unsigned char>(value[index + 1]);
            if ((first == 0xE0 && second < 0xA0) || (first == 0xED && second > 0x9F)) {
                return false;
            }
        }
        if (length == 4) {
            const auto second = static_cast<unsigned char>(value[index + 1]);
            if ((first == 0xF0 && second < 0x90) || (first == 0xF4 && second > 0x8F)) {
                return false;
            }
        }
        index += length;
        if (++codePoints > maximumCodePoints) {
            return false;
        }
    }
    return true;
}

bool isValidUuid(const std::string& value)
{
    if (value.size() != 36) {
        return false;
    }
    for (std::size_t index = 0; index < value.size(); ++index) {
        const bool separator = index == 8 || index == 13 || index == 18 || index == 23;
        const char character = value[index];
        const bool hex = (character >= '0' && character <= '9')
            || (character >= 'A' && character <= 'F')
            || (character >= 'a' && character <= 'f');
        if ((separator && character != '-') || (!separator && !hex)) {
            return false;
        }
    }
    return true;
}

}  // namespace

CommandExecutionResult executeCommand(const Command& command, DeviceCommandTarget& target)
{
    if (command.name == CommandName::DeviceGetStatus) {
        return getStatus(target);
    }
    if (command.name == CommandName::DeviceGetInfo) {
        return getInfo(target);
    }
    if (command.name == CommandName::AudioSetVolume) {
        if (command.arguments.volume < 0 || command.arguments.volume > 100) {
            return invalidArgument("Volume is outside the supported range");
        }
        return target.setVolume(command.arguments.volume)
            ? success()
            : invalidState("Speaker is unavailable");
    }
    if (command.name == CommandName::DisplaySetBrightness) {
        if (command.arguments.brightness < 0 || command.arguments.brightness > 100) {
            return invalidArgument("Brightness is outside the supported range");
        }
        return target.setBrightness(command.arguments.brightness)
            ? success()
            : invalidState("Display is unavailable");
    }
    if (command.name == CommandName::DisplayShowText) {
        if (!isValidBoundedText(command.arguments.text, 256)
            || command.arguments.durationMs < 100 || command.arguments.durationMs > 30000
            || command.arguments.priority < 0 || command.arguments.priority > 10) {
            return invalidArgument("Display text is outside the supported range");
        }
        return target.showText(
                   command.arguments.text,
                   command.arguments.durationMs,
                   command.arguments.priority
               )
            ? success()
            : invalidState("Display is unavailable");
    }
    if (command.name == CommandName::AvatarSetExpression) {
        if (!isSupportedExpression(command.arguments.expression)) {
            return invalidArgument("Expression is not supported");
        }
        return target.setExpression(command.arguments.expression)
            ? success()
            : invalidState("Avatar is unavailable");
    }
    if (command.name == CommandName::AvatarSetBlink) {
        return target.setBlink(command.arguments.enabled)
            ? success()
            : invalidState("Avatar is unavailable");
    }
    if (command.name == CommandName::LedSet) {
        const int ledCount = target.ledCount();
        if (ledCount <= 0) {
            return invalidState("LEDs are unavailable");
        }
        if (command.arguments.index < 0 || command.arguments.index >= ledCount
            || !isRgbValue(command.arguments.red)
            || !isRgbValue(command.arguments.green)
            || !isRgbValue(command.arguments.blue)) {
            return invalidArgument("LED value is outside the supported range");
        }
        return target.setLed(
                   command.arguments.index,
                   command.arguments.red,
                   command.arguments.green,
                   command.arguments.blue
               )
            ? success()
            : invalidState("LEDs are unavailable");
    }
    if (command.name == CommandName::LedSetAll) {
        if (target.ledCount() <= 0) {
            return invalidState("LEDs are unavailable");
        }
        if (!isRgbValue(command.arguments.red) || !isRgbValue(command.arguments.green)
            || !isRgbValue(command.arguments.blue)) {
            return invalidArgument("LED value is outside the supported range");
        }
        return target.setAllLeds(
                   command.arguments.red,
                   command.arguments.green,
                   command.arguments.blue
               )
            ? success()
            : invalidState("LEDs are unavailable");
    }
    if (command.name == CommandName::LedClear) {
        if (target.ledCount() <= 0) {
            return invalidState("LEDs are unavailable");
        }
        return target.clearLeds() ? success() : invalidState("LEDs are unavailable");
    }
    if (command.name == CommandName::HeadSetAngles) {
        const int speed = command.arguments.hasSpeed
            ? command.arguments.speed
            : K151MotionSafety::kDefaultSpeed;
        if (!K151MotionSafety::contains(
                command.arguments.yaw,
                command.arguments.pitch,
                speed
            )) {
            return invalidArgument("Head motion is outside the K151 safety profile");
        }
        return target.setHeadAngles(command.arguments.yaw, command.arguments.pitch, speed)
            ? success()
            : invalidState("Head motion is unavailable");
    }
    if (command.name == CommandName::HeadHome) {
        const int speed = command.arguments.hasSpeed
            ? command.arguments.speed
            : K151MotionSafety::kDefaultSpeed;
        if (!K151MotionSafety::containsSpeed(speed)) {
            return invalidArgument("Head motion is outside the K151 safety profile");
        }
        return target.homeHead(speed) ? success() : invalidState("Head motion is unavailable");
    }
    if (command.name == CommandName::HeadGetAngles) {
        HeadAngles angles;
        if (!target.getHeadAngles(angles)) {
            return invalidState("Head position is unavailable");
        }
        CommandExecutionResult result;
        result.ok = true;
        result.fields = {{"yaw", angles.yaw}, {"pitch", angles.pitch}};
        return result;
    }
    if (command.name == CommandName::SpeechCancel) {
        return target.cancelSpeech(command.turnId)
            ? success()
            : invalidState("Speech turn is not active");
    }
    if (command.name == CommandName::CameraCancel) {
        return target.cancelCapture(command.arguments.captureId) ? success() : invalidState("Capture is not active");
    }
    if (command.name == CommandName::CameraCapture) {
        if (!isValidUuid(command.arguments.captureId) || command.arguments.quality < 10
            || command.arguments.quality > 95 || command.arguments.captureTimeoutMs < 1
            || command.arguments.captureTimeoutMs > 120000) {
            return invalidArgument("Camera capture is outside the supported range");
        }
        switch (target.startCapture(
            command.arguments.captureId, command.arguments.quality, command.arguments.captureTimeoutMs
        )) {
            case CommandTargetResult::Success:
                return success();
            case CommandTargetResult::DeviceBusy:
                return deviceBusy("Camera is busy");
            case CommandTargetResult::InvalidState:
                return invalidState("Camera is unavailable");
        }
    }
    return invalidState("Command is not available");
}

}  // namespace stackchan::bridge_client
