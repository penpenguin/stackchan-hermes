#include "stackchan_bridge_camera.h"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <utility>

#include <board.h>
#include <esp_pthread.h>
#include <http.h>
#include <network_interface.h>

#ifndef CONFIG_IDF_TARGET_ESP32
#include <jpg/image_to_jpeg.h>

#include "board/stackchan_camera.h"
#endif

namespace stackchan::hermes {
namespace {

constexpr std::size_t kCameraWorkerStackSize = 12 * 1024;

class ScopedPthreadConfig {
public:
    ScopedPthreadConfig()
    {
        hasPrevious_ = esp_pthread_get_cfg(&previous_) == ESP_OK;
        auto configuration = hasPrevious_ ? previous_ : esp_pthread_get_default_config();
        configuration.stack_size = kCameraWorkerStackSize;
        configuration.inherit_cfg = false;
        configuration.thread_name = "hermes_camera";
        applied_ = esp_pthread_set_cfg(&configuration) == ESP_OK;
    }

    ~ScopedPthreadConfig()
    {
        restore();
    }

    ScopedPthreadConfig(const ScopedPthreadConfig&) = delete;
    ScopedPthreadConfig& operator=(const ScopedPthreadConfig&) = delete;

    bool applied() const
    {
        return applied_;
    }

private:
    void restore()
    {
        if (!applied_) {
            return;
        }
        const auto configuration =
            hasPrevious_ ? previous_ : esp_pthread_get_default_config();
        (void)esp_pthread_set_cfg(&configuration);
        applied_ = false;
    }

    esp_pthread_cfg_t previous_ = {};
    bool hasPrevious_ = false;
    bool applied_ = false;
};

class OfficialCameraUploadTransport final : public bridge_client::CameraUploadTransport {
public:
    explicit OfficialCameraUploadTransport(std::unique_ptr<Http> http)
        : http_(std::move(http))
    {
    }

    bool valid() const
    {
        return http_ != nullptr;
    }

    void setTimeoutMs(int timeoutMs) override
    {
        http_->SetTimeout(timeoutMs);
    }

    void setHeader(const std::string& name, const std::string& value) override
    {
        http_->SetHeader(name, value);
    }

    bool openPost(const std::string& url) override
    {
        return http_->Open("POST", url);
    }

    bool write(const std::uint8_t* data, std::size_t size) override
    {
        const char* bytes = size == 0 ? "" : reinterpret_cast<const char*>(data);
        return http_->Write(bytes, size) >= 0;
    }

    int statusCode() override
    {
        return http_->GetStatusCode();
    }

    void close() override
    {
        http_->Close();
    }

private:
    std::unique_ptr<Http> http_;
};

#ifndef CONFIG_IDF_TARGET_ESP32
struct JpegEncoderContext {
    bridge_client::CameraMultipartUpload* upload = nullptr;
    bridge_client::CameraUploadError error = bridge_client::CameraUploadError::None;
    bool terminated = false;
};

std::size_t writeJpegChunk(
    void* argument,
    std::size_t,
    const void* data,
    std::size_t size
)
{
    auto& context = *static_cast<JpegEncoderContext*>(argument);
    if (data == nullptr || size == 0) {
        context.terminated = true;
        return 0;
    }
    if (context.error != bridge_client::CameraUploadError::None) {
        return 0;
    }
    context.error = context.upload->writeJpegChunk(
        static_cast<const std::uint8_t*>(data), size
    );
    return context.error == bridge_client::CameraUploadError::None ? size : 0;
}
#endif

}  // namespace

OfficialCameraCapture::OfficialCameraCapture(
    Board& board,
    NetworkInterface& network,
    std::string bridgeUrl,
    std::string deviceToken,
    std::string deviceId
)
    : board_(board),
      network_(network),
      bridgeUrl_(std::move(bridgeUrl)),
      deviceToken_(std::move(deviceToken)),
      deviceId_(std::move(deviceId))
{
}

OfficialCameraCapture::~OfficialCameraCapture()
{
    if (worker_.joinable()) {
        worker_.join();
    }
}

void OfficialCameraCapture::setBridgeUrl(std::string bridgeUrl)
{
    std::lock_guard<std::mutex> lock(mutex_);
    bridgeUrl_ = std::move(bridgeUrl);
}

bool OfficialCameraCapture::available() const
{
#ifdef CONFIG_IDF_TARGET_ESP32
    return false;
#else
    return board_.GetCamera() != nullptr;
#endif
}

bridge_client::CommandTargetResult OfficialCameraCapture::start(
    const std::string& captureId,
    int quality
)
{
    if (!available()) {
        return bridge_client::CommandTargetResult::InvalidState;
    }
    bridge_client::CameraCaptureRequest request;
    request.captureId = captureId;
    request.quality = quality;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        const auto error = gate_.tryStart(request);
        if (error == bridge_client::CameraRequestError::InvalidArgument) {
            return bridge_client::CommandTargetResult::InvalidState;
        }
        if (error == bridge_client::CameraRequestError::DeviceBusy) {
            return bridge_client::CommandTargetResult::DeviceBusy;
        }
    }
    return bridge_client::CommandTargetResult::Success;
}

