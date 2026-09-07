#include <cstdlib>
#include <iostream>

#include <stackchan_bridge_client/state_machine.h>

namespace {

using stackchan::bridge_client::DeviceEvent;
using stackchan::bridge_client::DeviceState;
using stackchan::bridge_client::DeviceStateMachine;
using stackchan::bridge_client::TransitionError;
using stackchan::bridge_client::deviceStateName;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void reachConnectingBridge(DeviceStateMachine& machine)
{
    expect(
        machine.transition(DeviceEvent::InitializationSucceeded) == TransitionError::None,
        "initialization failed"
    );
    expect(
        machine.transition(DeviceEvent::WifiConnected) == TransitionError::None,
        "Wi-Fi connection failed"
    );
}

void reachIdle(DeviceStateMachine& machine)
{
    reachConnectingBridge(machine);
    expect(
        machine.transition(DeviceEvent::HelloAcknowledged) == TransitionError::None,
        "hello acknowledgement failed"
    );
}

void testBootInitializationStartsWifiConnection()
{
    DeviceStateMachine machine;
    expect(machine.state() == DeviceState::Booting, "initial state is not BOOTING");
    expect(
        machine.transition(DeviceEvent::InitializationSucceeded) == TransitionError::None,
        "initialization transition failed"
    );
    expect(
        machine.state() == DeviceState::ConnectingWifi,
        "initialization did not start Wi-Fi connection"
    );
}

void testEveryDeviceStateHasAStableProtocolName()
{
    const struct {
        DeviceState state;
        const char* name;
    } cases[] = {
        {DeviceState::Booting, "BOOTING"},
        {DeviceState::ConnectingWifi, "CONNECTING_WIFI"},
        {DeviceState::ConnectingBridge, "CONNECTING_BRIDGE"},
        {DeviceState::Idle, "IDLE"},
        {DeviceState::Listening, "LISTENING"},
        {DeviceState::Speaking, "SPEAKING"},
        {DeviceState::Error, "ERROR"},
        {DeviceState::Updating, "UPDATING"},
    };
    for (const auto& value : cases) {
        expect(
            std::string(deviceStateName(value.state)) == value.name,
            "device state protocol name changed"
        );
    }
}

void testBootFailureEntersError()
{
    DeviceStateMachine machine;
    expect(
        machine.transition(DeviceEvent::HardwareOrConfigFailure) == TransitionError::None,
        "boot failure transition failed"
    );
    expect(machine.state() == DeviceState::Error, "boot failure did not enter ERROR");
}

void testRetryableWifiFailureKeepsConnecting()
{
    DeviceStateMachine machine;
    expect(
        machine.transition(DeviceEvent::InitializationSucceeded) == TransitionError::None,
        "initialization failed"
    );
    expect(
        machine.transition(DeviceEvent::RetryableFailure) == TransitionError::None,
        "retryable Wi-Fi failure was rejected"
    );
    expect(
        machine.state() == DeviceState::ConnectingWifi,
        "retryable Wi-Fi failure changed state"
    );
}

void testFatalWifiFailureEntersError()
{
    DeviceStateMachine machine;
    expect(
        machine.transition(DeviceEvent::InitializationSucceeded) == TransitionError::None,
        "initialization failed"
    );
    expect(
        machine.transition(DeviceEvent::HardwareOrConfigFailure) == TransitionError::None,
        "fatal Wi-Fi failure was rejected"
    );
    expect(machine.state() == DeviceState::Error, "fatal Wi-Fi failure did not enter ERROR");
}

void testRetryableBridgeFailureKeepsConnecting()
{
    DeviceStateMachine machine;
    reachConnectingBridge(machine);
    expect(
        machine.transition(DeviceEvent::RetryableFailure) == TransitionError::None,
        "retryable Bridge failure was rejected"
    );
    expect(
        machine.state() == DeviceState::ConnectingBridge,
        "retryable Bridge failure changed state"
    );
}

void testWifiLossWhileConnectingBridgeRestartsWifiConnection()
{
    DeviceStateMachine machine;
    reachConnectingBridge(machine);
    expect(
        machine.transition(DeviceEvent::WifiLost) == TransitionError::None,
        "Wi-Fi loss was rejected"
    );
    expect(
        machine.state() == DeviceState::ConnectingWifi,
        "Wi-Fi loss did not restart Wi-Fi connection"
    );
}

void testAuthenticatedConnectionReachesIdle()
{
    DeviceStateMachine machine;
    expect(
        machine.transition(DeviceEvent::InitializationSucceeded) == TransitionError::None,
        "initialization failed"
    );
    expect(
        machine.transition(DeviceEvent::WifiConnected) == TransitionError::None,
        "Wi-Fi connection failed"
    );
    expect(
        machine.state() == DeviceState::ConnectingBridge,
        "Wi-Fi did not begin Bridge connection"
    );
    expect(
        machine.transition(DeviceEvent::HelloAcknowledged) == TransitionError::None,
        "hello acknowledgement failed"
    );
    expect(machine.state() == DeviceState::Idle, "authenticated connection did not reach IDLE");
    expect(
        machine.transition(DeviceEvent::HelloAcknowledged) == TransitionError::InvalidState,
        "duplicate acknowledgement was accepted"
    );
    expect(machine.state() == DeviceState::Idle, "invalid transition changed state");
    expect(
        machine.transition(DeviceEvent::BridgeDisconnected) == TransitionError::None,
        "Bridge disconnect was rejected"
    );
    expect(
        machine.state() == DeviceState::ConnectingBridge,
        "Bridge disconnect did not begin reconnect"
    );
}

void testAcceptedLocalInputStartsListening()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::LocalInputAccepted) == TransitionError::None,
        "local input was rejected"
    );
    expect(machine.state() == DeviceState::Listening, "local input did not start LISTENING");
}

