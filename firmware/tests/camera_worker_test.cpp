#include "platform.h"
#include "stackchan_bridge_camera.h"
#include "board/stackchan_camera.h"
#include <board.h>
#include <esp_heap_caps.h>
#include <esp_pthread.h>
#include <esp_rom_sys.h>

#include <cassert>
#include <chrono>
#include <system_error>
#include <thread>

using namespace stackchan::hermes;
using stackchan::bridge_client::CommandTargetResult;
// Fail allocations on the dispatching thread only. Count every attempt through publication of the failure.
thread_local bool denyNew = false;
thread_local unsigned deniedAttempts = 0;
void* operator new(std::size_t size)
{
    if (denyNew) { ++deniedAttempts; throw std::bad_alloc(); }
    if (void* p = std::malloc(size ? size : 1)) { return p; }
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }

enum class Failure { None, Launch, FrameException, UnknownException, JpegAllocation, JpegGrowth };
static Failure failure = Failure::None;

WebSocket::~WebSocket() = default;
StackChanCamera::StackChanCamera(const esp_video_init_config_t&) {}
StackChanCamera::~StackChanCamera() { heap_caps_free(frame_.data); }
bool StackChanCamera::Capture() { return Capture(10000,nullptr); }
bool StackChanCamera::Capture(std::uint64_t,const std::atomic<bool>*) {
    ++worker_fake::captures;
    heap_caps_free(frame_.data);
    frame_.data=static_cast<std::uint8_t*>(heap_caps_malloc(320*240*2,1));
    frame_.len=320*240*2; frame_.width=320; frame_.height=240;
    if (failure == Failure::FrameException) { throw std::runtime_error("private-message"); }
    if (failure == Failure::UnknownException) { throw 123; }
    if (failure == Failure::JpegAllocation) { worker_fake::failAllocation = true; }
    return frame_.data != nullptr;
}
bool StackChanCamera::SetHMirror(bool) { return true; }
bool StackChanCamera::SetVFlip(bool) { return true; }
std::string response(int status,const std::string& body) {
    return "HTTP/1.1 " + std::to_string(status) + " Response\r\nContent-Length: " + std::to_string(body.size()) + "\r\n\r\n" + body;
}
std::thread launchWorker(void (OfficialCameraCapture::*entry)(), OfficialCameraCapture* owner)
{
    if (failure == Failure::Launch) {
        throw std::system_error(std::make_error_code(std::errc::resource_unavailable_try_again), "private-message");
    }
    return std::thread(entry, owner);
}

