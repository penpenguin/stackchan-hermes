#pragma once

namespace stackchan::bridge_client {

enum class DeviceState {
    Booting,
    ConnectingWifi,
    ConnectingBridge,
    Idle,
    Listening,
    Speaking,
    Error,
    Updating,
};

enum class DeviceEvent {
    InitializationSucceeded,
    WifiConnected,
    HelloAcknowledged,
    BridgeDisconnected,
    HardwareOrConfigFailure,
    RetryableFailure,
    WifiLost,
    LocalInputAccepted,
    PlaybackStarted,
    ThinkingChanged,
    UpdateStarted,
    InputEnded,
    PlaybackEnded,
    BargeInTriggered,
    SafetyError,
    RecoverySucceeded,
    UpdateCompleted,
    UpdateFailed,
};

enum class TransitionError {
    None,
    InvalidState,
};

const char* deviceStateName(DeviceState state);

class DeviceStateMachine {
public:
    DeviceState state() const;
    TransitionError transition(DeviceEvent event);

private:
    DeviceState state_ = DeviceState::Booting;
};

}  // namespace stackchan::bridge_client
