#pragma once

#include <string>

#include <stackchan_bridge_client/protocol.h>

namespace stackchan::bridge_client {

enum class DeviceFaultEventType {
    DeviceError,
    ServoError,
};

enum class DeviceFaultCode {
    AudioDecodeError,
    AudioEncodeError,
    InternalError,
};

enum class EventBuildError {
    None,
    InvalidArgument,
    MessageTooLarge,
};

EventBuildError buildDeviceFaultEventJson(
    const EnvelopeMetadata& envelope,
    const std::string& deviceId,
    DeviceFaultEventType type,
    DeviceFaultCode code,
    const std::string& message,
    std::string& output
);

EventBuildError buildTouchTapEventJson(
    const EnvelopeMetadata& envelope,
    const std::string& deviceId,
    int x,
    int y,
    std::string& output
);

}  // namespace stackchan::bridge_client
