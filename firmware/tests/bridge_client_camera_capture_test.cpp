#include <cstdlib>
#include <iostream>
#include <limits>
#include <map>
#include <string>
#include <vector>

#include <stackchan_bridge_client/camera_capture.h>

namespace {

using stackchan::bridge_client::CameraCaptureGate;
using stackchan::bridge_client::CameraCaptureRequest;
using stackchan::bridge_client::CameraCompletionError;
using stackchan::bridge_client::CameraEventBuildError;
using stackchan::bridge_client::CameraRequestError;
using stackchan::bridge_client::CameraMultipartUpload;
using stackchan::bridge_client::CameraUploadError;
using stackchan::bridge_client::CameraUploadTransport;
using stackchan::bridge_client::CaptureRetryBudget;
using stackchan::bridge_client::EnvelopeMetadata;
using stackchan::bridge_client::buildCameraCompletedEventJson;
using stackchan::bridge_client::resolveCaptureUploadUrl;

constexpr char kCaptureId[] = "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7";

class FakeCameraUploadTransport final : public CameraUploadTransport {
public:
    void setTimeoutMs(int value) override
    {
        timeoutMs = value;
    }

    void setHeader(const std::string& name, const std::string& value) override
    {
        headers[name] = value;
    }

    bool openPost(const std::string& value) override
    {
        url = value;
        return openResult;
    }

    bool write(const std::uint8_t* data, std::size_t size) override
    {
        if (!writeResult) {
            return false;
        }
        if (size == 0) {
            ended = true;
        } else {
            body.insert(body.end(), data, data + size);
        }
        return true;
    }

    int statusCode() override
    {
        return responseStatus;
    }

    void close() override
    {
        closed = true;
    }

    std::map<std::string, std::string> headers;
    std::string url;
    std::vector<std::uint8_t> body;
    int timeoutMs = 0;
    int responseStatus = 201;
    bool openResult = true;
    bool writeResult = true;
    bool ended = false;
    bool closed = false;
};

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testOnlyOneValidatedCaptureCanOwnTheCamera()
{
    CameraCaptureGate gate;
    CameraCaptureRequest request;
    request.captureId = kCaptureId;
    request.quality = 80;

    expect(gate.tryStart(request) == CameraRequestError::None, "valid capture was rejected");
    expect(gate.busy(), "accepted capture did not own the camera");
    expect(gate.current().captureId == kCaptureId, "capture ownership was lost");
    expect(
        gate.tryStart(request) == CameraRequestError::DeviceBusy,
        "concurrent capture did not report busy"
    );

    gate.complete();
    expect(!gate.busy(), "completed capture retained camera ownership");
    expect(gate.tryStart(request) == CameraRequestError::None, "camera was not reusable");
}

void testAcceptedCaptureWaitsForExplicitPostResponseDispatch()
{
    CameraCaptureGate gate;
    CameraCaptureRequest request;
    request.captureId = kCaptureId;
    request.quality = 70;

    expect(gate.tryStart(request) == CameraRequestError::None, "capture was not reserved");

    CameraCaptureRequest dispatched;
    expect(gate.takePending(dispatched), "reserved capture was not pending dispatch");
    expect(dispatched.captureId == kCaptureId, "dispatched capture lost its ID");
    expect(dispatched.quality == 70, "dispatched capture lost its quality");
    expect(!gate.takePending(dispatched), "capture work was dispatched more than once");
    expect(gate.busy(), "dispatched capture released ownership before completion");

    gate.complete();
    expect(!gate.takePending(dispatched), "completed capture retained pending work");
}

void testInvalidCaptureRequestNeverOwnsTheCamera()
{
    CameraCaptureGate gate;
    for (const int quality : {9, 96}) {
        CameraCaptureRequest request;
        request.captureId = kCaptureId;
        request.quality = quality;
        expect(
            gate.tryStart(request) == CameraRequestError::InvalidArgument,
            "invalid quality was accepted"
        );
        expect(!gate.busy(), "invalid quality acquired the camera");
    }
    CameraCaptureRequest invalidId;
    invalidId.captureId = "not-a-uuid";
    invalidId.quality = 80;
    expect(
        gate.tryStart(invalidId) == CameraRequestError::InvalidArgument,
        "invalid capture ID was accepted"
    );
    expect(!gate.busy(), "invalid capture ID acquired the camera");
}

void testUploadAttemptsStopAfterThree()
{
    CaptureRetryBudget budget(3);
    int attempt = 0;
    expect(budget.takeAttempt(attempt) && attempt == 1, "first upload attempt missing");
    expect(budget.takeAttempt(attempt) && attempt == 2, "second upload attempt missing");
    expect(budget.takeAttempt(attempt) && attempt == 3, "third upload attempt missing");
    expect(!budget.takeAttempt(attempt), "upload retried forever");
}

void testWebSocketEndpointMapsToOwnedCaptureUploadEndpoint()
{
    std::string output;
    expect(
        resolveCaptureUploadUrl(
            "ws://192.0.2.10:8765/v1/device/ws", kCaptureId, output
        ),
        "plain WebSocket URL was not mapped"
    );
    expect(
        output
            == "http://192.0.2.10:8765/v1/device/captures/"
                "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "plain capture upload URL changed"
    );
    expect(
        resolveCaptureUploadUrl("wss://bridge.local/v1/device/ws", kCaptureId, output),
        "secure WebSocket URL was not mapped"
    );
    expect(
        output
            == "https://bridge.local/v1/device/captures/"
                "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "secure capture upload URL changed"
    );
    expect(
        !resolveCaptureUploadUrl("http://bridge.local/v1/device/ws", kCaptureId, output),
        "non-WebSocket scheme was accepted"
    );
    expect(output.empty(), "failed URL resolution retained stale output");
}

void testCameraCompletionEventIsOwnedAndSafe()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 26;
    std::string output;

