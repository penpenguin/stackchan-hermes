#include <stackchan_bridge_client/audio_output.h>

#include <array>
#include <cstdint>
#include <limits>
#include <utility>

#include <ArduinoJson.h>

#include <stackchan_bridge_client/protocol.h>

namespace stackchan::bridge_client {
namespace {

using ArduinoJson::DeserializationOption::NestingLimit;
using ArduinoJson::JsonDocument;
using ArduinoJson::JsonObjectConst;

bool isValidUuid(const char* value)
{
    if (value == nullptr) {
        return false;
    }
    constexpr std::array<int, 4> kHyphens = {8, 13, 18, 23};
    for (int index = 0; index < 36; ++index) {
        bool isHyphen = false;
        for (const int hyphen : kHyphens) {
            if (index == hyphen) {
                isHyphen = true;
                break;
            }
        }
        const char character = value[index];
        if (isHyphen) {
            if (character != '-') {
                return false;
            }
        } else if (!((character >= '0' && character <= '9')
                     || (character >= 'a' && character <= 'f')
                     || (character >= 'A' && character <= 'F'))) {
            return false;
        }
    }
    return value[36] == '\0';
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

const char* audioBufferEventName(AudioBufferEventType type)
{
    switch (type) {
        case AudioBufferEventType::Underrun:
            return "audio.underrun";
        case AudioBufferEventType::Overflow:
            return "audio.overflow";
    }
    return nullptr;
}

bool hasValidEnvelope(const JsonObjectConst& root, const char* expectedType)
{
    const char* type = root["type"].as<const char*>();
    const char* messageId = root["message_id"].as<const char*>();
    const char* turnId = root["turn_id"].as<const char*>();
    const char* streamId = root["stream_id"].as<const char*>();
    return root["v"].is<int>() && root["v"].as<int>() == 1
        && type != nullptr && std::string(type) == expectedType && isValidUuid(messageId)
        && isValidUuid(turnId) && isValidUuid(streamId) && root["sent_at_ms"].is<std::uint64_t>()
        && root["sent_at_ms"].as<std::uint64_t>()
            <= static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())
        && root["payload"].is<JsonObjectConst>();
}

bool parseEndReason(const char* value, AudioOutputEndReason& output)
{
    if (value == nullptr) {
        return false;
    }
    const std::string reason(value);
    if (reason == "completed") {
        output = AudioOutputEndReason::Completed;
    } else if (reason == "cancelled") {
        output = AudioOutputEndReason::Cancelled;
    } else if (reason == "barge_in") {
        output = AudioOutputEndReason::BargeIn;
    } else if (reason == "tts_error") {
        output = AudioOutputEndReason::TtsError;
    } else if (reason == "device_error") {
        output = AudioOutputEndReason::DeviceError;
    } else if (reason == "disconnect") {
        output = AudioOutputEndReason::Disconnect;
    } else {
        return false;
    }
    return true;
}

bool isAllowedFrameDuration(int frameMs)
{
    return frameMs == 20 || frameMs == 40 || frameMs == 60;
}

bool isValidStream(const AudioOutputStream& stream)
{
    return !stream.turnId.empty() && !stream.streamId.empty() && stream.codec == "opus"
        && stream.sampleRate == 16000 && stream.channels == 1
        && isAllowedFrameDuration(stream.frameMs) && stream.expectedDurationMs >= 0
        && stream.expectedDurationMs <= 120000;
}

}  // namespace

AudioOutputBuffer::AudioOutputBuffer(int playbackPrerollMs)
    : playbackPrerollMs_(playbackPrerollMs)
{
}

AudioBufferEventBuildError buildAudioBufferEventJson(
    const EnvelopeMetadata& envelope,
    const std::string& deviceId,
    const std::string& streamId,
    AudioBufferEventType type,
    std::uint32_t droppedPackets,
    std::string& output
)
{
    output.clear();
    const char* eventName = audioBufferEventName(type);
    if (!isValidUuid(envelope.messageId.c_str()) || !isValidDeviceId(deviceId)
        || !isValidUuid(streamId.c_str()) || eventName == nullptr || droppedPackets == 0
        || droppedPackets > 65'535
        || envelope.sentAtMs
            > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
        return AudioBufferEventBuildError::InvalidArgument;
    }
    JsonDocument document;
    document["v"] = 1;
    document["type"] = "event";
    document["message_id"] = envelope.messageId;
    document["sent_at_ms"] = envelope.sentAtMs;
    document["device_id"] = deviceId;
    auto payload = document["payload"].to<ArduinoJson::JsonObject>();
    payload["name"] = eventName;
    auto data = payload["data"].to<ArduinoJson::JsonObject>();
    data["stream_id"] = streamId;
    data["dropped_packets"] = droppedPackets;
    serializeJson(document, output);
    if (output.size() > kMaxJsonBytes) {
        output.clear();
        return AudioBufferEventBuildError::MessageTooLarge;
    }
    return AudioBufferEventBuildError::None;
}

AudioOutputParseError parseAudioOutputControlJson(
    const std::string& input,
    AudioOutputControl& output
)
{
    if (input.size() > kMaxJsonBytes) {
        return AudioOutputParseError::MessageTooLarge;
    }
    JsonDocument document;
    if (deserializeJson(document, input, NestingLimit(8)) || !document.is<JsonObjectConst>()) {
        return AudioOutputParseError::InvalidMessage;
    }
    const JsonObjectConst root = document.as<JsonObjectConst>();
    const char* type = root["type"].as<const char*>();
    if (type == nullptr) {
        return AudioOutputParseError::InvalidMessage;
    }

    AudioOutputControl parsed;
    if (std::string(type) == "audio.output.start") {
        if (!hasValidEnvelope(root, "audio.output.start")) {
            return AudioOutputParseError::InvalidMessage;
        }
        parsed.messageId = root["message_id"].as<const char*>();
        const JsonObjectConst payload = root["payload"].as<JsonObjectConst>();
        const char* codec = payload["codec"].as<const char*>();
        if (codec == nullptr || !payload["sample_rate"].is<int>()
            || !payload["channels"].is<int>() || !payload["frame_ms"].is<int>()
            || !payload["expected_duration_ms"].is<int>()) {
            return AudioOutputParseError::InvalidMessage;
        }
        parsed.type = AudioOutputControlType::Start;
        parsed.stream.turnId = root["turn_id"].as<const char*>();
        parsed.stream.streamId = root["stream_id"].as<const char*>();
        parsed.stream.codec = codec;
        parsed.stream.sampleRate = payload["sample_rate"].as<int>();
        parsed.stream.channels = payload["channels"].as<int>();
        parsed.stream.frameMs = payload["frame_ms"].as<int>();
        parsed.stream.expectedDurationMs = payload["expected_duration_ms"].as<int>();
        if (!isValidStream(parsed.stream)) {
            return AudioOutputParseError::InvalidArgument;
        }
    } else if (std::string(type) == "audio.output.end") {
        if (!hasValidEnvelope(root, "audio.output.end")) {
            return AudioOutputParseError::InvalidMessage;
        }
        parsed.messageId = root["message_id"].as<const char*>();
        const JsonObjectConst payload = root["payload"].as<JsonObjectConst>();
        if (!parseEndReason(payload["reason"].as<const char*>(), parsed.reason)) {
            return AudioOutputParseError::InvalidArgument;
        }
        parsed.type = AudioOutputControlType::End;
        parsed.stream.turnId = root["turn_id"].as<const char*>();
        parsed.stream.streamId = root["stream_id"].as<const char*>();
    } else {
        return AudioOutputParseError::InvalidMessage;
    }

    output = std::move(parsed);
    return AudioOutputParseError::None;
}

AudioOutputError AudioOutputBuffer::start(const AudioOutputStream& stream)
{
    if (!isValidStream(stream) || playbackPrerollMs_ < 0
        || static_cast<std::size_t>(playbackPrerollMs_)
            > kAudioOutputQueuePackets * static_cast<std::size_t>(stream.frameMs)) {
        return AudioOutputError::InvalidArgument;
    }
    if (contextActive_) {
        return AudioOutputError::InvalidState;
    }
    stream_ = stream;
    queue_.clear();
    contextActive_ = true;
    open_ = true;
    ended_ = false;
    prerollSatisfied_ = false;
    underflowActive_ = false;
    return AudioOutputError::None;
}

AudioOutputError AudioOutputBuffer::push(const std::uint8_t* data, std::size_t size)
{
    if (!open_) {
        ++droppedPackets_;
        return AudioOutputError::InvalidState;
    }
    if (data == nullptr || size == 0) {
        ++droppedPackets_;
        return AudioOutputError::InvalidArgument;
    }
    if (size > kMaxAudioPacketBytes) {
        ++droppedPackets_;
        return AudioOutputError::PacketTooLarge;
    }
    if (queue_.size() >= kAudioOutputQueuePackets) {
        ++droppedPackets_;
        return AudioOutputError::QueueOverflow;
    }
    queue_.emplace_back(data, data + size);
    underflowActive_ = false;
    if (queue_.size() * static_cast<std::size_t>(stream_.frameMs)
        >= static_cast<std::size_t>(playbackPrerollMs_)) {
        prerollSatisfied_ = true;
    }
    return AudioOutputError::None;
}

AudioOutputError AudioOutputBuffer::finish(
    const std::string& turnId,
    const std::string& streamId,
    AudioOutputEndReason reason
)
{
    if (!open_) {
        return AudioOutputError::InvalidState;
    }
    if (stream_.turnId != turnId || stream_.streamId != streamId) {
        return AudioOutputError::WrongStream;
    }
    open_ = false;
    ended_ = true;
    if (reason != AudioOutputEndReason::Completed) {
        clearContext();
    }
    return AudioOutputError::None;
}

AudioOutputError AudioOutputBuffer::cancelTurn(const std::string& turnId)
{
    if (!contextActive_) {
        return AudioOutputError::InvalidState;
    }
    if (stream_.turnId != turnId) {
        return AudioOutputError::WrongStream;
    }
    clearContext();
    return AudioOutputError::None;
}

AudioOutputError AudioOutputBuffer::acknowledgePlayback(
    const std::string& turnId,
    const std::string& streamId
)
{
    if (!contextActive_) {
        return AudioOutputError::InvalidState;
    }
    if (stream_.turnId != turnId || stream_.streamId != streamId) {
        return AudioOutputError::WrongStream;
    }
    if (!deliveryComplete()) {
        return AudioOutputError::InvalidState;
    }
    clearContext();
    return AudioOutputError::None;
}

bool AudioOutputBuffer::pop(std::vector<std::uint8_t>& output)
{
    output.clear();
    if (detectUnderflow()) {
        return false;
    }
    if (!readyForPlayback() || queue_.empty()) {
        return false;
    }
    output = std::move(queue_.front());
    queue_.pop_front();
    return true;
}

bool AudioOutputBuffer::deliverNext(const std::function<bool(
    const AudioOutputStream& stream,
    const std::vector<std::uint8_t>& packet
)>& consumer)
{
    if (!consumer || detectUnderflow() || !readyForPlayback() || queue_.empty()) {
        return false;
    }
    if (!consumer(stream_, queue_.front())) {
        return false;
    }
    queue_.pop_front();
    return true;
}

bool AudioOutputBuffer::detectUnderflow()
{
    if (!contextActive_ || !open_ || !prerollSatisfied_ || !queue_.empty()) {
        return false;
    }
    if (!underflowActive_) {
        ++underflowCount_;
        underflowActive_ = true;
    }
    return true;
}

void AudioOutputBuffer::reset()
{
    clearContext();
}

bool AudioOutputBuffer::isOpen() const
{
    return open_;
}

bool AudioOutputBuffer::deliveryComplete() const
{
    return contextActive_ && ended_ && queue_.empty();
}

bool AudioOutputBuffer::readyForPlayback() const
{
    if (!contextActive_ || queue_.empty()) {
        return false;
    }
    return ended_ || prerollSatisfied_;
}

std::size_t AudioOutputBuffer::queuedPackets() const
{
    return queue_.size();
}

std::size_t AudioOutputBuffer::droppedPackets() const
{
    return droppedPackets_;
}

std::size_t AudioOutputBuffer::underflowCount() const
{
    return underflowCount_;
}

const std::string& AudioOutputBuffer::turnId() const
{
    return stream_.turnId;
}

const std::string& AudioOutputBuffer::streamId() const
{
    return stream_.streamId;
}

void AudioOutputBuffer::clearContext()
{
    queue_.clear();
    stream_ = {};
    contextActive_ = false;
    open_ = false;
    ended_ = false;
    prerollSatisfied_ = false;
    underflowActive_ = false;
}

}  // namespace stackchan::bridge_client
