#include <stackchan_bridge_client/protocol_guard.h>

#include <limits>
#include <utility>

#include <ArduinoJson.h>

namespace stackchan::bridge_client {
namespace {

constexpr std::uint32_t kInvalidMessageWindowMs = 10'000;
constexpr std::uint8_t kInvalidMessageLimit = 3;

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

bool isUtf8Continuation(unsigned char value)
{
    return value >= 0x80 && value <= 0xBF;
}

bool isValidText(const std::string& value, std::size_t maximumCodePoints)
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

bool parseRemoteErrorCode(const char* value, RemoteErrorCode& output)
{
    if (value == nullptr) {
        return false;
    }
    const std::string code(value);
    if (code == "UNSUPPORTED_VERSION") {
        output = RemoteErrorCode::UnsupportedVersion;
    } else if (code == "UNAUTHORIZED") {
        output = RemoteErrorCode::Unauthorized;
    } else if (code == "UNKNOWN_DEVICE") {
        output = RemoteErrorCode::UnknownDevice;
    } else if (code == "INVALID_MESSAGE") {
        output = RemoteErrorCode::InvalidMessage;
    } else if (code == "INVALID_ARGUMENT") {
        output = RemoteErrorCode::InvalidArgument;
    } else if (code == "INVALID_STATE") {
        output = RemoteErrorCode::InvalidState;
    } else if (code == "COMMAND_TIMEOUT") {
        output = RemoteErrorCode::CommandTimeout;
    } else if (code == "DEVICE_BUSY") {
        output = RemoteErrorCode::DeviceBusy;
    } else if (code == "AUDIO_DECODE_ERROR") {
        output = RemoteErrorCode::AudioDecodeError;
    } else if (code == "AUDIO_ENCODE_ERROR") {
        output = RemoteErrorCode::AudioEncodeError;
    } else if (code == "CAPTURE_FAILED") {
        output = RemoteErrorCode::CaptureFailed;
    } else if (code == "INTERNAL_ERROR") {
        output = RemoteErrorCode::InternalError;
    } else {
        return false;
    }
    return true;
}

bool readOptionalUuid(
    const ArduinoJson::JsonObjectConst& root,
    const char* name,
    std::string& output
)
{
    output.clear();
    const ArduinoJson::JsonVariantConst field = root[name];
    if (field.isUnbound()) {
        return true;
    }
    const char* value = field.as<const char*>();
    if (value == nullptr || !isValidUuid(value)) {
        return false;
    }
    output = value;
    return true;
}

const char* errorCode(PeerErrorCode code)
{
    switch (code) {
        case PeerErrorCode::InvalidMessage:
            return "INVALID_MESSAGE";
        case PeerErrorCode::InvalidArgument:
            return "INVALID_ARGUMENT";
        case PeerErrorCode::InvalidState:
            return "INVALID_STATE";
    }
    return nullptr;
}

}  // namespace

PeerErrorBuildError buildPeerErrorJson(
    const EnvelopeMetadata& envelope,
    PeerErrorCode code,
    const std::string& message,
    std::string& output
)
{
    output.clear();
    const char* codeValue = errorCode(code);
    if (!isValidUuid(envelope.messageId) || codeValue == nullptr
        || !isValidText(message, 160)
        || envelope.sentAtMs
            > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
        return PeerErrorBuildError::InvalidArgument;
    }

    ArduinoJson::JsonDocument document;
    document["v"] = 1;
    document["type"] = "error";
    document["message_id"] = envelope.messageId;
    document["sent_at_ms"] = envelope.sentAtMs;
    auto payload = document["payload"].to<ArduinoJson::JsonObject>();
    payload["code"] = codeValue;
    payload["message"] = message;
    serializeJson(document, output);
    if (output.size() > kMaxJsonBytes) {
        output.clear();
        return PeerErrorBuildError::MessageTooLarge;
    }
    return PeerErrorBuildError::None;
}

RemoteErrorParseError parseRemoteErrorJson(
    const std::string& input,
    RemoteErrorMessage& output
)
{
    output = RemoteErrorMessage{};
    if (input.size() > kMaxJsonBytes) {
        return RemoteErrorParseError::MessageTooLarge;
    }

    ArduinoJson::JsonDocument document;
    if (deserializeJson(
            document,
            input,
            ArduinoJson::DeserializationOption::NestingLimit(8)
        )
        || !document.is<ArduinoJson::JsonObjectConst>()) {
        return RemoteErrorParseError::InvalidMessage;
    }
    const ArduinoJson::JsonObjectConst root =
        document.as<ArduinoJson::JsonObjectConst>();
    const char* type = root["type"].as<const char*>();
    const char* messageId = root["message_id"].as<const char*>();
    const ArduinoJson::JsonVariantConst sentAtMs = root["sent_at_ms"];
    if (!root["v"].is<int>() || root["v"].as<int>() != 1 || type == nullptr
        || std::string(type) != "error" || messageId == nullptr
        || !isValidUuid(messageId) || !sentAtMs.is<std::uint64_t>()
        || sentAtMs.as<std::uint64_t>()
            > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())
        || !root["payload"].is<ArduinoJson::JsonObjectConst>()) {
        return RemoteErrorParseError::InvalidMessage;
    }

    const ArduinoJson::JsonObjectConst payload =
        root["payload"].as<ArduinoJson::JsonObjectConst>();
    const char* code = payload["code"].as<const char*>();
    const char* message = payload["message"].as<const char*>();
    RemoteErrorMessage parsed;
    if (!parseRemoteErrorCode(code, parsed.code) || message == nullptr
        || !isValidText(message, 160)
        || !readOptionalUuid(root, "turn_id", parsed.turnId)
        || !readOptionalUuid(root, "stream_id", parsed.streamId)) {
        return RemoteErrorParseError::InvalidArgument;
    }
    const ArduinoJson::JsonVariantConst detailField = payload["detail"];
    if (!detailField.isUnbound()) {
        const char* detail = detailField.as<const char*>();
        if (detail == nullptr || !isValidText(detail, 512)) {
            return RemoteErrorParseError::InvalidArgument;
        }
    }
    parsed.messageId = messageId;
    output = std::move(parsed);
    return RemoteErrorParseError::None;
}

bool InvalidMessageWindow::observe(std::uint32_t nowMs)
{
    if (count_ == 0 || nowMs - startedAtMs_ >= kInvalidMessageWindowMs) {
        startedAtMs_ = nowMs;
        count_ = 1;
        return false;
    }
    if (count_ < kInvalidMessageLimit) {
        ++count_;
    }
    return count_ >= kInvalidMessageLimit;
}

void InvalidMessageWindow::reset()
{
    startedAtMs_ = 0;
    count_ = 0;
}

}  // namespace stackchan::bridge_client
