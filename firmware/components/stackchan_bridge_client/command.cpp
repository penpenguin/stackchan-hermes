#include <stackchan_bridge_client/command.h>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <type_traits>

#include <ArduinoJson.h>

#include <stackchan_bridge_client/protocol.h>

namespace stackchan::bridge_client {
namespace {

bool isHexDigit(char value)
{
    return (value >= '0' && value <= '9') || (value >= 'A' && value <= 'F')
        || (value >= 'a' && value <= 'f');
}

bool isValidUuid(const char* value)
{
    if (value == nullptr) {
        return false;
    }
    const std::string uuid = value;
    if (uuid.size() != 36) {
        return false;
    }
    for (std::size_t index = 0; index < uuid.size(); ++index) {
        const bool separator = index == 8 || index == 13 || index == 18 || index == 23;
        if ((separator && uuid[index] != '-') || (!separator && !isHexDigit(uuid[index]))) {
            return false;
        }
    }
    return true;
}

bool isAsciiAlphaNumeric(char value)
{
    return (value >= 'A' && value <= 'Z') || (value >= 'a' && value <= 'z')
        || (value >= '0' && value <= '9');
}

bool isValidDeviceId(const char* value)
{
    if (value == nullptr) {
        return false;
    }
    const std::string deviceId = value;
    if (deviceId.empty() || deviceId.size() > 64 || !isAsciiAlphaNumeric(deviceId.front())) {
        return false;
    }
    for (const char character : deviceId) {
        if (!isAsciiAlphaNumeric(character) && character != '.' && character != '_'
            && character != '-') {
            return false;
        }
    }
    return true;
}

bool hasKey(JsonObjectConst object, const char* key)
{
    for (JsonPairConst entry : object) {
        if (std::strcmp(entry.key().c_str(), key) == 0) {
            return true;
        }
    }
    return false;
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
        std::size_t sequenceLength = 0;
        if (first <= 0x7F) {
            if (first < 0x20 || first == 0x7F) {
                return false;
            }
            sequenceLength = 1;
        } else if (first >= 0xC2 && first <= 0xDF) {
            sequenceLength = 2;
        } else if (first >= 0xE0 && first <= 0xEF) {
            sequenceLength = 3;
        } else if (first >= 0xF0 && first <= 0xF4) {
            sequenceLength = 4;
        } else {
            return false;
        }

        if (index + sequenceLength > value.size()) {
            return false;
        }
        for (std::size_t offset = 1; offset < sequenceLength; ++offset) {
            if (!isUtf8Continuation(static_cast<unsigned char>(value[index + offset]))) {
                return false;
            }
        }
        if (sequenceLength == 3) {
            const auto second = static_cast<unsigned char>(value[index + 1]);
            if ((first == 0xE0 && second < 0xA0) || (first == 0xED && second > 0x9F)) {
                return false;
            }
        }
        if (sequenceLength == 4) {
            const auto second = static_cast<unsigned char>(value[index + 1]);
            if ((first == 0xF0 && second < 0x90) || (first == 0xF4 && second > 0x8F)) {
                return false;
            }
        }

        index += sequenceLength;
        ++codePoints;
        if (codePoints > maximumCodePoints) {
            return false;
        }
    }
    return true;
}

bool isValidExpression(const std::string& value)
{
    return value == "idle" || value == "happy" || value == "thinking" || value == "sad"
        || value == "surprised" || value == "embarrassed";
}

bool readProtocolAngle(JsonVariantConst value, double& output)
{
    if (value.is<bool>() || (!value.is<std::int64_t>() && !value.is<double>())) {
        return false;
    }
    const double parsed = value.as<double>();
    if (!std::isfinite(parsed) || parsed < -90.0 || parsed > 90.0) {
        return false;
    }
    output = parsed;
    return true;
}

bool readByte(JsonVariantConst value, int& output)
{
    if (!value.is<int>() || value.as<int>() < 0 || value.as<int>() > 255) {
        return false;
    }
    output = value.as<int>();
    return true;
}

bool isResultFieldName(const std::string& value)
{
    if (value.empty() || value.size() > 64
        || !((value.front() >= 'A' && value.front() <= 'Z')
            || (value.front() >= 'a' && value.front() <= 'z') || value.front() == '_')) {
        return false;
    }
    for (char character : value) {
        if (!((character >= 'A' && character <= 'Z')
            || (character >= 'a' && character <= 'z')
            || (character >= '0' && character <= '9') || character == '_')) {
            return false;
        }
    }
    return true;
}

const char* commandErrorCodeName(CommandErrorCode code)
{
    switch (code) {
        case CommandErrorCode::InvalidArgument:
            return "INVALID_ARGUMENT";
        case CommandErrorCode::InvalidState:
            return "INVALID_STATE";
        case CommandErrorCode::DeviceBusy:
            return "DEVICE_BUSY";
        case CommandErrorCode::None:
            return nullptr;
    }
    return nullptr;
}

}  // namespace