bool OfficialCameraCapture::completion(CameraCaptureCompletion& output) const
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (!completionReady_) {
        return false;
    }
    output = completion_;
    return true;
}

void OfficialCameraCapture::acknowledgeCompletion()
{
    std::thread completedWorker;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!completionReady_) {
            return;
        }
        completionReady_ = false;
        completion_ = {};
        gate_.complete();
        completedWorker = std::move(worker_);
    }
    if (completedWorker.joinable()) {
        completedWorker.join();
    }
}

void OfficialCameraCapture::update()
{
    bridge_client::CameraCaptureRequest request;
    std::lock_guard<std::mutex> lock(mutex_);
    if (completionReady_ || worker_.joinable() || !gate_.takePending(request)) {
        return;
    }
    ScopedPthreadConfig cameraThreadConfig;
    if (!cameraThreadConfig.applied()) {
        completion_.captureId = std::move(request.captureId);
        completion_.ok = false;
        completion_.error = bridge_client::CameraCompletionError::InternalError;
        completionReady_ = true;
        return;
    }
    try {
        worker_ = std::thread(&OfficialCameraCapture::run, this, std::move(request));
    } catch (...) {
        completion_.captureId = std::move(request.captureId);
        completion_.ok = false;
        completion_.error = bridge_client::CameraCompletionError::InternalError;
        completionReady_ = true;
    }
}

void OfficialCameraCapture::run(bridge_client::CameraCaptureRequest request)
{
    const bool ok = captureAndUpload(request);
    std::lock_guard<std::mutex> lock(mutex_);
    completion_.captureId = std::move(request.captureId);
    completion_.ok = ok;
    completion_.error = ok ? bridge_client::CameraCompletionError::None
                           : bridge_client::CameraCompletionError::CaptureFailed;
    completionReady_ = true;
}

bool OfficialCameraCapture::captureAndUpload(
    const bridge_client::CameraCaptureRequest& request
)
{
#ifdef CONFIG_IDF_TARGET_ESP32
    return false;
#else
    std::string bridgeUrl;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        bridgeUrl = bridgeUrl_;
    }
    std::string uploadUrl;
    if (!bridge_client::resolveCaptureUploadUrl(bridgeUrl, request.captureId, uploadUrl)) {
        return false;
    }
    auto* camera = static_cast<StackChanCamera*>(board_.GetCamera());
    if (camera == nullptr || !camera->Capture() || camera->GetFrameData() == nullptr
        || camera->GetFrameSize() == 0 || camera->GetFrameWidth() != 320
        || camera->GetFrameHeight() != 240) {
        return false;
    }

    bridge_client::CaptureRetryBudget retry(bridge_client::kMaxCaptureUploadAttempts);
    int attempt = 0;
    while (retry.takeAttempt(attempt)) {
        if (uploadAttempt(request, uploadUrl)) {
            return true;
        }
    }
    return false;
#endif
}

bool OfficialCameraCapture::uploadAttempt(
    const bridge_client::CameraCaptureRequest& request,
    const std::string& uploadUrl
)
{
#ifdef CONFIG_IDF_TARGET_ESP32
    return false;
#else
    OfficialCameraUploadTransport transport(network_.CreateHttp(3));
    if (!transport.valid()) {
        return false;
    }
    bridge_client::CameraMultipartUpload upload(transport);
    if (upload.begin(uploadUrl, deviceToken_, deviceId_)
        != bridge_client::CameraUploadError::None) {
        return false;
    }

    auto* camera = static_cast<StackChanCamera*>(board_.GetCamera());
    JpegEncoderContext context;
    context.upload = &upload;
    const bool encoded = image_to_jpeg_cb(
        const_cast<std::uint8_t*>(camera->GetFrameData()),
        camera->GetFrameSize(),
        static_cast<std::uint16_t>(camera->GetFrameWidth()),
        static_cast<std::uint16_t>(camera->GetFrameHeight()),
        static_cast<v4l2_pix_fmt_t>(camera->GetFrameFormat()),
        static_cast<std::uint8_t>(request.quality),
        writeJpegChunk,
        &context
    );
    return encoded && context.terminated
        && context.error == bridge_client::CameraUploadError::None
        && upload.finish() == bridge_client::CameraUploadError::None;
#endif
}

}  // namespace stackchan::hermes