    expect(
        buildCameraCompletedEventJson(
            envelope,
            "stackchan-001",
            kCaptureId,
            true,
            CameraCompletionError::None,
            output
        ) == CameraEventBuildError::None,
        "successful camera event was not built"
    );
    expect(output.find(R"("name":"camera.completed")") != std::string::npos, "wrong event");
    expect(output.find(R"("device_id":"stackchan-001")") != std::string::npos, "device lost");
    expect(output.find(R"("capture_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7")")
               != std::string::npos,
           "capture lost");
    expect(output.find(R"("ok":true)") != std::string::npos, "success changed");
    expect(output.find("error_code") == std::string::npos, "success included an error code");

    expect(
        buildCameraCompletedEventJson(
            envelope,
            "stackchan-001",
            kCaptureId,
            false,
            CameraCompletionError::CaptureFailed,
            output
        ) == CameraEventBuildError::None,
        "failed camera event was not built"
    );
    expect(output.find(R"("error_code":"CAPTURE_FAILED")") != std::string::npos, "error changed");
}

void testCameraCompletionRejectsTimestampOutsideSignedJsonRange()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = static_cast<std::uint64_t>(
        std::numeric_limits<std::int64_t>::max()
    ) + 1;
    std::string output = "stale output";

    expect(
        buildCameraCompletedEventJson(
            envelope,
            "stackchan-001",
            kCaptureId,
            true,
            CameraCompletionError::None,
            output
        ) == CameraEventBuildError::InvalidArgument,
        "out-of-range camera event timestamp was accepted"
    );
    expect(output.empty(), "invalid camera event timestamp retained output");
}

