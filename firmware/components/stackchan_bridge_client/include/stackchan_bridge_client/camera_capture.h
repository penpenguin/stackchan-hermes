#pragma once

#include <string>

#include <stackchan_bridge_client/protocol.h>

namespace stackchan::bridge_client {

constexpr int kMaxCaptureUploadAttempts = 3;
constexpr std::size_t kMaxJpegBytes = 2 * 1024 * 1024;

struct CameraCaptureRequest {
    std::string captureId;
    int quality = 0;
    int timeoutMs = 0;
    std::uint64_t startedMs = 0;
};

enum class CameraRequestError {
    None,
    InvalidArgument,
    DeviceBusy,
};

enum class CameraCompletionError {
    None,
    CaptureFailed,
    InternalError,
};

enum class CameraEventBuildError {
    None,
    InvalidArgument,
    MessageTooLarge,
};

enum class CameraUploadError {
    None,
    InvalidArgument,
    TransportFailure,
    PayloadTooLarge,
    InvalidJpeg,
    Rejected,
};

class CameraUploadTransport {
public:
    virtual ~CameraUploadTransport() = default;

    virtual void setTimeoutMs(int timeoutMs) = 0;
    virtual void setHeader(const std::string& name, const std::string& value) = 0;
    virtual bool openPost(const std::string& url) = 0;
    virtual bool write(const std::uint8_t* data, std::size_t size) = 0;
    virtual int statusCode() = 0;
    virtual void close() = 0;
};

class CameraMultipartUpload {
public:
    explicit CameraMultipartUpload(CameraUploadTransport& transport);
    ~CameraMultipartUpload();

    CameraMultipartUpload(const CameraMultipartUpload&) = delete;
    CameraMultipartUpload& operator=(const CameraMultipartUpload&) = delete;

    CameraUploadError begin(
        const std::string& url,
        const std::string& deviceToken,
        const std::string& deviceId,
        int timeoutMs = 3000
    );
    CameraUploadError writeJpegChunk(const std::uint8_t* data, std::size_t size);
    CameraUploadError finish();
    void abort();
    std::size_t jpegBytes() const;

private:
    CameraUploadTransport& transport_;
    std::size_t jpegBytes_ = 0;
    std::uint8_t firstBytes_[2] = {};
    std::size_t firstByteCount_ = 0;
    std::uint8_t lastBytes_[2] = {};
    std::size_t lastByteCount_ = 0;
    bool active_ = false;
};

class CameraCaptureGate {
public:
    CameraRequestError tryStart(const CameraCaptureRequest& request);
    bool takePending(CameraCaptureRequest& output);
    void complete();
    bool busy() const;
    const CameraCaptureRequest& current() const;

private:
    CameraCaptureRequest current_;
    bool busy_ = false;
    bool pending_ = false;
};

class CaptureRetryBudget {
public:
    explicit CaptureRetryBudget(int maximumAttempts);
    bool takeAttempt(int& attemptNumber);

private:
    int maximumAttempts_ = 0;
    int attempts_ = 0;
};

bool resolveCaptureUploadUrl(
    const std::string& bridgeWebSocketUrl,
    const std::string& captureId,
    std::string& output
);

bool parseCameraCompletedAck(const std::string& input, std::string& captureId);

CameraEventBuildError buildCameraCompletedEventJson(
    const EnvelopeMetadata& envelope,
    const std::string& deviceId,
    const std::string& captureId,
    bool ok,
    CameraCompletionError error,
    std::string& output,
    const std::string& digest = {},
    std::size_t sizeBytes = 0
);

}  // namespace stackchan::bridge_client
