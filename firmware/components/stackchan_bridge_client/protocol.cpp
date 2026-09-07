#include <stackchan_bridge_client/protocol.h>

#include <limits>

#include <ArduinoJson.h>

namespace stackchan::bridge_client {
namespace {

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
    for (char character : value) {
        if (!isAsciiAlphaNumeric(character) && character != '.' && character != '_'
            && character != '-') {
            return false;
        }
    }
    return true;
}

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

}  // namespace

ProtocolError buildHelloJson(
    const EnvelopeMetadata& envelope,
    const HelloPayload& hello,
    std::string& output
)
{
    output.clear();
    const bool validFrameDuration = hello.audio.frameMs == 20 || hello.audio.frameMs == 40
        || hello.audio.frameMs == 60;
    if (!isValidUuid(envelope.messageId)
        || envelope.sentAtMs
            > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())
        || !isValidDeviceId(hello.deviceId)
        || !isValidBoundedText(hello.deviceName, 64)
        || !isValidBoundedText(hello.firmwareVersion, 32)
        || !isValidBoundedText(hello.hardwareModel, 64)
        || hello.capabilities.ledCount > 256
        || hello.audio.codec != "opus" || hello.audio.sampleRate != 16000
        || hello.audio.channels != 1 || !validFrameDuration) {
        return ProtocolError::InvalidArgument;
    }

    JsonDocument document;
    document["v"]          = 1;
    document["type"]       = "hello";
    document["message_id"] = envelope.messageId;
    document["sent_at_ms"] = envelope.sentAtMs;

    JsonObject payload        = document["payload"].to<JsonObject>();
    payload["device_id"]      = hello.deviceId;
    payload["device_name"]    = hello.deviceName;
    payload["firmware_version"] = hello.firmwareVersion;
    payload["hardware_model"]   = hello.hardwareModel;

    JsonArray protocolVersions = payload["protocol_versions"].to<JsonArray>();
    protocolVersions.add(1);

    JsonObject capabilities       = payload["capabilities"].to<JsonObject>();
    capabilities["microphone"]    = hello.capabilities.microphone;
    capabilities["speaker"]       = hello.capabilities.speaker;
    capabilities["camera"]        = hello.capabilities.camera;
    capabilities["touch"]         = hello.capabilities.touch;
    capabilities["head"]          = hello.capabilities.head;
    capabilities["display"]       = hello.capabilities.display;
    capabilities["avatar"]        = hello.capabilities.avatar;
    capabilities["led_count"]     = hello.capabilities.ledCount;

    JsonObject audio      = payload["audio"].to<JsonObject>();
    audio["codec"]        = hello.audio.codec;
    audio["sample_rate"]  = hello.audio.sampleRate;
    audio["channels"]     = hello.audio.channels;
    audio["frame_ms"]     = hello.audio.frameMs;

    serializeJson(document, output);
    if (output.size() > kMaxJsonBytes) {
        output.clear();
        return ProtocolError::MessageTooLarge;
    }
    return ProtocolError::None;
}

ProtocolError parseHelloAckJson(const std::string& input, HelloAck& output)
{
    output = HelloAck{};
    if (input.size() > kMaxJsonBytes) {
        return ProtocolError::MessageTooLarge;
    }

    JsonDocument document;
    if (deserializeJson(document, input, DeserializationOption::NestingLimit(8))) {
        return ProtocolError::InvalidArgument;
    }

    JsonVariantConst protocolVersion = document["v"];
    JsonVariantConst sentAtMs        = document["sent_at_ms"];
    const char* messageType = document["type"].as<const char*>();
    const char* messageId   = document["message_id"].as<const char*>();
    if (!protocolVersion.is<int>() || protocolVersion.as<int>() != 1 || messageType == nullptr
        || std::string(messageType) != "hello_ack" || messageId == nullptr
        || !isValidUuid(messageId) || !sentAtMs.is<std::uint64_t>()
        || sentAtMs.as<std::uint64_t>()
            > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
        return ProtocolError::InvalidArgument;
    }

    JsonVariantConst payloadValue = document["payload"];
    if (!payloadValue.is<JsonObjectConst>()) {
        return ProtocolError::InvalidArgument;
    }
    JsonObjectConst payload = payloadValue.as<JsonObjectConst>();
    const char* connectionId = payload["connection_id"].as<const char*>();
    const char* serverVersion = payload["server_version"].as<const char*>();
    JsonVariantConst heartbeatValue = payload["heartbeat_interval_ms"];
    JsonVariantConst selectedVersionValue = payload["selected_protocol_version"];
    JsonVariantConst commandTimeoutValue = payload["max_command_timeout_ms"];
    if (!heartbeatValue.is<std::uint32_t>() || !selectedVersionValue.is<std::uint8_t>()
        || !commandTimeoutValue.is<std::uint32_t>()) {
        return ProtocolError::InvalidArgument;
    }
    const std::uint32_t heartbeatIntervalMs = heartbeatValue.as<std::uint32_t>();
    const std::uint8_t selectedProtocolVersion = selectedVersionValue.as<std::uint8_t>();
    const std::uint32_t maxCommandTimeoutMs = commandTimeoutValue.as<std::uint32_t>();
    if (connectionId == nullptr || !isValidUuid(connectionId) || serverVersion == nullptr
        || !isValidBoundedText(serverVersion, 32) || heartbeatIntervalMs < 1000
        || heartbeatIntervalMs > 60000
        || selectedProtocolVersion != 1 || maxCommandTimeoutMs < 100
        || maxCommandTimeoutMs > 30000) {
        return ProtocolError::InvalidArgument;
    }

    HelloAck parsed;
    parsed.connectionId            = connectionId;
    parsed.selectedProtocolVersion = selectedProtocolVersion;
    parsed.heartbeatIntervalMs     = heartbeatIntervalMs;
    parsed.maxCommandTimeoutMs     = maxCommandTimeoutMs;
    parsed.serverVersion           = serverVersion;
    output                         = std::move(parsed);
    return ProtocolError::None;
}

}  // namespace stackchan::bridge_client
