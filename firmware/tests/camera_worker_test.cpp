#include "platform.h"
#include "stackchan_bridge_camera.h"
#include "board/stackchan_camera.h"
#include <board.h>
#include <esp_heap_caps.h>
#include <cassert>
#include <chrono>
#include <thread>
using namespace stackchan::hermes;
using stackchan::bridge_client::CommandTargetResult;
WebSocket::~WebSocket() = default;
StackChanCamera::StackChanCamera(const esp_video_init_config_t&) {}
StackChanCamera::~StackChanCamera() { heap_caps_free(frame_.data); }
bool StackChanCamera::Capture() { return Capture(10000,nullptr); }
bool StackChanCamera::Capture(std::uint64_t,const std::atomic<bool>*) {
    ++worker_fake::captures;
    heap_caps_free(frame_.data);
    frame_.data=static_cast<std::uint8_t*>(heap_caps_malloc(320*240*2,1));
    frame_.len=320*240*2; frame_.width=320; frame_.height=240;
    return frame_.data != nullptr;
}
bool StackChanCamera::SetHMirror(bool) { return true; }
bool StackChanCamera::SetVFlip(bool) { return true; }
std::string response(int status,const std::string& body) {
    return "HTTP/1.1 " + std::to_string(status) + " Response\r\nContent-Length: " + std::to_string(body.size()) + "\r\n\r\n" + body;
}
int main() {
    const std::string id="11111111-1111-4111-8111-111111111111";
    const auto reserved=response(200,R"({"state":"reserved","remaining_ms":10000})");
    const auto saved=response(200,"{\"state\":\"image_saved\",\"remaining_ms\":9000,\"sha256\":\"" + std::string(64,'0') + "\",\"size_bytes\":6}");
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
