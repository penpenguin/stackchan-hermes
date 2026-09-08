#pragma once

#include <atomic>
#include <cstdint>
#include <memory>
#include <network_interface.h>

namespace stackchan::hermes {

struct CaptureIoContext {
    std::atomic<bool> cancelled{false};
    std::atomic<std::uint64_t> deadlineMs{0};
    std::atomic<int> error{0};
    std::string captureId;
    std::uint64_t startedMs = 0;
    std::size_t wireBytes = 0;
    int attempt = 0;
};

// HTTP responses are pumped on the capture worker, with no per-upload receive task.
class CaptureNetwork final : public NetworkInterface {
public:
    explicit CaptureNetwork(std::shared_ptr<CaptureIoContext> context) : context_(std::move(context)) {}
    std::unique_ptr<Http> CreateHttp(int = -1) override;
    std::unique_ptr<Tcp> CreateTcp(int = -1) override;
    std::unique_ptr<Tcp> CreateSsl(int = -1) override;
    std::unique_ptr<Udp> CreateUdp(int = -1) override { return nullptr; }
    std::unique_ptr<Mqtt> CreateMqtt(int = -1) override { return nullptr; }
    std::unique_ptr<WebSocket> CreateWebSocket(int = -1) override { return nullptr; }
private:
    std::shared_ptr<CaptureIoContext> context_;
};

} // namespace stackchan::hermes
