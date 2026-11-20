#include "platform.h"
#include "capture_network.h"
#include "capture_log.h"
#include <cassert>
#include <http_client.h>
#include <esp_log.h>
using namespace stackchan::hermes;
WebSocket::~WebSocket() = default;
int main() {
    const std::uint64_t start = 43;
    assert(captureLogElapsedMs(start + 120000, start) == 120000);
    assert(captureLogElapsedMs(start + UINT32_MAX, start) == UINT32_MAX);
    assert(captureLogElapsedMs(start + UINT32_MAX + 1, start) == UINT32_MAX);
    for (bool secure : {false,true}) {
        camera_fake::reset();
        auto context=std::make_shared<CaptureIoContext>(); context->deadlineMs=100;
        context->captureId = "network-test";
        context->attempt = 2;
        capture_log::lines.clear();
        CaptureNetwork network(context);
        auto socket=secure?network.CreateSsl():network.CreateTcp();
        assert(socket->Connect("127.0.0.1",80));
        std::string received; socket->OnStream([&](const std::string& data){received+=data;});
        camera_fake::response="HTTP/1.1 201 Created\r\nContent-Length: 2\r\n\r\n{}";
        assert(socket->Send("payload")==7);
        assert(socket->Send("0\r\n\r\n")==5);
        assert(received==camera_fake::response);
        assert(capture_log::contains("capture_id=network-test attempt=2 stage=response_end elapsed_ms=0 wire_bytes="
            + std::to_string(camera_fake::receivedWrites.size()) + " error=0 busy=1"));
        assert(camera_fake::liveSockets==0 && camera_fake::taskCreates==0);
        for(int fault=0;fault<4;++fault) {
            camera_fake::reset(); context->deadlineMs=100; context->cancelled=false;
            auto failed=secure?network.CreateSsl():network.CreateTcp();
            if(fault==0) camera_fake::stallConnect=true;
            bool connected=failed->Connect("127.0.0.1",80);
            if(fault==0) { assert(!connected); }
            else {
                assert(connected);
                if(fault==1) camera_fake::stallSend=true;
                if(fault==2) camera_fake::zeroSend=true;
                if(fault==3) camera_fake::stallResponse=true;
                assert(failed->Send("0\r\n\r\n")<0);
            }
            failed.reset();
            assert(camera_fake::now<=100 && camera_fake::liveSockets==0);
        }
    }
    for (unsigned delay : {2u, 8u, 24u}) {
        camera_fake::reset();
        camera_fake::connectReadyAt = delay;
        auto context = std::make_shared<CaptureIoContext>();
        context->deadlineMs = 100;
        CaptureNetwork network(context);
        auto socket = network.CreateSsl();
        assert(socket->Connect("camera.example.test", 443));
        assert(camera_fake::tlsPolls > 1 && camera_fake::emptyTlsPolls == 0);
        assert(camera_fake::now >= delay && camera_fake::now < 100);
        assert(camera_fake::handshakePolls == 1);
        assert(camera_fake::verifiedHostname == "camera.example.test");
        socket.reset();
        assert(camera_fake::liveSockets == 0);
    }
    camera_fake::reset();
    camera_fake::connectReadyAt = 8;
    camera_fake::rejectHandshake = true;
    {
        auto context = std::make_shared<CaptureIoContext>(); context->deadlineMs = 100;
        CaptureNetwork network(context);
        assert(!network.CreateSsl()->Connect("camera.example.test", 443));
        assert(camera_fake::handshakePolls == 1 && camera_fake::liveSockets == 0);
    }
    camera_fake::reset(); camera_fake::stallDns=true;
    auto context=std::make_shared<CaptureIoContext>(); context->deadlineMs=50;
    CaptureNetwork network(context);
    auto socket=network.CreateTcp();
    assert(!socket->Connect("synthetic.invalid",80));
    assert(context->error==ETIMEDOUT);
    assert(capture_log::contains("capture_id= attempt=0 stage=io_error elapsed_ms=50 wire_bytes=0 error="
        + std::to_string(ETIMEDOUT) + " busy=1"));
    socket.reset();
    camera_fake::dnsCallback(nullptr,nullptr,camera_fake::dnsArgument); // Late callback owns no socket.
    assert(camera_fake::liveSockets==0);
}
