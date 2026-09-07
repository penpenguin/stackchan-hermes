#include <stackchan_bridge_client/audio_input.h>

#include <array>
#include <limits>

#include <ArduinoJson.h>

namespace stackchan::bridge_client {
namespace {

bool isValidUuid(const std::string& value)
{
    if (value.size() != 36) {
        return false;
    }
    constexpr std::array<std::size_t, 4> kHyphens = {8, 13, 18, 23};
    for (std::size_t index = 0; index < value.size(); ++index) {
        bool isHyphen = false;
        for (const std::size_t hyphen : kHyphens) {
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
    return true;
}

const char* triggerName(AudioInputTrigger trigger)
{
    switch (trigger) {
        case AudioInputTrigger::Touch:
            return "touch";
        case AudioInputTrigger::Button:
            return "button";
        case AudioInputTrigger::Wakeword:
            return "wakeword";
        case AudioInputTrigger::ControlApi:
            return "control_api";
        case AudioInputTrigger::Simulator:
            return "simulator";
    }
    return nullptr;
}

const char* endReasonName(AudioInputEndReason reason)
{
    switch (reason) {
        case AudioInputEndReason::Silence:
            return "silence";
        case AudioInputEndReason::MaxDuration:
            return "max_duration";
        case AudioInputEndReason::UserCancel:
            return "user_cancel";
        case AudioInputEndReason::DeviceError:
            return "device_error";
        case AudioInputEndReason::Disconnect:
            return "disconnect";
    }
    return nullptr;
}

bool validIdentity(
    const EnvelopeMetadata& envelope,
    const std::string& turnId,
    const std::string& streamId
)
{
    return isValidUuid(envelope.messageId)
        && envelope.sentAtMs
            <= static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())
        && isValidUuid(turnId) && isValidUuid(streamId);
}

void addEnvelope(
    ArduinoJson::JsonDocument& document,
    const char* type,
    const EnvelopeMetadata& envelope,
    const std::string& turnId,
    const std::string& streamId
)
{
    document["v"] = 1;
    document["type"] = type;
    document["message_id"] = envelope.messageId;
    document["turn_id"] = turnId;
    document["stream_id"] = streamId;
    document["sent_at_ms"] = envelope.sentAtMs;
}

AudioInputBuildError finishDocument(ArduinoJson::JsonDocument& document, std::string& output)
{
    serializeJson(document, output);
    if (output.size() > kMaxJsonBytes) {
        output.clear();
        return AudioInputBuildError::MessageTooLarge;
    }
    return AudioInputBuildError::None;
}

}  // namespace

AudioInputBuildError buildAudioInputStartJson(
    const EnvelopeMetadata& envelope,
    const std::string& turnId,
    const std::string& streamId,
    AudioInputTrigger trigger,
    int frameMs,
    std::string& output
)
{
    output.clear();
    const char* triggerValue = triggerName(trigger);
    if (!validIdentity(envelope, turnId, streamId) || triggerValue == nullptr
        || (frameMs != 20 && frameMs != 40 && frameMs != 60)) {
        return AudioInputBuildError::InvalidArgument;
    }

    ArduinoJson::JsonDocument document;
    addEnvelope(document, "audio.input.start", envelope, turnId, streamId);
    ArduinoJson::JsonObject payload = document["payload"].to<ArduinoJson::JsonObject>();
    payload["codec"] = "opus";
    payload["sample_rate"] = 16000;
    payload["channels"] = 1;
    payload["frame_ms"] = frameMs;
    payload["trigger"] = triggerValue;
    return finishDocument(document, output);
}

AudioInputBuildError buildAudioInputEndJson(
    const EnvelopeMetadata& envelope,
    const std::string& turnId,
    const std::string& streamId,
    AudioInputEndReason reason,
    std::string& output
)
{
    output.clear();
    const char* reasonValue = endReasonName(reason);
    if (!validIdentity(envelope, turnId, streamId) || reasonValue == nullptr) {
        return AudioInputBuildError::InvalidArgument;
    }

    ArduinoJson::JsonDocument document;
    addEnvelope(document, "audio.input.end", envelope, turnId, streamId);
    ArduinoJson::JsonObject payload = document["payload"].to<ArduinoJson::JsonObject>();
    payload["reason"] = reasonValue;
    return finishDocument(document, output);
}

}  // namespace stackchan::bridge_client
