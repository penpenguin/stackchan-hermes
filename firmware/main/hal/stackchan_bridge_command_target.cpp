#include "stackchan_bridge_command_target.h"

#include <cmath>
#include <cstdint>
#include <utility>

#include <board.h>
#include <assets/lang_config.h>
#include <display.h>
#include <esp_app_desc.h>
#include <sdkconfig.h>
#include <settings.h>
#include <stackchan/stackchan.h>
#include <stackchan_bridge_client/hardware_identity.h>
#include <stackchan_bridge_client/motion_safety.h>
#include <wifi_manager.h>

#include "hal.h"
#include "board/stackchan_display.h"

namespace stackchan::hermes {
namespace {

const char* officialEmotion(const std::string& expression)
{
    if (expression == "happy") {
        return "happy";
    }
    if (expression == "thinking") {
        return "doubtful";
    }
    if (expression == "sad") {
        return "sad";
    }
    if (expression == "surprised") {
        return "doubtful";
    }
    return "neutral";
}

}  // namespace

OfficialDeviceCommandTarget::OfficialDeviceCommandTarget(Board& board, int ledCount)
    : board_(board), ledCount_(ledCount)
{
}

void OfficialDeviceCommandTarget::setCancelSpeechCallback(CancelSpeechCallback callback)
{
    cancelSpeechCallback_ = std::move(callback);
}

void OfficialDeviceCommandTarget::setStartCaptureCallback(StartCaptureCallback callback)
{
    startCaptureCallback_ = std::move(callback);
}

void OfficialDeviceCommandTarget::applyBridgeState(bridge_client::DeviceState state)
{
    bridgeState_.store(state);
    notificationDirty_.store(true);
    presentationDirty_.store(true);
}

void OfficialDeviceCommandTarget::update(std::uint32_t nowMs)
{
    auto* display = board_.GetDisplay();
    if (display != nullptr && notificationDirty_.exchange(false)) {
        switch (bridgeState_.load()) {
            case bridge_client::DeviceState::Idle:
                display->ShowNotification("Bridge connected", 1600);
                break;
            case bridge_client::DeviceState::ConnectingBridge:
                display->ShowNotification("Connecting Bridge", 3000);
                break;
            default:
                break;
        }
    }
    if (display != nullptr && display->IsSetupUICalled()
        && presentationDirty_.exchange(false)) {
        switch (bridgeState_.load()) {
            case bridge_client::DeviceState::Idle:
                display->SetEmotion("neutral");
                display->SetStatus(Lang::Strings::STANDBY);
                break;
            case bridge_client::DeviceState::Listening:
                display->SetEmotion("doubtful");
                display->SetStatus(Lang::Strings::LISTENING);
                break;
            case bridge_client::DeviceState::Speaking:
                display->SetStatus(Lang::Strings::SPEAKING);
                break;
            case bridge_client::DeviceState::Error:
                display->SetEmotion("sad");
                display->SetStatus("Bridge error");
                break;
            case bridge_client::DeviceState::Booting:
                display->SetStatus("Starting Bridge client");
                break;
            case bridge_client::DeviceState::ConnectingWifi:
                display->SetStatus("Connecting Wi-Fi");
                break;
            case bridge_client::DeviceState::ConnectingBridge:
                display->SetEmotion("neutral");
                display->SetStatus("Connecting Bridge");
                break;
            case bridge_client::DeviceState::Updating:
                display->SetStatus("Updating");
                break;
        }
    }
    if (!textVisible_ || static_cast<std::int32_t>(nowMs - textExpiresAtMs_) < 0) {
        return;
    }
    if (display != nullptr) {
        display->ClearChatMessages();
    }
    textVisible_ = false;
    textPriority_ = -1;
}

bridge_client::DeviceInfo OfficialDeviceCommandTarget::getInfo() const
{
    Settings deviceSettings("device", false);
    bridge_client::DeviceInfo info;
    info.deviceId = deviceSettings.GetString("id", board_.GetUuid());
    info.deviceName = deviceSettings.GetString("name", "StackChan");
    info.firmwareVersion = esp_app_get_description()->version;
    info.hardwareModel = bridge_client::kStackChanHardwareModel;
    return info;
}

bridge_client::DeviceStatus OfficialDeviceCommandTarget::getStatus() const
{
    const auto info = getInfo();
    const auto& wifi = WifiManager::GetInstance();
    bridge_client::DeviceStatus status;
    status.deviceId = info.deviceId;
    status.firmwareVersion = info.firmwareVersion;
    status.hardwareModel = info.hardwareModel;
    status.state = bridge_client::deviceStateName(bridgeState_.load());
    status.batteryPercent = GetHAL().getBatteryLevel();
    status.volume = GetHAL().getSpeakerVolume();
    status.brightness = GetHAL().getBackLightBrightness();
    status.wifiRssiDbm = wifi.IsConnected() ? wifi.GetRssi() : -127;
    return status;
}

bool OfficialDeviceCommandTarget::setVolume(int volume)
{
    if (board_.GetAudioCodec() == nullptr) {
        return false;
    }
    GetHAL().setSpeakerVolume(static_cast<std::uint8_t>(volume), true);
    Settings settings("audio", true);
    settings.SetInt("volume", volume);
    return true;
}

bool OfficialDeviceCommandTarget::setBrightness(int brightness)
{
    if (board_.GetDisplay() == nullptr) {
        return false;
    }
    GetHAL().setBackLightBrightness(static_cast<std::uint8_t>(brightness), true);
    return true;
}

bool OfficialDeviceCommandTarget::showText(
    const std::string& text,
    int durationMs,
    int priority
)
{
    auto* display = board_.GetDisplay();
    if (display == nullptr) {
        return false;
    }
    const std::uint32_t nowMs = GetHAL().millis();
    if (textVisible_ && static_cast<std::int32_t>(nowMs - textExpiresAtMs_) < 0
        && priority < textPriority_) {
        return false;
    }
    display->ShowNotification(text.c_str(), durationMs);
    textExpiresAtMs_ = nowMs + static_cast<std::uint32_t>(durationMs);
    textPriority_ = priority;
    textVisible_ = true;
    return true;
}

bool OfficialDeviceCommandTarget::setExpression(const std::string& expression)
{
    auto* display = dynamic_cast<StackChanAvatarDisplay*>(board_.GetDisplay());
    if (display == nullptr) {
        return false;
    }
    if (!display->IsSetupUICalled()) {
        display->SetupUI();
    }
    if (!GetStackChan().hasAvatar()) {
        return false;
    }
    presentationDirty_.store(false);
    display->SetEmotion(officialEmotion(expression));
    return true;
}

bool OfficialDeviceCommandTarget::setBlink(bool enabled)
{
    auto* display = dynamic_cast<StackChanAvatarDisplay*>(board_.GetDisplay());
    return display != nullptr && display->SetBlinkEnabled(enabled);
}

int OfficialDeviceCommandTarget::ledCount() const
{
    return ledCount_;
}

bool OfficialDeviceCommandTarget::setLed(int index, int red, int green, int blue)
{
    if (index < 0 || index >= ledCount_) {
        return false;
    }
    GetHAL().setRgbColor(
        static_cast<std::uint8_t>(index),
        static_cast<std::uint8_t>(red),
        static_cast<std::uint8_t>(green),
        static_cast<std::uint8_t>(blue)
    );
    GetHAL().refreshRgb();
    return true;
}

bool OfficialDeviceCommandTarget::setAllLeds(int red, int green, int blue)
{
    if (ledCount_ <= 0) {
        return false;
    }
    GetHAL().showRgbColor(
        static_cast<std::uint8_t>(red),
        static_cast<std::uint8_t>(green),
        static_cast<std::uint8_t>(blue)
    );
    return true;
}

bool OfficialDeviceCommandTarget::clearLeds()
{
    return setAllLeds(0, 0, 0);
}

bool OfficialDeviceCommandTarget::setHeadAngles(double yaw, double pitch, int speed)
{
#if CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK
    return false;
#else
    if (!bridge_client::K151MotionSafety::contains(yaw, pitch, speed)) {
        return false;
    }
    LvglLockGuard lock;
    auto& motion = GetStackChan().motion();
    motion.moveFromAuthenticatedBridgeWithSpeed(
        static_cast<int>(std::lround(yaw * 10.0)),
        static_cast<int>(std::lround(pitch * 10.0)),
        speed * 10
    );
    return true;
#endif
}

bool OfficialDeviceCommandTarget::homeHead(int speed)
{
    return setHeadAngles(
        bridge_client::K151MotionSafety::kHomeYawDegrees,
        bridge_client::K151MotionSafety::kHomePitchDegrees,
        speed
    );
}

bool OfficialDeviceCommandTarget::getHeadAngles(bridge_client::HeadAngles& output) const
{
    LvglLockGuard lock;
    const auto angles = GetStackChan().motion().getCurrentAngles();
    output.yaw = static_cast<double>(angles.x) / 10.0;
    output.pitch = static_cast<double>(angles.y) / 10.0;
    return true;
}

bool OfficialDeviceCommandTarget::cancelSpeech(const std::string&)
{
    if (!cancelSpeechCallback_) {
        return false;
    }
    cancelSpeechCallback_();
    return true;
}

bridge_client::CommandTargetResult OfficialDeviceCommandTarget::startCapture(
    const std::string& captureId,
    int quality
)
{
    if (!startCaptureCallback_) {
        return bridge_client::CommandTargetResult::InvalidState;
    }
    return startCaptureCallback_(captureId, quality);
}

}  // namespace stackchan::hermes
