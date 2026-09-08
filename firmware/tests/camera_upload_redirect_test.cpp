#include <cassert>
#include <memory>
#include <string>
#include <vector>
#include <http_client.h>
#include <network_interface.h>
#include <stackchan_bridge_client/camera_capture.h>
#include "stackchan_bridge_camera_upload.h"

namespace {
struct Destination { std::string host; int port; };

class RecordingTcp final : public Tcp {
public:
    explicit RecordingTcp(std::vector<Destination>& destinations) : destinations_(destinations) {}
    bool Connect(const std::string& host, int port) override {
        destinations_.push_back({host, port});
        return true;
    }
    void Disconnect() override {}
    int GetLastError() override { return 0; }
    int Send(const std::string& data) override {
        bytes += data;
        return static_cast<int>(data.size());
    }
    void respond(int status) {
        stream_callback_("HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 " + std::to_string(status) + " Response\r\n"
                         "Location: https://other.example.test:9443/stolen\r\n"
                         "Content-Length: 0\r\n\r\n");
    }
    std::string bytes;
private:
    std::vector<Destination>& destinations_;
};

class RecordingNetwork final : public NetworkInterface {
public:
    std::unique_ptr<Tcp> CreateTcp(int) override {
        auto socket = std::make_unique<RecordingTcp>(destinations);
        tcp = socket.get();
        return socket;
    }
    std::unique_ptr<Tcp> CreateSsl(int id) override { return CreateTcp(id); }
    RecordingTcp* tcp = nullptr;
    std::vector<Destination> destinations;
};
}

int main()
{
    using namespace stackchan::bridge_client;
    for (const auto* bridge : {"ws://192.168.2.1:8765/v1/device/ws",
                               "wss://configured.example.test:8443/v1/device/ws"}) {
        for (int status : {201, 301, 302, 303, 307, 308}) {
            RecordingNetwork network;
            stackchan::hermes::OfficialCameraUploadTransport transport(
                std::make_unique<HttpClient>(&network, 3));
            std::string url;
            assert(resolveCaptureUploadUrl(bridge, "12345678-1234-1234-1234-123456789abc", url));
            CameraMultipartUpload upload(transport);
            assert(upload.begin(url, "test-device-token", "sim-001") == CameraUploadError::None);
            const uint8_t jpeg[] = {0xff, 0xd8, 0xff, 0x00, 0xff, 0xd9};
            assert(upload.writeJpegChunk(jpeg, sizeof(jpeg)) == CameraUploadError::None);
            network.tcp->respond(status);
            assert(upload.finish() == (status == 201 ? CameraUploadError::None : CameraUploadError::Rejected));
            assert(network.destinations.size() == 1);
            const bool secure = std::string(bridge).rfind("wss://", 0) == 0;
            assert(network.destinations[0].host == (secure ? "configured.example.test" : "192.168.2.1"));
            assert(network.destinations[0].port == (secure ? 8443 : 8765));
            assert(network.tcp->bytes.find("Authorization: Bearer test-device-token\r\n") != std::string::npos);
            assert(network.tcp->bytes.find(std::string(reinterpret_cast<const char*>(jpeg), sizeof(jpeg))) != std::string::npos);
        }
    }
}