void testPlaybackStartFromIdleStartsSpeaking()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::PlaybackStarted) == TransitionError::None,
        "playback start was rejected"
    );
    expect(machine.state() == DeviceState::Speaking, "playback did not start SPEAKING");
}

void testThinkingOverlayDoesNotChangeIdleState()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::ThinkingChanged) == TransitionError::None,
        "thinking overlay change was rejected"
    );
    expect(machine.state() == DeviceState::Idle, "thinking overlay changed the physical state");
}

void testAuthenticatedUpdateEntersUpdating()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::UpdateStarted) == TransitionError::None,
        "update start was rejected"
    );
    expect(machine.state() == DeviceState::Updating, "update did not enter UPDATING");
}

void testInputEndReturnsListeningToIdle()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::LocalInputAccepted) == TransitionError::None,
        "local input was rejected"
    );
    expect(
        machine.transition(DeviceEvent::InputEnded) == TransitionError::None,
        "input end was rejected"
    );
    expect(machine.state() == DeviceState::Idle, "input end did not return to IDLE");
}

void testPlaybackStartWhileListeningStartsSpeaking()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::LocalInputAccepted) == TransitionError::None,
        "local input was rejected"
    );
    expect(
        machine.transition(DeviceEvent::PlaybackStarted) == TransitionError::None,
        "playback while listening was rejected"
    );
    expect(machine.state() == DeviceState::Speaking, "playback did not enter SPEAKING");
}

void testPlaybackEndReturnsSpeakingToIdle()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::PlaybackStarted) == TransitionError::None,
        "playback start was rejected"
    );
    expect(
        machine.transition(DeviceEvent::PlaybackEnded) == TransitionError::None,
        "playback end was rejected"
    );
    expect(machine.state() == DeviceState::Idle, "playback end did not return to IDLE");
}

void testBargeInMovesSpeakingToListening()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::PlaybackStarted) == TransitionError::None,
        "playback start was rejected"
    );
    expect(
        machine.transition(DeviceEvent::BargeInTriggered) == TransitionError::None,
        "barge-in was rejected"
    );
    expect(machine.state() == DeviceState::Listening, "barge-in did not enter LISTENING");
}

void testBridgeDisconnectWhileListeningStartsReconnect()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::LocalInputAccepted) == TransitionError::None,
        "local input was rejected"
    );
    expect(
        machine.transition(DeviceEvent::BridgeDisconnected) == TransitionError::None,
        "Bridge disconnect while listening was rejected"
    );
    expect(
        machine.state() == DeviceState::ConnectingBridge,
        "Bridge disconnect while listening did not start reconnect"
    );
}

void testBridgeDisconnectWhileSpeakingStartsReconnect()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::PlaybackStarted) == TransitionError::None,
        "playback start was rejected"
    );
    expect(
        machine.transition(DeviceEvent::BridgeDisconnected) == TransitionError::None,
        "Bridge disconnect while speaking was rejected"
    );
    expect(
        machine.state() == DeviceState::ConnectingBridge,
        "Bridge disconnect while speaking did not start reconnect"
    );
}

void testSafetyErrorFromIdleEntersError()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::SafetyError) == TransitionError::None,
        "safety error was rejected"
    );
    expect(machine.state() == DeviceState::Error, "safety error did not enter ERROR");
}

void testSafetyErrorFromListeningEntersError()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::LocalInputAccepted) == TransitionError::None,
        "local input was rejected"
    );
    expect(
        machine.transition(DeviceEvent::SafetyError) == TransitionError::None,
        "safety error while listening was rejected"
    );
    expect(machine.state() == DeviceState::Error, "listening safety error did not enter ERROR");
}

