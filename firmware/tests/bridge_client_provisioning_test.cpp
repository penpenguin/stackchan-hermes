#include <cstdlib>
#include <iostream>

#include <stackchan_bridge_client/provisioning.h>

namespace {

using stackchan::bridge_client::ProvisioningAction;
using stackchan::bridge_client::ProvisioningError;
using stackchan::bridge_client::WifiCycleAuthorization;
using stackchan::bridge_client::authorizeAttendedWifiCycle;
using stackchan::bridge_client::parseProvisioningArguments;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testValidBridgeUrlCanBeProvisioned()
{
    const char* arguments[] = {
        "stackchan-hermes",
        "set-url",
        "ws://192.0.2.10:8765/v1/device/ws",
    };

    const auto result = parseProvisioningArguments(3, arguments);

    expect(result.error == ProvisioningError::None, "valid URL was rejected");
    expect(result.action == ProvisioningAction::SetBridgeUrl, "wrong provisioning action");
    expect(result.value == arguments[2], "provisioned URL changed");
    expect(result.restartRequired, "runtime configuration did not require a safe restart");
}

void testValidDeviceTokenCanBeProvisioned()
{
    const char* arguments[] = {
        "stackchan-hermes",
        "set-token",
        "example-device-token_0123456789",  // pragma: allowlist secret
    };

    const auto result = parseProvisioningArguments(3, arguments);

    expect(result.error == ProvisioningError::None, "valid token was rejected");
    expect(result.action == ProvisioningAction::SetBridgeToken, "wrong token action");
    expect(result.value == arguments[2], "provisioned token changed");
    expect(result.restartRequired, "token change did not require a safe restart");
}

void testHeaderInjectionTokenIsRejectedWithoutReturningTheSecret()
{
    const char* arguments[] = {
        "stackchan-hermes",
        "set-token",
        "secret\r\nInjected: value",
    };

    const auto result = parseProvisioningArguments(3, arguments);

    expect(result.error == ProvisioningError::InvalidValue, "header injection token was accepted");
    expect(result.action == ProvisioningAction::None, "invalid token produced a write action");
    expect(result.value.empty(), "invalid token was returned to the caller");
    expect(!result.restartRequired, "rejected token requested a restart");
}

void testValidAttendedWifiCycleDoesNotRequireAReboot()
{
    for (const char* duration : {"5", "15", "30"}) {
        const char* arguments[] = {
            "stackchan-hermes",
            "cycle-wifi",
            duration,
        };

        const auto result = parseProvisioningArguments(3, arguments);

        expect(result.error == ProvisioningError::None, "valid WiFi cycle was rejected");
        expect(result.action == ProvisioningAction::CycleWifi, "wrong WiFi cycle action");
        expect(result.value == duration, "WiFi cycle duration changed");
        expect(!result.restartRequired, "temporary WiFi cycle requested a reboot");
    }
}

void testAttendedWifiCycleAllowsOnlyOneConnectedAttempt()
{
    bool used = false;

    expect(
        authorizeAttendedWifiCycle(false, used) == WifiCycleAuthorization::NotConnected,
        "disconnected WiFi cycle was authorized"
    );
    expect(!used, "rejected disconnected WiFi cycle consumed the one-shot gate");
    expect(
        authorizeAttendedWifiCycle(true, used) == WifiCycleAuthorization::Allowed,
        "first connected WiFi cycle was rejected"
    );
    expect(used, "accepted WiFi cycle did not consume the one-shot gate");
    expect(
        authorizeAttendedWifiCycle(true, used) == WifiCycleAuthorization::AlreadyUsed,
        "second WiFi cycle was authorized"
    );
}

void testEveryRuntimeSettingHasAValidatedProvisioningAction()
{
    const struct {
        const char* command;
        const char* value;
        ProvisioningAction action;
    } cases[] = {
        {"set-device-id", "stackchan-001", ProvisioningAction::SetDeviceId},
        {"set-device-name", "スタックチャン", ProvisioningAction::SetDeviceName},
        {"set-fallback-url", "wss://bridge.local/v1/device/ws", ProvisioningAction::SetBridgeFallbackUrl},
        {"set-discovery", "enabled", ProvisioningAction::SetBridgeDiscoveryEnabled},
        {"set-volume", "65", ProvisioningAction::SetAudioVolume},
        {"set-brightness", "70", ProvisioningAction::SetDisplayBrightness},
        {"set-idle-level", "2", ProvisioningAction::SetMotionIdleLevel},
        {"set-touch", "disabled", ProvisioningAction::SetTouchEnabled},
    };

    for (const auto& value : cases) {
        const char* arguments[] = {"stackchan-hermes", value.command, value.value};
        const auto result = parseProvisioningArguments(3, arguments);
        expect(result.error == ProvisioningError::None, "valid runtime setting was rejected");
        expect(result.action == value.action, "runtime setting mapped to the wrong action");
        expect(result.restartRequired, "runtime setting did not request safe restart");
    }
}

void testInvalidRuntimeSettingsCannotProduceWrites()
{
    const struct {
        const char* command;
        const char* value;
    } cases[] = {
        {"set-device-id", "../unsafe"},
        {"set-device-name", "bad\nname"},
        {"set-fallback-url", "http://bridge.local/v1/device/ws"},
        {"set-discovery", "maybe"},
        {"set-volume", "101"},
        {"set-brightness", "-1"},
        {"set-idle-level", "4"},
        {"set-touch", "true"},
        {"cycle-wifi", "4"},
        {"cycle-wifi", "31"},
        {"cycle-wifi", "15s"},
    };

    for (const auto& value : cases) {
        const char* arguments[] = {"stackchan-hermes", value.command, value.value};
        const auto result = parseProvisioningArguments(3, arguments);
        expect(result.error == ProvisioningError::InvalidValue, "invalid setting was accepted");
        expect(result.action == ProvisioningAction::None, "invalid setting produced a write action");
        expect(result.value.empty(), "invalid setting value was retained");
        expect(!result.restartRequired, "invalid setting requested restart");
    }
}

}  // namespace


int main()
{
    testValidBridgeUrlCanBeProvisioned();
    testValidDeviceTokenCanBeProvisioned();
    testHeaderInjectionTokenIsRejectedWithoutReturningTheSecret();
    testValidAttendedWifiCycleDoesNotRequireAReboot();
    testAttendedWifiCycleAllowsOnlyOneConnectedAttempt();
    testEveryRuntimeSettingHasAValidatedProvisioningAction();
    testInvalidRuntimeSettingsCannotProduceWrites();
    return 0;
}
