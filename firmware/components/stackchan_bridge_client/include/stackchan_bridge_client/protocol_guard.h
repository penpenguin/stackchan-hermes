#pragma once

#include <cstdint>
#include <string>

#include <stackchan_bridge_client/protocol.h>

namespace stackchan::bridge_client {

enum class PeerErrorCode {
    InvalidMessage,
    InvalidArgument,
    InvalidState,
};

enum class PeerErrorBuildError {
    None,
    InvalidArgument,
    MessageTooLarge,
};

enum class RemoteErrorCode {
    UnsupportedVersion,
    Unauthorized,
    UnknownDevice,
    InvalidMessage,
    InvalidArgument,
    InvalidState,
    CommandTimeout,
    DeviceBusy,
    AudioDecodeError,
    AudioEncodeError,
    CaptureFailed,
    InternalError,
};

enum class RemoteErrorParseError {
    None,
    InvalidMessage,
    InvalidArgument,
    MessageTooLarge,
};

struct RemoteErrorMessage {
    RemoteErrorCode code = RemoteErrorCode::InvalidMessage;
    std::string messageId;
    std::string turnId;
    std::string streamId;
};

PeerErrorBuildError buildPeerErrorJson(
    const EnvelopeMetadata& envelope,
    PeerErrorCode code,
    const std::string& message,
    std::string& output
);

RemoteErrorParseError parseRemoteErrorJson(
    const std::string& input,
    RemoteErrorMessage& output
);

class InvalidMessageWindow {
public:
    bool observe(std::uint32_t nowMs);
    void reset();

private:
    std::uint32_t startedAtMs_ = 0;
    std::uint8_t count_ = 0;
};

}  // namespace stackchan::bridge_client