CameraCaptureCompletion awaitCompletion(OfficialCameraCapture& capture)
{
    CameraCaptureCompletion completion;
    for (int i = 0; i < 500; ++i) {
        capture.update();
        if (capture.completion(completion)) { return completion; }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::abort();
}

void checkFailureRecovery(Failure fault, const std::string& expected)
{
    const std::string id = "11111111-1111-4111-8111-111111111111";
    const std::string next = "22222222-2222-4222-8222-222222222222";
    const auto reserved = response(200, R"({"state":"reserved","remaining_ms":10000})");
    camera_fake::reset();
    worker_fake::diagnostic[0] = '\0';
    camera_fake::responses = {reserved};
    StackChanCamera camera({});
    Board board;
    board.camera = &camera;
    CaptureNetwork network(std::make_shared<CaptureIoContext>());
    OfficialCameraCapture capture(board, network, "ws://127.0.0.1:8765/v1/device/ws", "synthetic", "sim-001", launchWorker);
    worker_fake::readConfigResult = ESP_OK;
    worker_fake::currentConfig = {8192, true, "caller"};
    worker_fake::failJpegGrowth = fault == Failure::JpegGrowth;
    failure = fault;
    assert(capture.start(id, 80, 10000) == CommandTargetResult::Success);
    const auto failed = awaitCompletion(capture);
    assert(!failed.ok && failed.captureId == id);
    using stackchan::bridge_client::CameraCompletionError;
    assert(failed.error == (fault == Failure::JpegGrowth ? CameraCompletionError::CaptureFailed
                                                         : CameraCompletionError::InternalError));
    assert(std::strstr(worker_fake::diagnostic, expected.c_str()));
    assert(!std::strstr(worker_fake::diagnostic, "private-message"));
    assert(camera_fake::liveSockets == 0 && worker_fake::allocations == 0);
    assert(worker_fake::currentConfig.stack_size == 8192 && worker_fake::currentConfig.inherit_cfg);
    worker_fake::failJpegGrowth = false;
    failure = Failure::None;
    worker_fake::failAllocation = false;
    camera_fake::responses = {reserved, response(201, "{}")};
    camera_fake::responseIndex = 0;
    assert(capture.start(next, 80, 10000) == CommandTargetResult::Success);
    const auto recovered = awaitCompletion(capture);
    assert(recovered.ok && recovered.captureId == next);
}

void checkSetupFailures(const std::string& id)
{
    camera_fake::reset();
    StackChanCamera camera({});
    Board board;
    board.camera = &camera;
    CaptureNetwork network(std::make_shared<CaptureIoContext>());
    OfficialCameraCapture capture(board, network, "ws://127.0.0.1:8765/v1/device/ws", "synthetic", "sim-001");
    worker_fake::readConfigResult = -1;
    assert(capture.start(id, 80, 10000) == CommandTargetResult::Success);
    const auto readFailure = awaitCompletion(capture);
    assert(std::strstr(worker_fake::diagnostic, "stage=pthread_config_read reason=esp_error code=-1"));
    assert(readFailure.captureId == id && !readFailure.ok);
    assert(readFailure.error == stackchan::bridge_client::CameraCompletionError::InternalError);
    capture.acknowledgeCompletion(id);
    worker_fake::readConfigResult = ESP_ERR_NOT_FOUND;
    worker_fake::configResult = ESP_ERR_INVALID_ARG;
    assert(capture.start(id, 80, 10000) == CommandTargetResult::Success);
    capture.update();
    assert(std::strstr(worker_fake::diagnostic, "stage=pthread_config reason=esp_error code=258"));
    capture.update();
    CameraCaptureCompletion completion;
    assert(capture.completion(completion) && !completion.ok && completion.captureId == id);
    assert(completion.error == stackchan::bridge_client::CameraCompletionError::InternalError);
    worker_fake::configResult = ESP_OK;
    capture.acknowledgeCompletion(id);
    assert(capture.start(id, 80, 10000) == CommandTargetResult::Success);
    denyNew = true;
    capture.update();
    denyNew = false;
    assert(deniedAttempts == 1);
    assert(std::strstr(worker_fake::diagnostic, "stage=context_prepare reason=bad_alloc"));
    assert(std::strstr(worker_fake::diagnostic, "internal_free=20000 internal_largest=10000"));
    assert(std::strstr(worker_fake::diagnostic, "psram_free=90000 psram_largest=70000 stack_bytes=12288"));
    assert(capture.cancel(id));
    assert(capture.start(id, 80, 10000) == CommandTargetResult::DeviceBusy);
    capture.update();
    assert(capture.completion(completion) && !completion.ok && completion.captureId == id);
    assert(completion.error == stackchan::bridge_client::CameraCompletionError::InternalError);

    const std::string next = "22222222-2222-4222-8222-222222222222";
    camera_fake::responses = {response(200, R"({"state":"reserved","remaining_ms":10000})"), response(201, "{}")};
    worker_fake::restoreResult = ESP_ERR_INVALID_ARG;
    assert(capture.start(next, 80, 10000) == CommandTargetResult::Success);
    const auto recovered = awaitCompletion(capture);
    assert(recovered.ok && recovered.captureId == next);
    assert(std::strstr(worker_fake::diagnostic, "stage=pthread_restore reason=esp_error code=258"));
    worker_fake::restoreResult = ESP_OK;
}

int main() {
    const std::string id="11111111-1111-4111-8111-111111111111";
    const auto reserved=response(200,R"({"state":"reserved","remaining_ms":10000})");
    const auto saved=response(200,"{\"state\":\"image_saved\",\"remaining_ms\":9000,\"sha256\":\"" + std::string(64,'0') + "\",\"size_bytes\":6}");
    checkSetupFailures(id);
    checkFailureRecovery(Failure::Launch, "stage=thread_create reason=system_error code=" + std::to_string(EAGAIN));
    checkFailureRecovery(Failure::FrameException, "stage=frame_capture reason=std_exception");
    checkFailureRecovery(Failure::UnknownException, "stage=frame_capture reason=unknown_exception");
    checkFailureRecovery(Failure::JpegAllocation, "stage=jpeg_encode reason=bad_alloc");
    checkFailureRecovery(Failure::JpegGrowth, "stage=jpeg_encode reason=bad_alloc");
    for (int fault=0;fault<9;++fault) {
        camera_fake::reset(); worker_fake::encodes=0; worker_fake::captures=0;
        worker_fake::failEncoding=fault==4; worker_fake::failAllocation=fault==5;
        camera_fake::responses={reserved, fault==1 ? std::string{} : response(fault==2?404:fault==3?429:201,"{}"),saved};
        if (fault == 6) camera_fake::responses={reserved,response(500,"{}"),response(201,"{}")};
        if (fault == 7) camera_fake::responses={reserved,response(503,"{}"),response(503,"{}"),response(503,"{}")};
        if (fault == 8) camera_fake::responses={reserved,"",reserved,response(201,"{}")};
        StackChanCamera camera({}); Board board; board.camera=&camera;
        CaptureNetwork network(std::make_shared<CaptureIoContext>());
        OfficialCameraCapture capture(board,network,"ws://127.0.0.1:8765/v1/device/ws","synthetic","sim-001");
        assert(capture.start(id,80,10000)==CommandTargetResult::Success);
        assert(capture.start(id,80,10000)==CommandTargetResult::DeviceBusy);
        CameraCaptureCompletion completion;
        bool done=false;
        for(int i=0;i<500 && !done;++i) {
            capture.update(); done=capture.completion(completion);
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        assert(done);
        assert(completion.ok == (fault<2 || fault==6 || fault==8));
        assert(camera_fake::liveSockets==0);
        assert(worker_fake::allocations==0);
        assert(worker_fake::captures==1 && worker_fake::encodes<=1);
        assert(camera_fake::responseIndex == (fault==1 || fault==6 ? 3 : fault==7 || fault==8 ? 4 : fault==4 || fault==5 ? 1 : 2));
        // Missing WS ACK does not retain the camera gate. A new capture can be cancelled.
        assert(capture.start("22222222-2222-4222-8222-222222222222",80,10000)==CommandTargetResult::Success);
        assert(capture.cancel("22222222-2222-4222-8222-222222222222"));
        capture.acknowledgeCompletion(id);
        assert(!capture.completion(completion));
    }
}
