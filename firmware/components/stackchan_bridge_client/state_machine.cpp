#include <stackchan_bridge_client/state_machine.h>

namespace stackchan::bridge_client {

const char* deviceStateName(DeviceState state)
{
    switch (state) {
        case DeviceState::Booting:
            return "BOOTING";
        case DeviceState::ConnectingWifi:
            return "CONNECTING_WIFI";
        case DeviceState::ConnectingBridge:
            return "CONNECTING_BRIDGE";
        case DeviceState::Idle:
            return "IDLE";
        case DeviceState::Listening:
            return "LISTENING";
        case DeviceState::Speaking:
            return "SPEAKING";
        case DeviceState::Error:
            return "ERROR";
        case DeviceState::Updating:
            return "UPDATING";
    }
    return "ERROR";
}

DeviceState DeviceStateMachine::state() const
{
    return state_;
}

TransitionError DeviceStateMachine::transition(DeviceEvent event)
{
    if (event == DeviceEvent::SafetyError && state_ != DeviceState::Updating) {
        state_ = DeviceState::Error;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Booting && event == DeviceEvent::InitializationSucceeded) {
        state_ = DeviceState::ConnectingWifi;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Booting && event == DeviceEvent::HardwareOrConfigFailure) {
        state_ = DeviceState::Error;
        return TransitionError::None;
    }
    if (state_ == DeviceState::ConnectingWifi && event == DeviceEvent::WifiConnected) {
        state_ = DeviceState::ConnectingBridge;
        return TransitionError::None;
    }
    if (state_ == DeviceState::ConnectingWifi && event == DeviceEvent::RetryableFailure) {
        return TransitionError::None;
    }
    if (state_ == DeviceState::ConnectingWifi && event == DeviceEvent::HardwareOrConfigFailure) {
        state_ = DeviceState::Error;
        return TransitionError::None;
    }
    if (state_ == DeviceState::ConnectingBridge && event == DeviceEvent::HelloAcknowledged) {
        state_ = DeviceState::Idle;
        return TransitionError::None;
    }
    if (state_ == DeviceState::ConnectingBridge && event == DeviceEvent::RetryableFailure) {
        return TransitionError::None;
    }
    if (state_ == DeviceState::ConnectingBridge && event == DeviceEvent::WifiLost) {
        state_ = DeviceState::ConnectingWifi;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Idle && event == DeviceEvent::BridgeDisconnected) {
        state_ = DeviceState::ConnectingBridge;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Idle && event == DeviceEvent::LocalInputAccepted) {
        state_ = DeviceState::Listening;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Idle && event == DeviceEvent::PlaybackStarted) {
        state_ = DeviceState::Speaking;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Idle && event == DeviceEvent::ThinkingChanged) {
        return TransitionError::None;
    }
    if (state_ == DeviceState::Idle && event == DeviceEvent::UpdateStarted) {
        state_ = DeviceState::Updating;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Listening && event == DeviceEvent::InputEnded) {
        state_ = DeviceState::Idle;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Listening && event == DeviceEvent::PlaybackStarted) {
        state_ = DeviceState::Speaking;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Listening && event == DeviceEvent::BridgeDisconnected) {
        state_ = DeviceState::ConnectingBridge;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Speaking && event == DeviceEvent::PlaybackEnded) {
        state_ = DeviceState::Idle;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Speaking && event == DeviceEvent::BargeInTriggered) {
        state_ = DeviceState::Listening;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Speaking && event == DeviceEvent::BridgeDisconnected) {
        state_ = DeviceState::ConnectingBridge;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Error && event == DeviceEvent::RecoverySucceeded) {
        state_ = DeviceState::ConnectingWifi;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Updating && event == DeviceEvent::UpdateCompleted) {
        state_ = DeviceState::Booting;
        return TransitionError::None;
    }
    if (state_ == DeviceState::Updating && event == DeviceEvent::UpdateFailed) {
        state_ = DeviceState::Error;
        return TransitionError::None;
    }
    return TransitionError::InvalidState;
}

}  // namespace stackchan::bridge_client