void testSafetyErrorCoversEveryOtherNonUpdatingState()
{
    DeviceStateMachine booting;
    expect(
        booting.transition(DeviceEvent::SafetyError) == TransitionError::None,
        "BOOTING safety error was rejected"
    );

    DeviceStateMachine wifi;
    expect(
        wifi.transition(DeviceEvent::InitializationSucceeded) == TransitionError::None,
        "initialization failed"
    );
    expect(
        wifi.transition(DeviceEvent::SafetyError) == TransitionError::None,
        "CONNECTING_WIFI safety error was rejected"
    );

    DeviceStateMachine bridge;
    reachConnectingBridge(bridge);
    expect(
        bridge.transition(DeviceEvent::SafetyError) == TransitionError::None,
        "CONNECTING_BRIDGE safety error was rejected"
    );

    DeviceStateMachine speaking;
    reachIdle(speaking);
    expect(
        speaking.transition(DeviceEvent::PlaybackStarted) == TransitionError::None,
        "playback start was rejected"
    );
    expect(
        speaking.transition(DeviceEvent::SafetyError) == TransitionError::None,
        "SPEAKING safety error was rejected"
    );

    expect(
        speaking.transition(DeviceEvent::SafetyError) == TransitionError::None,
        "ERROR safety error was rejected"
    );
    expect(speaking.state() == DeviceState::Error, "safety error did not remain in ERROR");
}

void testSafetyErrorDoesNotInterruptUpdating()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::UpdateStarted) == TransitionError::None,
        "update start was rejected"
    );
    expect(
        machine.transition(DeviceEvent::SafetyError) == TransitionError::InvalidState,
        "UPDATING accepted a non-updating safety transition"
    );
    expect(machine.state() == DeviceState::Updating, "invalid transition interrupted UPDATING");
}

void testExplicitRecoveryRestartsWifiConnection()
{
    DeviceStateMachine machine;
    expect(
        machine.transition(DeviceEvent::SafetyError) == TransitionError::None,
        "safety error was rejected"
    );
    expect(
        machine.transition(DeviceEvent::RecoverySucceeded) == TransitionError::None,
        "explicit recovery was rejected"
    );
    expect(
        machine.state() == DeviceState::ConnectingWifi,
        "explicit recovery did not restart Wi-Fi connection"
    );
}

void testVerifiedUpdateCompletionReturnsToBooting()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::UpdateStarted) == TransitionError::None,
        "update start was rejected"
    );
    expect(
        machine.transition(DeviceEvent::UpdateCompleted) == TransitionError::None,
        "verified update completion was rejected"
    );
    expect(machine.state() == DeviceState::Booting, "update completion did not return to BOOTING");
}

void testUpdateFailureEntersError()
{
    DeviceStateMachine machine;
    reachIdle(machine);
    expect(
        machine.transition(DeviceEvent::UpdateStarted) == TransitionError::None,
        "update start was rejected"
    );
    expect(
        machine.transition(DeviceEvent::UpdateFailed) == TransitionError::None,
        "safe update failure was rejected"
    );
    expect(machine.state() == DeviceState::Error, "update failure did not enter ERROR");
}

}  // namespace

int main()
{
    testBootInitializationStartsWifiConnection();
    testEveryDeviceStateHasAStableProtocolName();
    testBootFailureEntersError();
    testRetryableWifiFailureKeepsConnecting();
    testFatalWifiFailureEntersError();
    testRetryableBridgeFailureKeepsConnecting();
    testWifiLossWhileConnectingBridgeRestartsWifiConnection();
    testAuthenticatedConnectionReachesIdle();
    testAcceptedLocalInputStartsListening();
    testPlaybackStartFromIdleStartsSpeaking();
    testThinkingOverlayDoesNotChangeIdleState();
    testAuthenticatedUpdateEntersUpdating();
    testInputEndReturnsListeningToIdle();
    testPlaybackStartWhileListeningStartsSpeaking();
    testPlaybackEndReturnsSpeakingToIdle();
    testBargeInMovesSpeakingToListening();
    testBridgeDisconnectWhileListeningStartsReconnect();
    testBridgeDisconnectWhileSpeakingStartsReconnect();
    testSafetyErrorFromIdleEntersError();
    testSafetyErrorFromListeningEntersError();
    testSafetyErrorCoversEveryOtherNonUpdatingState();
    testSafetyErrorDoesNotInterruptUpdating();
    testExplicitRecoveryRestartsWifiConnection();
    testVerifiedUpdateCompletionReturnsToBooting();
    testUpdateFailureEntersError();
    return 0;
}
