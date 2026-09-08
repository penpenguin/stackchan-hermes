#pragma once

#include <string>

#include <stackchan_bridge_client/command.h>

namespace stackchan::bridge_client {

struct DeviceInfo {
    std::string deviceId;
    std::string deviceName;
    std::string firmwareVersion;
    std::string hardwareModel;
};

struct DeviceStatus {
    std::string deviceId;
    std::string firmwareVersion;
    std::string hardwareModel;
    std::string state;
    int batteryPercent = 0;
    int volume = 0;
    int brightness = 0;
    int wifiRssiDbm = 0;
};

struct HeadAngles {
    double yaw = 0;
    double pitch = 0;
};

enum class CommandTargetResult {
    Success,
    InvalidState,
    DeviceBusy,
};

class DeviceCommandTarget {
public:
    virtual ~DeviceCommandTarget() = default;

    virtual DeviceInfo getInfo() const = 0;
    virtual DeviceStatus getStatus() const = 0;
    virtual bool setVolume(int volume) = 0;
    virtual bool setBrightness(int brightness) = 0;
    virtual bool showText(const std::string& text, int durationMs, int priority) = 0;
    virtual bool setExpression(const std::string& expression) = 0;
    virtual bool setBlink(bool enabled) = 0;
    virtual int ledCount() const = 0;
    virtual bool setLed(int index, int red, int green, int blue) = 0;
    virtual bool setAllLeds(int red, int green, int blue) = 0;
    virtual bool clearLeds() = 0;
    virtual bool setHeadAngles(double yaw, double pitch, int speed) = 0;
    virtual bool homeHead(int speed) = 0;
    virtual bool getHeadAngles(HeadAngles& output) const = 0;
    virtual bool cancelSpeech(const std::string& turnId) = 0;
    virtual bool cancelCapture(const std::string&) { return false; }
    virtual CommandTargetResult startCapture(const std::string& captureId, int quality, int timeoutMs) = 0;
};

CommandExecutionResult executeCommand(const Command& command, DeviceCommandTarget& target);

}  // namespace stackchan::bridge_client