CommandParseError parseCommandJson(const std::string& input, Command& output)
{
    output = Command{};
    if (input.size() > kMaxJsonBytes) {
        return CommandParseError::MessageTooLarge;
    }

    JsonDocument document;
    if (deserializeJson(document, input, DeserializationOption::NestingLimit(8))) {
        return CommandParseError::InvalidMessage;
    }
    if (!document.is<JsonObjectConst>()) {
        return CommandParseError::InvalidMessage;
    }

    const JsonObjectConst root = document.as<JsonObjectConst>();
    JsonVariantConst version = document["v"];
    JsonVariantConst sentAt = document["sent_at_ms"];
    const char* type = document["type"].as<const char*>();
    const char* messageId = document["message_id"].as<const char*>();
    const char* requestId = document["request_id"].as<const char*>();
    const char* turnId = document["turn_id"].as<const char*>();
    const char* streamId = document["stream_id"].as<const char*>();
    const char* deviceId = document["device_id"].as<const char*>();
    const bool hasTurnId = hasKey(root, "turn_id");
    const bool hasStreamId = hasKey(root, "stream_id");
    const bool hasDeviceId = hasKey(root, "device_id");
    JsonVariantConst payloadValue = document["payload"];
    if (!version.is<int>() || version.as<int>() != 1 || type == nullptr
        || std::string(type) != "command" || !isValidUuid(messageId) || !isValidUuid(requestId)
        || (hasTurnId && !isValidUuid(turnId)) || (hasStreamId && !isValidUuid(streamId))
        || (hasDeviceId && !isValidDeviceId(deviceId)) || !sentAt.is<std::uint64_t>()
        || sentAt.as<std::uint64_t>()
            > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())
        || !payloadValue.is<JsonObjectConst>()) {
        return CommandParseError::InvalidMessage;
    }

    JsonObjectConst payload = payloadValue.as<JsonObjectConst>();
    const char* name = payload["name"].as<const char*>();
    JsonVariantConst argumentsValue = payload["args"];
    if (name == nullptr || !argumentsValue.is<JsonObjectConst>() || payload.size() != 2) {
        return CommandParseError::InvalidArgument;
    }

    JsonObjectConst arguments = argumentsValue.as<JsonObjectConst>();
    Command parsed;
    if (std::string(name) == "device.get_status") {
        if (arguments.size() != 0) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::DeviceGetStatus;
    } else if (std::string(name) == "device.get_info") {
        if (arguments.size() != 0) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::DeviceGetInfo;
    } else if (std::string(name) == "audio.set_volume") {
        JsonVariantConst volume = arguments["volume"];
        if (arguments.size() != 1 || !volume.is<int>() || volume.as<int>() < 0
            || volume.as<int>() > 100) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::AudioSetVolume;
        parsed.arguments.volume = volume.as<int>();
    } else if (std::string(name) == "display.set_brightness") {
        JsonVariantConst brightness = arguments["brightness"];
        if (arguments.size() != 1 || !brightness.is<int>() || brightness.as<int>() < 0
            || brightness.as<int>() > 100) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::DisplaySetBrightness;
        parsed.arguments.brightness = brightness.as<int>();
    } else if (std::string(name) == "display.show_text") {
        const char* text = arguments["text"].as<const char*>();
        JsonVariantConst duration = arguments["duration_ms"];
        JsonVariantConst priority = arguments["priority"];
        if (arguments.size() != 3 || text == nullptr || !isValidBoundedText(text, 256)
            || !duration.is<int>() || duration.as<int>() < 100 || duration.as<int>() > 30000
            || !priority.is<int>() || priority.as<int>() < 0 || priority.as<int>() > 10) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::DisplayShowText;
        parsed.arguments.text = text;
        parsed.arguments.durationMs = duration.as<int>();
        parsed.arguments.priority = priority.as<int>();
    } else if (std::string(name) == "avatar.set_expression") {
        const char* expression = arguments["expression"].as<const char*>();
        if (arguments.size() != 1 || expression == nullptr || !isValidExpression(expression)) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::AvatarSetExpression;
        parsed.arguments.expression = expression;
    } else if (std::string(name) == "avatar.set_blink") {
        JsonVariantConst enabled = arguments["enabled"];
        if (arguments.size() != 1 || !enabled.is<bool>()) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::AvatarSetBlink;
        parsed.arguments.enabled = enabled.as<bool>();
    } else if (std::string(name) == "head.set_angles") {
        JsonVariantConst yaw = arguments["yaw"];
        JsonVariantConst pitch = arguments["pitch"];
        JsonVariantConst speed = arguments["speed"];
        if ((arguments.size() != 2 && arguments.size() != 3)
            || !readProtocolAngle(yaw, parsed.arguments.yaw)
            || !readProtocolAngle(pitch, parsed.arguments.pitch)) {
            return CommandParseError::InvalidArgument;
        }
        if (!speed.isNull()) {
            if (arguments.size() != 3 || !speed.is<int>() || speed.as<int>() < 1
                || speed.as<int>() > 100) {
                return CommandParseError::InvalidArgument;
            }
            parsed.arguments.hasSpeed = true;
            parsed.arguments.speed = speed.as<int>();
        } else if (arguments.size() != 2) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::HeadSetAngles;
    } else if (std::string(name) == "head.get_angles") {
        if (arguments.size() != 0) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::HeadGetAngles;
    } else if (std::string(name) == "head.home") {
        JsonVariantConst speed = arguments["speed"];
        if (arguments.size() > 1 || (!speed.isNull()
            && (!speed.is<int>() || speed.as<int>() < 1 || speed.as<int>() > 100))) {
            return CommandParseError::InvalidArgument;
        }
        if (!speed.isNull()) {
            parsed.arguments.hasSpeed = true;
            parsed.arguments.speed = speed.as<int>();
        }
        parsed.name = CommandName::HeadHome;
    } else if (std::string(name) == "led.set") {
        if (arguments.size() != 4 || !readByte(arguments["index"], parsed.arguments.index)
            || !readByte(arguments["r"], parsed.arguments.red)
            || !readByte(arguments["g"], parsed.arguments.green)
            || !readByte(arguments["b"], parsed.arguments.blue)) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::LedSet;
    } else if (std::string(name) == "led.set_all") {
        if (arguments.size() != 3 || !readByte(arguments["r"], parsed.arguments.red)
            || !readByte(arguments["g"], parsed.arguments.green)
            || !readByte(arguments["b"], parsed.arguments.blue)) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::LedSetAll;
    } else if (std::string(name) == "led.clear") {
        if (arguments.size() != 0) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::LedClear;
    } else if (std::string(name) == "camera.capture") {
        const char* captureId = arguments["capture_id"].as<const char*>();
        JsonVariantConst quality = arguments["quality"];
        if (arguments.size() != 3 || !arguments["timeout_ms"].is<int>()
            || arguments["timeout_ms"].as<int>() < 1 || arguments["timeout_ms"].as<int>() > 120000
            || !isValidUuid(captureId) || !quality.is<int>()
            || quality.as<int>() < 10 || quality.as<int>() > 95) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::CameraCapture;
        parsed.arguments.captureId = captureId;
        parsed.arguments.quality = quality.as<int>();
        parsed.arguments.captureTimeoutMs = arguments["timeout_ms"].as<int>();
    } else if (std::string(name) == "camera.cancel") {
        const char* captureId = arguments["capture_id"].as<const char*>();
        if (arguments.size() != 1 || !isValidUuid(captureId)) { return CommandParseError::InvalidArgument; }
        parsed.name = CommandName::CameraCancel;
        parsed.arguments.captureId = captureId;
    } else if (std::string(name) == "speech.cancel") {
        if (arguments.size() != 0 || turnId == nullptr) {
            return CommandParseError::InvalidArgument;
        }
        parsed.name = CommandName::SpeechCancel;
    } else {
        return CommandParseError::InvalidArgument;
    }

    parsed.messageId = messageId;
    parsed.requestId = requestId;
    if (turnId != nullptr) {
        parsed.turnId = turnId;
    }
    if (streamId != nullptr) {
        parsed.streamId = streamId;
    }
    if (deviceId != nullptr) {
        parsed.deviceId = deviceId;
    }
    parsed.sentAtMs = sentAt.as<std::uint64_t>();
    output = std::move(parsed);
    return CommandParseError::None;
}

