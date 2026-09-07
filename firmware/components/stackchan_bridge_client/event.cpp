#include <stackchan_bridge_client/event.h>

#include <cstdint>
#include <limits>

#include <ArduinoJson.h>

namespace stackchan::bridge_client {
namespace {

bool isHexDigit(char value)
{
    return (value >= '0' && value <= '9') || (value >= 'A' && value <= 'F')
        || (value >= 'a' && value <= 'f');
}

bool isValidUuid(const std::string& value)
{
    if (value.size() != 36) {
        return false;
    }
    for (std::size_t index = 0; index < value.size(); ++index) {
        const bool separator = index == 8 || index == 13 || index == 18 || index == 23;
        if ((separator && value[index] != '-') || (!separator && !isHexDigit(value[index]))) {
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

bool isValidDeviceId(const std::string& value)
{
    if (value.empty() || value.size() > 64 || !isAsciiAlphaNumeric(value.front())) {
        return false;
    }
    for (const char character : value) {
        if (!isAsciiAlphaNumeric(character) && character != '.' && character != '_'
            && character != '-') {
            return false;
        }
    }
    return true;
}

bool isUtf8Continuation(unsigned char value)
{
    return value >= 0x80 && value <= 0xBF;
}

bool isValidMessage(const std::string& value)
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
        if (++codePoints > 160) {
            return false;
        }
    }
    return true;
}

const char* eventName(DeviceFaultEventType type)
{
    switch (type) {
        case DeviceFaultEventType::DeviceError:
            return "device.error";
        case DeviceFaultEventType::ServoError:
            return "servo.error";
    }
    return nullptr;
}

const char* errorCode(DeviceFaultCode code)
{
    switch (code) {
        case DeviceFaultCode::AudioDecodeError:
            return "AUDIO_DECODE_ERROR";
        case DeviceFaultCode::AudioEncodeError:
            return "AUDIO_ENCODE_ERROR";
        case DeviceFaultCode::InternalError:
            return "INTERNAL_ERROR";
    }
    return nullptr;
}

}  // namespace

EventBuildError buildDeviceFaultEventJson(
    const EnvelopeMetadata& envelope,
    const std::string& deviceId,
    DeviceFaultEventType type,
    DeviceFaultCode code,
    const std::string& message,
    std::string& output
)
{
    output.clear();
    const char* name = eventName(type);
    const char* codeValue = errorCode(code);
    if (!isValidUuid(envelope.messageId) || !isValidDeviceId(deviceId)
        || !isValidMessage(message) || name == nullptr || codeValue == nullptr
        || envelope.sentAtMs
            > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
        return EventBuildError::InvalidArgument;
    }
    ArduinoJson::JsonDocument document;
    document["v"] = 1;
    document["type"] = "event";
    document["message_id"] = envelope.messageId;
    document["sent_at_ms"] = envelope.sentAtMs;
    document["device_id"] = deviceId;
    auto payload = document["payload"].to<ArduinoJson::JsonObject>();
    payload["name"] = name;
    auto data = payload["data"].to<ArduinoJson::JsonObject>();
    data["code"] = codeValue;
    data["message"] = message;
    serializeJson(document, output);
    if (output.size() > kMaxJsonBytes) {
        output.clear();
        return EventBuildError::MessageTooLarge;
    }
    return EventBuildError::None;
}

EventBuildError buildTouchTapEventJson(
    const EnvelopeMetadata& envelope,
    const std::string& deviceId,
    int x,
    int y,
    std::string& output
)
{
    output.clear();
    if (!isValidUuid(envelope.messageId) || !isValidDeviceId(deviceId)
        || x < 0 || x > 319 || y < 0 || y > 239
        || envelope.sentAtMs
            > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
        return EventBuildError::InvalidArgument;
    }
    ArduinoJson::JsonDocument document;
    document["v"] = 1;
    document["type"] = "event";
    document["message_id"] = envelope.messageId;
    document["sent_at_ms"] = envelope.sentAtMs;
    document["device_id"] = deviceId;
    auto payload = document["payload"].to<ArduinoJson::JsonObject>();
    payload["name"] = "touch.tap";
    auto data = payload["data"].to<ArduinoJson::JsonObject>();
    data["x"] = x;
    data["y"] = y;
    serializeJson(document, output);
    if (output.size() > kMaxJsonBytes) {
        output.clear();
        return EventBuildError::MessageTooLarge;
    }
    return EventBuildError::None;
}

}  // namespace stackchan::bridge_client