void testMultipartUploadStreamsAuthenticatedBoundedJpeg()
{
    FakeCameraUploadTransport transport;
    CameraMultipartUpload upload(transport);
    const std::string url =
        "http://192.0.2.10:8765/v1/device/captures/"
        "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7";
    expect(
        upload.begin(url, "device-token", "stackchan-001") == CameraUploadError::None,
        "authenticated multipart upload did not start"
    );
    const std::uint8_t first[] = {0xFF, 0xD8, 0x01};
    const std::uint8_t last[] = {0x02, 0xFF, 0xD9};
    expect(
        upload.writeJpegChunk(first, sizeof(first)) == CameraUploadError::None,
        "first JPEG chunk was rejected"
    );
    expect(
        upload.writeJpegChunk(last, sizeof(last)) == CameraUploadError::None,
        "last JPEG chunk was rejected"
    );
    expect(upload.finish() == CameraUploadError::None, "valid JPEG upload did not finish");

    expect(transport.timeoutMs == 10'000, "capture upload timeout is not finite");
    expect(transport.url == url, "capture upload URL changed");
    expect(
        transport.headers["Authorization"] == "Bearer device-token",
        "capture upload lost bearer authentication"
    );
    expect(
        transport.headers["X-StackChan-Device-Id"] == "stackchan-001",
        "capture upload lost device ownership"
    );
    expect(
        transport.headers["Content-Type"].find("multipart/form-data; boundary=") == 0,
        "capture upload did not use multipart"
    );
    const std::string body(transport.body.begin(), transport.body.end());
    expect(body.find(R"(name="file"; filename="capture.jpg")") != std::string::npos,
           "multipart file part changed");
    expect(body.find("Content-Type: image/jpeg") != std::string::npos,
           "multipart JPEG type changed");
    expect(body.find(std::string(reinterpret_cast<const char*>(first), sizeof(first)))
               != std::string::npos,
           "JPEG bytes were copied incorrectly");
    expect(transport.ended, "chunked request was not terminated");
    expect(transport.closed, "finished upload retained HTTP resources");
}

void testMultipartUploadRejectsOversizeAndInvalidJpeg()
{
    FakeCameraUploadTransport oversizedTransport;
    CameraMultipartUpload oversized(oversizedTransport);
    expect(
        oversized.begin("http://bridge/capture", "token", "stackchan-001")
            == CameraUploadError::None,
        "oversize test upload did not start"
    );
    std::vector<std::uint8_t> bytes(stackchan::bridge_client::kMaxJpegBytes + 1, 0x55);
    expect(
        oversized.writeJpegChunk(bytes.data(), bytes.size())
            == CameraUploadError::PayloadTooLarge,
        "oversized JPEG was accepted"
    );
    oversized.abort();
    expect(oversizedTransport.closed, "oversized upload was not closed");

    FakeCameraUploadTransport invalidTransport;
    CameraMultipartUpload invalid(invalidTransport);
    expect(
        invalid.begin("http://bridge/capture", "token", "stackchan-001")
            == CameraUploadError::None,
        "invalid JPEG test upload did not start"
    );
    const std::uint8_t invalidJpeg[] = {0x00, 0x01, 0x02, 0x03};
    expect(
        invalid.writeJpegChunk(invalidJpeg, sizeof(invalidJpeg)) == CameraUploadError::None,
        "bounded invalid JPEG chunk failed too early"
    );
    expect(invalid.finish() == CameraUploadError::InvalidJpeg, "invalid JPEG magic was accepted");
    expect(invalidTransport.closed, "invalid JPEG upload was not closed");
}

}  // namespace

int main()
{
    testOnlyOneValidatedCaptureCanOwnTheCamera();
    testAcceptedCaptureWaitsForExplicitPostResponseDispatch();
    testInvalidCaptureRequestNeverOwnsTheCamera();
    testUploadAttemptsStopAfterThree();
    testWebSocketEndpointMapsToOwnedCaptureUploadEndpoint();
    testCameraCompletionEventIsOwnedAndSafe();
    testCameraCompletionRejectsTimestampOutsideSignedJsonRange();
    testMultipartUploadStreamsAuthenticatedBoundedJpeg();
    testMultipartUploadRejectsOversizeAndInvalidJpeg();
    return 0;
}