bool isSameCommandRequest(const Command& left, const Command& right)
{
    return left.name == right.name && left.requestId == right.requestId
        && left.turnId == right.turnId && left.streamId == right.streamId
        && left.deviceId == right.deviceId
        && left.arguments.volume == right.arguments.volume
        && left.arguments.brightness == right.arguments.brightness
        && left.arguments.text == right.arguments.text
        && left.arguments.durationMs == right.arguments.durationMs
        && left.arguments.priority == right.arguments.priority
        && left.arguments.expression == right.arguments.expression
        && left.arguments.enabled == right.arguments.enabled
        && left.arguments.yaw == right.arguments.yaw
        && left.arguments.pitch == right.arguments.pitch
        && left.arguments.hasSpeed == right.arguments.hasSpeed
        && left.arguments.speed == right.arguments.speed
        && left.arguments.index == right.arguments.index
        && left.arguments.red == right.arguments.red
        && left.arguments.green == right.arguments.green
        && left.arguments.blue == right.arguments.blue
        && left.arguments.captureId == right.arguments.captureId
        && left.arguments.quality == right.arguments.quality
        && left.arguments.captureTimeoutMs == right.arguments.captureTimeoutMs;
}

CommandResultBuildError buildCommandResultJson(
    const EnvelopeMetadata& envelope,
    const std::string& requestId,
    const CommandExecutionResult& result,
    std::string& output
)
{
    output.clear();
    if (!isValidUuid(envelope.messageId.c_str()) || !isValidUuid(requestId.c_str())
        || envelope.sentAtMs
            > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
        return CommandResultBuildError::InvalidArgument;
    }

    JsonDocument document;
    document["v"] = 1;
    document["type"] = "command_result";
    document["message_id"] = envelope.messageId;
    document["request_id"] = requestId;
    document["sent_at_ms"] = envelope.sentAtMs;
    JsonObject payload = document["payload"].to<JsonObject>();
    payload["ok"] = result.ok;
    if (result.ok) {
        if (result.errorCode != CommandErrorCode::None || !result.errorMessage.empty()
            || result.fields.size() > 32) {
            output.clear();
            return CommandResultBuildError::InvalidArgument;
        }
        JsonObject resultObject = payload["result"].to<JsonObject>();
        std::vector<std::string> fieldNames;
        fieldNames.reserve(result.fields.size());
        for (const auto& field : result.fields) {
            if (!isResultFieldName(field.name)
                || std::find(fieldNames.begin(), fieldNames.end(), field.name) != fieldNames.end()) {
                output.clear();
                return CommandResultBuildError::InvalidArgument;
            }
            fieldNames.push_back(field.name);
            bool valid = true;
            std::visit(
                [&](const auto& value) {
                    using Value = std::decay_t<decltype(value)>;
                    if constexpr (std::is_same_v<Value, std::string>) {
                        valid = isValidBoundedText(value, 512);
                    } else if constexpr (std::is_same_v<Value, double>) {
                        valid = std::isfinite(value);
                    }
                    if (valid) {
                        resultObject[field.name] = value;
                    }
                },
                field.value
            );
            if (!valid) {
                output.clear();
                return CommandResultBuildError::InvalidArgument;
            }
        }
    } else {
        const char* errorCode = commandErrorCodeName(result.errorCode);
        if (errorCode == nullptr || !isValidBoundedText(result.errorMessage, 160)) {
            output.clear();
            return CommandResultBuildError::InvalidArgument;
        }
        JsonObject error = payload["error"].to<JsonObject>();
        error["code"] = errorCode;
        error["message"] = result.errorMessage;
    }

    serializeJson(document, output);
    if (output.size() > kMaxJsonBytes) {
        output.clear();
        return CommandResultBuildError::MessageTooLarge;
    }
    return CommandResultBuildError::None;
}

}  // namespace stackchan::bridge_client
