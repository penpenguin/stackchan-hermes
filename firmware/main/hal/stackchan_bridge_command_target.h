#pragma once

#include <atomic>
#include <cstdint>
#include <functional>
#include <string>

#include <stackchan_bridge_client/command_executor.h>
#include <stackchan_bridge_client/state_machine.h>

class Board;

namespace stackchan::hermes {

class OfficialDeviceCommandTarget final : public bridge_client::DeviceCommandTarget {
public:
    using CancelSpeechCallback = std::function<void()>;
    using StartCaptureCallback = std::function<bridge_client::CommandTargetResult(
        const std::string& captureId,
        int quality
    )>;

    OfficialDeviceCommandTarget(Board& board, int ledCount);

    void setCancelSpeechCallback(CancelSpeechCallback callback);
    void setStartCaptureCallback(StartCaptureCallback callback);
    void applyBridgeState(bridge_client::DeviceState state);
    void update(std::uint32_t nowMs);

    bridge_client::DeviceInfo getInfo() const override;
    bridge_client::DeviceStatus getStatus() const override;
    bool setVolume(int volume) override;
    bool setBrightness(int brightness) override;
    bool showText(const std::string& text, int durationMs, int priority) override;
    bool setExpression(const std::string& expression) override;
    bool setBlink(bool enabled) override;
    int ledCount() const override;
    bool setLed(int index, int red, int green, int blue) override;
    bool setAllLeds(int red, int green, int blue) override;
    bool clearLeds() override;
    bool setHeadAngles(double yaw, double pitch, int speed) override;
    bool homeHead(int speed) override;
    bool getHeadAngles(bridge_client::HeadAngles& output) const override;
    bool cancelSpeech(const std::string& turnId) override;
    bridge_client::CommandTargetResult startCapture(
        const std::string& captureId,
        int quality
    ) override;

private:
    Board& board_;
    int ledCount_ = 0;
    CancelSpeechCallback cancelSpeechCallback_;
    StartCaptureCallback startCaptureCallback_;
    std::uint32_t textExpiresAtMs_ = 0;
    int textPriority_ = -1;
    bool textVisible_ = false;
    std::atomic<bridge_client::DeviceState> bridgeState_{
        bridge_client::DeviceState::Booting
    };
    std::atomic<bool> notificationDirty_{true};
    std::atomic<bool> presentationDirty_{true};
};

}  // namespace stackchan::hermes
