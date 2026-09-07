#include <stackchan_bridge_client/provisioning.h>

#include <charconv>

#include <stackchan_bridge_client/settings.h>

namespace stackchan::bridge_client {
namespace {

bool isValidDeviceToken(const std::string& value)
{
    if (value.empty() || value.size() > 512) {
        return false;
    }
    for (unsigned char character : value) {
        if (character < 0x20 || character == 0x7F) {
            return false;
        }
    }
    return true;
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

bool isUtf8Continuation(unsigned char value)
{
    return value >= 0x80 && value <= 0xBF;
}

bool isValidDeviceName(const std::string& value)
{
    if (value.empty()) {
        return false;
    }
    std::size_t codePoints = 0;
    for (std::size_t index = 0; index < value.size();) {
        const auto first = static_cast<unsigned char>(value[index]);
        std::size_t length = 0;
        if (first <= 0x7F) {
            if (first < 0x20 || first == 0x7F) {
                return false;
            }
            length = 1;
        } else if (first >= 0xC2 && first <= 0xDF) {
            length = 2;
        } else if (first >= 0xE0 && first <= 0xEF) {
            length = 3;
        } else if (first >= 0xF0 && first <= 0xF4) {
            length = 4;
        } else {
            return false;
        }
        if (index + length > value.size()) {
            return false;
        }
        for (std::size_t offset = 1; offset < length; ++offset) {
            if (!isUtf8Continuation(static_cast<unsigned char>(value[index + offset]))) {
                return false;
            }
        }
        if (length == 3) {
            const auto second = static_cast<unsigned char>(value[index + 1]);
            if ((first == 0xE0 && second < 0xA0) || (first == 0xED && second > 0x9F)) {
                return false;
            }
        }
        if (length == 4) {
            const auto second = static_cast<unsigned char>(value[index + 1]);
            if ((first == 0xF0 && second < 0x90) || (first == 0xF4 && second > 0x8F)) {
                return false;
            }
        }
        index += length;
        if (++codePoints > 64) {
            return false;
        }
    }
    return true;
}

bool parseBoundedInteger(const std::string& value, int minimum, int maximum, int& output)
{
    int parsed = 0;
    const auto result = std::from_chars(value.data(), value.data() + value.size(), parsed);
    if (result.ec != std::errc{} || result.ptr != value.data() + value.size()
        || parsed < minimum || parsed > maximum) {
        return false;
    }
    output = parsed;
    return true;
}

bool parseEnabled(const std::string& value, bool& output)
{
    if (value == "enabled") {
        output = true;
        return true;
    }
    if (value == "disabled") {
        output = false;
        return true;
    }
    return false;
}

}  // namespace

WifiCycleAuthorization authorizeAttendedWifiCycle(bool connected, bool& used)
{
    if (used) {
        return WifiCycleAuthorization::AlreadyUsed;
    }
    if (!connected) {
        return WifiCycleAuthorization::NotConnected;
    }
    used = true;
    return WifiCycleAuthorization::Allowed;
}

ProvisioningResult parseProvisioningArguments(int argumentCount, const char* const* arguments)
{
    if (argumentCount != 3 || arguments == nullptr || arguments[1] == nullptr
        || arguments[2] == nullptr) {
        return ProvisioningResult{};
    }

    ProvisioningResult result;
    const std::string command = arguments[1];
    const std::string value = arguments[2];
    if (command == "set-device-id") {
        if (!isValidDeviceId(value)) {
            result.error = ProvisioningError::InvalidValue;
            return result;
        }
        result.action = ProvisioningAction::SetDeviceId;
    } else if (command == "set-device-name") {
        if (!isValidDeviceName(value)) {
            result.error = ProvisioningError::InvalidValue;
            return result;
        }
        result.action = ProvisioningAction::SetDeviceName;
    } else if (command == "set-url" || command == "set-fallback-url") {
        BridgeEndpointSources sources;
        sources.nvsUrl = value;
        if (!resolveBridgeEndpoint(sources).ok) {
            result.error = ProvisioningError::InvalidValue;
            return result;
        }
        result.action = command == "set-url" ? ProvisioningAction::SetBridgeUrl
                                              : ProvisioningAction::SetBridgeFallbackUrl;
    } else if (command == "set-token") {
        if (!isValidDeviceToken(value)) {
            result.error = ProvisioningError::InvalidValue;
            return result;
        }
        result.action = ProvisioningAction::SetBridgeToken;
    } else if (command == "set-discovery" || command == "set-touch") {
        if (!parseEnabled(value, result.boolValue)) {
            result.error = ProvisioningError::InvalidValue;
            return result;
        }
        result.action = command == "set-discovery"
            ? ProvisioningAction::SetBridgeDiscoveryEnabled
            : ProvisioningAction::SetTouchEnabled;
    } else if (command == "set-volume" || command == "set-brightness"
               || command == "set-idle-level") {
        const int maximum = command == "set-idle-level" ? 3 : 100;
        if (!parseBoundedInteger(value, 0, maximum, result.numericValue)) {
            result.error = ProvisioningError::InvalidValue;
            return result;
        }
        result.action = command == "set-volume" ? ProvisioningAction::SetAudioVolume
            : command == "set-brightness" ? ProvisioningAction::SetDisplayBrightness
                                             : ProvisioningAction::SetMotionIdleLevel;
    } else if (command == "cycle-wifi") {
        if (!parseBoundedInteger(value, 5, 30, result.numericValue)) {
            result.error = ProvisioningError::InvalidValue;
            return result;
        }
        result.action = ProvisioningAction::CycleWifi;
    } else {
        return result;
    }

    result.error           = ProvisioningError::None;
    result.value           = value;
    result.restartRequired = result.action != ProvisioningAction::CycleWifi;
    return result;
}

}  // namespace stackchan::bridge_client
