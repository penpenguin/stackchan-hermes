#pragma once

#include <mutex>
#include <string>
#include <thread>
#include "capture_network.h"
#include <stackchan_bridge_client/capture_transaction.h>

#include <stackchan_bridge_client/camera_capture.h>
#include <stackchan_bridge_client/command_executor.h>

class Board;
class NetworkInterface;

namespace stackchan::hermes {

using CameraCaptureCompletion = bridge_client::CaptureCompletionNotice;

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
    bridge_client::CommandTargetResult start(const std::string& captureId, int quality, int timeoutMs);
    bool cancel(const std::string& captureId);
    void update();
    bool completion(CameraCaptureCompletion& output);
    void acknowledgeCompletion(const std::string& captureId);

private:
    void run(bridge_client::CameraCaptureRequest request);
    bool captureAndUpload(const bridge_client::CameraCaptureRequest& request, CameraCaptureCompletion& result);

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
    bridge_client::CaptureCompletionQueue notifications_;
    std::shared_ptr<CaptureIoContext> io_;
};

}  // namespace stackchan::hermes
