#pragma once

#include <mutex>
#include <string>
#include <thread>

#include <stackchan_bridge_client/camera_capture.h>
#include <stackchan_bridge_client/command_executor.h>

class Board;
class NetworkInterface;

namespace stackchan::hermes {

struct CameraCaptureCompletion {
    std::string captureId;
    bool ok = false;
    bridge_client::CameraCompletionError error =
        bridge_client::CameraCompletionError::CaptureFailed;
};

class OfficialCameraCapture {
public:
    OfficialCameraCapture(
        Board& board,
        NetworkInterface& network,
        std::string bridgeUrl,
        std::string deviceToken,
        std::string deviceId
    );
    ~OfficialCameraCapture();

    OfficialCameraCapture(const OfficialCameraCapture&) = delete;
    OfficialCameraCapture& operator=(const OfficialCameraCapture&) = delete;

    void setBridgeUrl(std::string bridgeUrl);
    bool available() const;
    bridge_client::CommandTargetResult start(const std::string& captureId, int quality);
    void update();
    bool completion(CameraCaptureCompletion& output) const;
    void acknowledgeCompletion();

private:
    void run(bridge_client::CameraCaptureRequest request);
    bool captureAndUpload(const bridge_client::CameraCaptureRequest& request);
    bool uploadAttempt(
        const bridge_client::CameraCaptureRequest& request,
        const std::string& uploadUrl
    );

    Board& board_;
    NetworkInterface& network_;
    std::string bridgeUrl_;
    std::string deviceToken_;
    std::string deviceId_;
    mutable std::mutex mutex_;
    bridge_client::CameraCaptureGate gate_;
    CameraCaptureCompletion completion_;
    bool completionReady_ = false;
    std::thread worker_;
};

}  // namespace stackchan::hermes
