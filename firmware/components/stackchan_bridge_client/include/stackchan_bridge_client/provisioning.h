#pragma once

#include <string>

namespace stackchan::bridge_client {

enum class ProvisioningAction {
    None,
    SetDeviceId,
    SetDeviceName,
    SetBridgeUrl,
    SetBridgeFallbackUrl,
    SetBridgeToken,
    SetBridgeDiscoveryEnabled,
    SetAudioVolume,
    SetDisplayBrightness,
    SetMotionIdleLevel,
    SetTouchEnabled,
    CycleWifi,
};

enum class ProvisioningError {
    None,
    InvalidArguments,
    InvalidValue,
};

enum class WifiCycleAuthorization {
    Allowed,
    NotConnected,
    AlreadyUsed,
};

struct ProvisioningResult {
    ProvisioningAction action = ProvisioningAction::None;
    ProvisioningError error   = ProvisioningError::InvalidArguments;
    std::string value;
    int numericValue = 0;
    bool boolValue = false;
    bool restartRequired = false;
};

ProvisioningResult parseProvisioningArguments(int argumentCount, const char* const* arguments);
WifiCycleAuthorization authorizeAttendedWifiCycle(bool connected, bool& used);

}  // namespace stackchan::bridge_client
