#include "platform.h"
#include "capture_network.h"
#include <cassert>
#include <http_client.h>
using namespace stackchan::hermes;
WebSocket::~WebSocket() = default;
int main() {
    for (bool secure : {false,true}) {
        camera_fake::reset();
        auto context=std::make_shared<CaptureIoContext>(); context->deadlineMs=100;
        CaptureNetwork network(context);
        auto socket=secure?network.CreateSsl():network.CreateTcp();
        assert(socket->Connect("127.0.0.1",80));
        std::string received; socket->OnStream([&](const std::string& data){received+=data;});
        camera_fake::response="HTTP/1.1 201 Created\r\nContent-Length: 2\r\n\r\n{}";
        assert(socket->Send("payload")==7);
        assert(socket->Send("0\r\n\r\n")==5);
        assert(received==camera_fake::response);
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
    socket.reset();
    camera_fake::dnsCallback(nullptr,nullptr,camera_fake::dnsArgument); // Late callback owns no socket.
    assert(camera_fake::liveSockets==0);
}
