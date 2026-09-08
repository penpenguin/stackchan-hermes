#include "stackchan_bridge_camera.h"
#include "stackchan_bridge_camera_upload.h"

#include <algorithm>
#include <new>
#include <vector>
#include <ArduinoJson.h>
#include <board.h>
#include <esp_heap_caps.h>
#include <esp_log.h>
#include <esp_pthread.h>
#include <esp_timer.h>
#include <mbedtls/sha256.h>
#ifndef CONFIG_IDF_TARGET_ESP32
#include <jpg/image_to_jpeg.h>
#include "board/stackchan_camera.h"
#endif

namespace stackchan::hermes {
namespace {
std::uint64_t nowMs() { return esp_timer_get_time() / 1000; }
constexpr const char* kTag = "Capture";
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

#ifndef CONFIG_IDF_TARGET_ESP32
template<class T> struct PsramAllocator {
    using value_type = T;
    T* allocate(std::size_t count) {
        auto* value = static_cast<T*>(heap_caps_malloc(count * sizeof(T), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
        if (!value) { throw std::bad_alloc(); }
        return value;
    }
    void deallocate(T* value, std::size_t) { heap_caps_free(value); }
};
using Jpeg = std::vector<std::uint8_t, PsramAllocator<std::uint8_t>>;
struct Encoder {
    Jpeg bytes;
    CaptureIoContext* io;
    std::uint64_t end;
    bool terminated = false, failed = false;
};
std::size_t encodeChunk(void* argument, std::size_t, const void* data, std::size_t size)
{
    auto& output = *static_cast<Encoder*>(argument);
    if (output.io->cancelled.load() || nowMs() >= output.end) { output.failed = true; return 0; }
    if (!data || !size) { output.terminated = true; return 0; }
    if (size > bridge_client::kMaxJpegBytes - output.bytes.size()) { output.failed = true; return 0; }
    try {
        const auto* first = static_cast<const std::uint8_t*>(data);
        output.bytes.insert(output.bytes.end(), first, first + size);
    } catch (...) { output.failed = true; return 0; }
    return size;
}
std::string digest(const Jpeg& jpeg)
{
    unsigned char output[32];
    if (mbedtls_sha256(jpeg.data(), jpeg.size(), output, 0) != 0) { return {}; }
    const char* hex = "0123456789abcdef";
    std::string result;
    for (unsigned char byte : output) { result += hex[byte >> 4]; result += hex[byte & 15]; }
    return result;
}
struct Receipt { int status = -1; std::string state, digest; std::size_t size = 0; std::uint32_t remaining = 0; };
Receipt readReceipt(CaptureNetwork& network, const std::string& url, const std::string& token, const std::string& deviceId)
{
    Receipt result;
    auto http = network.CreateHttp();
    http->SetHeader("Authorization", "Bearer " + token);
    http->SetHeader("X-StackChan-Device-Id", deviceId);
    http->SetTimeout(1); // The synchronous capture transport already drained the bounded response.
    if (!http->Open("GET", url + "/status")) { return result; }
    result.status = http->GetStatusCode();
    if (result.status == 200) {
        ArduinoJson::JsonDocument document;
        const auto body = http->ReadAll();
        if (body.size() > 8192 || deserializeJson(document, body, ArduinoJson::DeserializationOption::NestingLimit(4))
            || !document["remaining_ms"].is<std::uint32_t>() || !document["state"].is<const char*>()) {
            result.status = -1;
        } else {
            result.state = document["state"].as<std::string>();
            result.remaining = std::min<std::uint32_t>(120000, document["remaining_ms"].as<std::uint32_t>());
            result.digest = document["sha256"].as<std::string>();
            result.size = document["size_bytes"].as<std::size_t>();
        }
    }
    http->Close();
    return result;
}
#endif
} // namespace

OfficialCameraCapture::OfficialCameraCapture(Board& board, NetworkInterface& network,
    std::string bridgeUrl, std::string deviceToken, std::string deviceId)
    : board_(board), network_(network), bridgeUrl_(std::move(bridgeUrl)),
      deviceToken_(std::move(deviceToken)), deviceId_(std::move(deviceId)) {}
OfficialCameraCapture::~OfficialCameraCapture()
{
    if (io_) { io_->cancelled.store(true); }
    if (worker_.joinable()) { worker_.join(); }
}
void OfficialCameraCapture::setBridgeUrl(std::string url)
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (io_ && url != bridgeUrl_) { io_->cancelled.store(true); }
    bridgeUrl_ = std::move(url);
}
bool OfficialCameraCapture::available() const
{
#ifdef CONFIG_IDF_TARGET_ESP32
    return false;
#else
    return board_.GetCamera() != nullptr;
#endif
}
bridge_client::CommandTargetResult OfficialCameraCapture::start(const std::string& id, int quality, int timeoutMs)
{
    if (!available()) { return bridge_client::CommandTargetResult::InvalidState; }
    std::lock_guard<std::mutex> lock(mutex_);
    notifications_.purge(nowMs());
    if (notifications_.size() >= 16) { return bridge_client::CommandTargetResult::DeviceBusy; }
    bridge_client::CameraCaptureRequest request{id, quality, timeoutMs, nowMs()};
    const auto error = gate_.tryStart(request);
    if (error == bridge_client::CameraRequestError::DeviceBusy) { return bridge_client::CommandTargetResult::DeviceBusy; }
    if (error != bridge_client::CameraRequestError::None) { return bridge_client::CommandTargetResult::InvalidState; }
    return bridge_client::CommandTargetResult::Success;
}
bool OfficialCameraCapture::cancel(const std::string& id)
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (!gate_.busy() || gate_.current().captureId != id) { return false; }
    if (io_) { io_->cancelled.store(true); }
    else { gate_.complete(); }
    return true;
}
bool OfficialCameraCapture::completion(CameraCaptureCompletion& output)
{
    std::lock_guard<std::mutex> lock(mutex_);
    return notifications_.next(nowMs(), output);
}
void OfficialCameraCapture::acknowledgeCompletion(const std::string& id)
{
    std::lock_guard<std::mutex> lock(mutex_);
    notifications_.acknowledge(id);
}
void OfficialCameraCapture::update()
{
    std::thread finished;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (completionReady_) { finished = std::move(worker_); }
    }
    // No network or encoder work remains once completionReady_ is published.
    if (finished.joinable()) { finished.join(); }
    std::lock_guard<std::mutex> lock(mutex_);
    if (completionReady_) {
        completionReady_ = false;
        io_.reset();
        gate_.complete();
        ESP_LOGI(kTag, "capture_id=%s stage=released busy=0 ok=%d", completion_.captureId.c_str(), completion_.ok);
        notifications_.push(std::move(completion_));
        completion_ = {};
    }
    bridge_client::CameraCaptureRequest request;
    if (worker_.joinable() || !gate_.takePending(request)) { return; }
    try {
        io_ = std::make_shared<CaptureIoContext>();
        io_->captureId = request.captureId;
        io_->startedMs = request.startedMs;
        ScopedPthreadConfig cameraThreadConfig;
        if (!cameraThreadConfig.applied()) { throw std::bad_alloc(); }
        worker_ = std::thread(&OfficialCameraCapture::run, this, request);
    } catch (...) {
        completion_ = {};
        completion_.captureId = request.captureId;
        completion_.error = bridge_client::CameraCompletionError::InternalError;
        completion_.deadlineMs = request.startedMs + request.timeoutMs;
        completionReady_ = true;
    }
}
void OfficialCameraCapture::run(bridge_client::CameraCaptureRequest request)
{
    CameraCaptureCompletion result;
    result.captureId = request.captureId;
    result.deadlineMs = request.startedMs + request.timeoutMs;
    try { result.ok = captureAndUpload(request, result); }
    catch (...) { result.ok = false; result.error = bridge_client::CameraCompletionError::InternalError; }
    if (result.ok) { result.error = bridge_client::CameraCompletionError::None; }
    ESP_LOGI(kTag, "capture_id=%s stage=worker_end elapsed_ms=%llu ok=%d error=%d", request.captureId.c_str(),
        static_cast<unsigned long long>(nowMs() - request.startedMs), result.ok, io_ ? io_->error.load() : ENOMEM);
    std::lock_guard<std::mutex> lock(mutex_);
    completion_ = std::move(result);
    completionReady_ = true;
}
bool OfficialCameraCapture::captureAndUpload(const bridge_client::CameraCaptureRequest& request, CameraCaptureCompletion& result)
{
#ifdef CONFIG_IDF_TARGET_ESP32
    return false;
#else
    std::string bridgeUrl;
    { std::lock_guard<std::mutex> lock(mutex_); bridgeUrl = bridgeUrl_; }
    std::string url;
    if (!bridge_client::resolveCaptureUploadUrl(bridgeUrl, request.captureId, url)) { return false; }
    bridge_client::CaptureDeadline deadline(request.startedMs, request.timeoutMs);
    CaptureNetwork network(io_);
    io_->deadlineMs.store(deadline.operationDeadline(nowMs()));
    const auto queryStart = nowMs();
    const auto initial = readReceipt(network, url, deviceToken_, deviceId_);
    if (initial.status != 200 || initial.state != "reserved") { return false; }
    deadline.constrain(queryStart, initial.remaining);
    result.deadlineMs = deadline.end();
    if (nowMs() >= deadline.workEnd() || io_->cancelled.load()) { return false; }
    ESP_LOGI(kTag, "capture_id=%s stage=camera_begin busy=1", request.captureId.c_str());
    auto* camera = static_cast<StackChanCamera*>(board_.GetCamera());
    struct FrameRelease {
        StackChanCamera* camera;
        ~FrameRelease() { if (camera) { camera->ReleaseFrame(); } }
    } frameRelease{camera};
    if (!camera || !camera->Capture(deadline.workEnd(), &io_->cancelled) || !camera->GetFrameData()
        || camera->GetFrameWidth() != 320 || camera->GetFrameHeight() != 240) { return false; }
    ESP_LOGI(kTag, "capture_id=%s stage=jpeg_begin elapsed_ms=%llu", request.captureId.c_str(),
        static_cast<unsigned long long>(nowMs() - request.startedMs));
    Encoder encoder{{}, io_.get(), deadline.workEnd()};
    encoder.bytes.reserve(65536);
    const bool encoded = image_to_jpeg_cb(const_cast<std::uint8_t*>(camera->GetFrameData()),
        camera->GetFrameSize(), camera->GetFrameWidth(), camera->GetFrameHeight(),
        static_cast<v4l2_pix_fmt_t>(camera->GetFrameFormat()), request.quality, encodeChunk, &encoder);
    camera->ReleaseFrame();
    if (!encoded || !encoder.terminated || encoder.failed || encoder.bytes.empty()) { return false; }
    result.digest = digest(encoder.bytes);
    result.sizeBytes = encoder.bytes.size();
    ESP_LOGI(kTag, "capture_id=%s stage=jpeg_end elapsed_ms=%llu planned_bytes=%u busy=1",
        request.captureId.c_str(), static_cast<unsigned long long>(nowMs() - request.startedMs),
        static_cast<unsigned>(result.sizeBytes));
    if (result.digest.empty()) { return false; }
    for (int attempt = 1; attempt <= 3 && nowMs() < deadline.workEnd() && !io_->cancelled.load(); ++attempt) {
        io_->deadlineMs.store(deadline.operationDeadline(nowMs()));
        io_->attempt = attempt;
        io_->wireBytes = 0;
        int status = -1;
        std::string retryAfter;
        {
            auto http = network.CreateHttp();
            auto* response = http.get();
            OfficialCameraUploadTransport transport(std::move(http));
            bridge_client::CameraMultipartUpload upload(transport);
            auto error = upload.begin(url, deviceToken_, deviceId_, 1);
            for (std::size_t offset = 0; error == bridge_client::CameraUploadError::None && offset < encoder.bytes.size();) {
                const auto count = std::min<std::size_t>(4096, encoder.bytes.size() - offset);
                error = upload.writeJpegChunk(encoder.bytes.data() + offset, count);
                offset += count;
            }
            if (error == bridge_client::CameraUploadError::None) { error = upload.finish(); }
            response->SetTimeout(1);
            status = response->GetStatusCode();
            retryAfter = response->GetResponseHeader("Retry-After");
            ESP_LOGI(kTag, "capture_id=%s attempt=%d stage=upload_end elapsed_ms=%llu planned_bytes=%u sent_bytes=%u status=%d error=%d",
                request.captureId.c_str(), attempt, static_cast<unsigned long long>(nowMs() - request.startedMs),
                static_cast<unsigned>(encoder.bytes.size()), static_cast<unsigned>(upload.jpegBytes()), status, static_cast<int>(error));
            if (error == bridge_client::CameraUploadError::None && status == 201) { return true; }
        }
        if (status == 201) { return true; }
        if (status < 0 && nowMs() < deadline.workEnd() && !io_->cancelled.load()) {
            io_->deadlineMs.store(deadline.operationDeadline(nowMs()));
            const auto before = nowMs();
            const auto receipt = readReceipt(network, url, deviceToken_, deviceId_);
            if (receipt.status == 200) {
                deadline.constrain(before, receipt.remaining);
                result.deadlineMs = deadline.end();
                if ((receipt.state == "image_saved" || receipt.state == "succeeded")
                    && receipt.digest == result.digest && receipt.size == result.sizeBytes) { return true; }
                if (receipt.state != "reserved") { return false; }
            } else if (receipt.status >= 400 && receipt.status < 500) { return false; }
        }
        const int remaining = nowMs() < deadline.workEnd() ? deadline.workEnd() - nowMs() : 0;
        const int delay = bridge_client::captureRetryDelay(status, retryAfter, attempt, remaining);
        if (delay < 0) { return false; }
        const auto retryAt = nowMs() + delay;
        while (nowMs() < retryAt && !io_->cancelled.load()) { vTaskDelay(1); }
    }
    return false;
#endif
}
} // namespace stackchan::hermes
