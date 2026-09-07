#include <stackchan_bridge_client/camera_capture.h>

#include <array>
#include <limits>

#include <ArduinoJson.h>

namespace stackchan::bridge_client {
namespace {

constexpr char kMultipartBoundary[] = "----StackChanHermesCapture";
constexpr int kCaptureUploadTimeoutMs = 10000;

bool isValidUuid(const std::string& value)
{
    if (value.size() != 36) {
        return false;
    }
    constexpr std::array<std::size_t, 4> kHyphens = {8, 13, 18, 23};
    for (std::size_t index = 0; index < value.size(); ++index) {
        bool isHyphen = false;
        for (const std::size_t hyphen : kHyphens) {
            if (index == hyphen) {
                isHyphen = true;
                break;
            }
        }
        const char character = value[index];
        if (isHyphen) {
            if (character != '-') {
                return false;
            }
        } else if (!((character >= '0' && character <= '9')
                     || (character >= 'a' && character <= 'f')
                     || (character >= 'A' && character <= 'F'))) {
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

const char* completionErrorName(CameraCompletionError error)
{
    switch (error) {
        case CameraCompletionError::CaptureFailed:
            return "CAPTURE_FAILED";
        case CameraCompletionError::InternalError:
            return "INTERNAL_ERROR";
        case CameraCompletionError::None:
            return nullptr;
    }
    return nullptr;
}

bool isSafeHeaderValue(const std::string& value)
{
    for (const unsigned char character : value) {
        if (character < 0x20 || character == 0x7F) {
            return false;
        }
    }
    return true;
}

}  // namespace

CameraMultipartUpload::CameraMultipartUpload(CameraUploadTransport& transport)
    : transport_(transport)
{
}

CameraMultipartUpload::~CameraMultipartUpload()
{
    abort();
}

CameraUploadError CameraMultipartUpload::begin(
    const std::string& url,
    const std::string& deviceToken,
    const std::string& deviceId
)
{
    if (active_ || url.empty() || deviceToken.empty() || deviceToken.size() > 512
        || !isSafeHeaderValue(deviceToken) || !isValidDeviceId(deviceId)) {
        return CameraUploadError::InvalidArgument;
    }
    jpegBytes_ = 0;
    firstByteCount_ = 0;
    lastByteCount_ = 0;
    transport_.setTimeoutMs(kCaptureUploadTimeoutMs);
    transport_.setHeader("Authorization", "Bearer " + deviceToken);
    transport_.setHeader("X-StackChan-Device-Id", deviceId);
    transport_.setHeader(
        "Content-Type", std::string("multipart/form-data; boundary=") + kMultipartBoundary
    );
    transport_.setHeader("Transfer-Encoding", "chunked");
    if (!transport_.openPost(url)) {
        return CameraUploadError::TransportFailure;
    }
    active_ = true;
    const std::string preamble = std::string("--") + kMultipartBoundary
        + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"capture.jpg\""
          "\r\nContent-Type: image/jpeg\r\n\r\n";
    if (!transport_.write(
            reinterpret_cast<const std::uint8_t*>(preamble.data()), preamble.size()
        )) {
        abort();
        return CameraUploadError::TransportFailure;
    }
    return CameraUploadError::None;
}

CameraUploadError CameraMultipartUpload::writeJpegChunk(
    const std::uint8_t* data,
    std::size_t size
)
{
    if (!active_ || data == nullptr || size == 0) {
        return CameraUploadError::InvalidArgument;
    }
    if (size > kMaxJpegBytes - jpegBytes_) {
        return CameraUploadError::PayloadTooLarge;
    }
    for (std::size_t index = 0; index < size; ++index) {
        const std::uint8_t byte = data[index];
        if (firstByteCount_ < 2) {
            firstBytes_[firstByteCount_++] = byte;
        }
        if (lastByteCount_ < 2) {
            lastBytes_[lastByteCount_++] = byte;
        } else {
            lastBytes_[0] = lastBytes_[1];
            lastBytes_[1] = byte;
        }
    }
    if (!transport_.write(data, size)) {
        abort();
        return CameraUploadError::TransportFailure;
    }
    jpegBytes_ += size;
    return CameraUploadError::None;
}

CameraUploadError CameraMultipartUpload::finish()
{
    if (!active_) {
        return CameraUploadError::InvalidArgument;
    }
    if (firstByteCount_ != 2 || lastByteCount_ != 2 || firstBytes_[0] != 0xFF
        || firstBytes_[1] != 0xD8 || lastBytes_[0] != 0xFF || lastBytes_[1] != 0xD9) {
        abort();
        return CameraUploadError::InvalidJpeg;
    }
    const std::string footer = std::string("\r\n--") + kMultipartBoundary + "--\r\n";
    if (!transport_.write(
            reinterpret_cast<const std::uint8_t*>(footer.data()), footer.size()
        )
        || !transport_.write(nullptr, 0)) {
        abort();
        return CameraUploadError::TransportFailure;
    }
    const int status = transport_.statusCode();
    transport_.close();
    active_ = false;
    return status == 201 ? CameraUploadError::None : CameraUploadError::Rejected;
}

void CameraMultipartUpload::abort()
{
    if (active_) {
        transport_.close();
        active_ = false;
    }
}

std::size_t CameraMultipartUpload::jpegBytes() const
{
    return jpegBytes_;
}

CameraRequestError CameraCaptureGate::tryStart(const CameraCaptureRequest& request)
{
    if (!isValidUuid(request.captureId) || request.quality < 10 || request.quality > 95) {
        return CameraRequestError::InvalidArgument;
    }
    if (busy_) {
        return CameraRequestError::DeviceBusy;
    }
    current_ = request;
    busy_ = true;
    pending_ = true;
    return CameraRequestError::None;
}

bool CameraCaptureGate::takePending(CameraCaptureRequest& output)
{
    if (!busy_ || !pending_) {
        return false;
    }
    output = current_;
    pending_ = false;
    return true;
}

void CameraCaptureGate::complete()
{
    current_ = {};
    busy_ = false;
    pending_ = false;
}

bool CameraCaptureGate::busy() const
{
    return busy_;
}

const CameraCaptureRequest& CameraCaptureGate::current() const
{
    return current_;
}

CaptureRetryBudget::CaptureRetryBudget(int maximumAttempts)
    : maximumAttempts_(maximumAttempts > 0 ? maximumAttempts : 0)
{
}

bool CaptureRetryBudget::takeAttempt(int& attemptNumber)
{
    if (attempts_ >= maximumAttempts_) {
        return false;
    }
    ++attempts_;
    attemptNumber = attempts_;
    return true;
}

bool resolveCaptureUploadUrl(
    const std::string& bridgeWebSocketUrl,
    const std::string& captureId,
    std::string& output
)
{
    output.clear();
    if (!isValidUuid(captureId)) {
        return false;
    }
    constexpr char kWebSocketPath[] = "/v1/device/ws";
    const std::size_t pathPosition = bridgeWebSocketUrl.rfind(kWebSocketPath);
    if (pathPosition == std::string::npos
        || pathPosition + sizeof(kWebSocketPath) - 1 != bridgeWebSocketUrl.size()) {
        return false;
    }

    std::string scheme;
    std::size_t authorityStart = 0;
    if (bridgeWebSocketUrl.rfind("ws://", 0) == 0) {
        scheme = "http://";
        authorityStart = 5;
    } else if (bridgeWebSocketUrl.rfind("wss://", 0) == 0) {
        scheme = "https://";
        authorityStart = 6;
    } else {
        return false;
    }
    if (pathPosition <= authorityStart) {
        return false;
    }
    output = scheme + bridgeWebSocketUrl.substr(authorityStart, pathPosition - authorityStart)
        + "/v1/device/captures/" + captureId;
    return true;
}

CameraEventBuildError buildCameraCompletedEventJson(
    const EnvelopeMetadata& envelope,
    const std::string& deviceId,
    const std::string& captureId,
    bool ok,
    CameraCompletionError error,
    std::string& output
)
{
    output.clear();
    const char* errorCode = completionErrorName(error);
    if (!isValidUuid(envelope.messageId) || !isValidDeviceId(deviceId)
        || !isValidUuid(captureId)
        || envelope.sentAtMs
            > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())
        || (ok && error != CameraCompletionError::None)
        || (!ok && errorCode == nullptr)) {
        return CameraEventBuildError::InvalidArgument;
    }

    ArduinoJson::JsonDocument document;
    document["v"] = 1;
    document["type"] = "event";
    document["message_id"] = envelope.messageId;
    document["sent_at_ms"] = envelope.sentAtMs;
    document["device_id"] = deviceId;
    ArduinoJson::JsonObject payload = document["payload"].to<ArduinoJson::JsonObject>();
    payload["name"] = "camera.completed";
    ArduinoJson::JsonObject data = payload["data"].to<ArduinoJson::JsonObject>();
    data["capture_id"] = captureId;
    data["ok"] = ok;
    if (!ok) {
        data["error_code"] = errorCode;
    }

    serializeJson(document, output);
    if (output.size() > kMaxJsonBytes) {
        output.clear();
        return CameraEventBuildError::MessageTooLarge;
    }
    return CameraEventBuildError::None;
}

}  // namespace stackchan::bridge_client
