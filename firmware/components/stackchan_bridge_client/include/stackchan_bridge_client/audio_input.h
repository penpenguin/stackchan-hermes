#pragma once

#include <string>

#include <stackchan_bridge_client/protocol.h>

namespace stackchan::bridge_client {

enum class AudioInputTrigger {
    Touch,
    Button,
    Wakeword,
    ControlApi,
    Simulator,
};

enum class AudioInputEndReason {
    Silence,
    MaxDuration,
    UserCancel,
    DeviceError,
    Disconnect,
};

enum class AudioInputBuildError {
    None,
    InvalidArgument,
    MessageTooLarge,
};

enum class AudioInputError {
    None,
    InvalidArgument,
    InvalidState,
    PacketTooLarge,
    TransportFailure,
};

AudioInputBuildError buildAudioInputStartJson(
    const EnvelopeMetadata& envelope,
    const std::string& turnId,
    const std::string& streamId,
    AudioInputTrigger trigger,
    int frameMs,
    std::string& output
);

AudioInputBuildError buildAudioInputEndJson(
    const EnvelopeMetadata& envelope,
    const std::string& turnId,
    const std::string& streamId,
    AudioInputEndReason reason,
    std::string& output
);

}  // namespace stackchan::bridge_client
