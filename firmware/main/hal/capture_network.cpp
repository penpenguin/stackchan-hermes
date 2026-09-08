#include "capture_network.h"

#include <cerrno>
#include <fcntl.h>
#include <sys/socket.h>
#include <unistd.h>
#include <esp_crt_bundle.h>
#include <esp_timer.h>
#include <esp_log.h>
#include <esp_tls.h>
#include <esp_tls_private.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <http_client.h>
#include <lwip/dns.h>
#include <lwip/tcpip.h>

namespace stackchan::hermes {
namespace {
std::uint64_t nowMs() { return esp_timer_get_time() / 1000; }
std::atomic<int> pendingDns{0};

struct DnsQuery {
    std::string host;
    ip_addr_t address{};
    std::atomic<bool> ready{false};
    bool valid = false;
};

void finishDns(void* argument, const ip_addr_t* address)
{
    auto* owner = static_cast<std::shared_ptr<DnsQuery>*>(argument);
    auto& query = **owner;
    if (address) { query.address = *address; query.valid = true; }
    query.ready.store(true);
    delete owner;
    --pendingDns;
}

class CaptureTcp final : public Tcp {
public:
    CaptureTcp(std::shared_ptr<CaptureIoContext> context, bool secure)
        : context_(std::move(context)), secure_(secure) {}
    ~CaptureTcp() override { Disconnect(); }

    bool Connect(const std::string& host, int port) override
    {
        Disconnect();
        context_->error.store(0);
        trace("dns_begin");
        ip_addr_t address{};
        if (!resolve(host, address) || expired()) { return false; }
        trace("dns_end");
        trace("connect_begin");
        char numeric[64]{};
        if (!ipaddr_ntoa_r(&address, numeric, sizeof(numeric))) { return fail(EHOSTUNREACH); }
        if (secure_) {
            tls_ = esp_tls_init();
            if (!tls_) { return fail(ENOMEM); }
            esp_tls_cfg_t configuration{};
            configuration.non_block = true;
            configuration.timeout_ms = 1;
            configuration.crt_bundle_attach = esp_crt_bundle_attach;
            configuration.common_name = host.c_str();
            int result = 0;
            while (!expired()) {
                // IDF 5.5.4 initializes these only in ESP_TLS_INIT. select() clears
                // them on timeout, so rearm the same socket before each TCP poll.
                // This uses the pinned SDK's private layout; review on SDK upgrades.
                if (tls_->conn_state == ESP_TLS_CONNECTING) {
                    FD_ZERO(&tls_->rset);
                    FD_SET(tls_->sockfd, &tls_->rset);
                    tls_->wset = tls_->rset;
                }
                result = esp_tls_conn_new_async(numeric, std::char_traits<char>::length(numeric), port, &configuration, tls_);
                if (result != 0) { break; }
                pause();
            }
            if (expired()) { Disconnect(); return false; }
            if (result != 1) { Disconnect(); return fail(ECONNREFUSED); }
        } else {
            descriptor_ = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
            if (descriptor_ < 0) { return fail(errno); }
            if (fcntl(descriptor_, F_SETFL, O_NONBLOCK) < 0) { Disconnect(); return fail(errno); }
            sockaddr_in peer{};
            peer.sin_family = AF_INET;
            peer.sin_port = htons(port);
            peer.sin_addr.s_addr = ip4_addr_get_u32(ip_2_ip4(&address));
            int result = connect(descriptor_, reinterpret_cast<sockaddr*>(&peer), sizeof(peer));
            if (result < 0 && errno != EINPROGRESS && errno != EWOULDBLOCK) {
                const int error = errno; Disconnect(); return fail(error);
            }
            while (result < 0 && !expired()) {
                fd_set writable;
                FD_ZERO(&writable); FD_SET(descriptor_, &writable);
                timeval duration{0, 1000};
                if (select(descriptor_ + 1, nullptr, &writable, nullptr, &duration) > 0) {
                    int error = 0; socklen_t length = sizeof(error);
                    if (getsockopt(descriptor_, SOL_SOCKET, SO_ERROR, &error, &length) < 0 || error) {
                        Disconnect(); return fail(error ? error : errno);
                    }
                    result = 0;
                } else { pause(); }
            }
            if (expired()) { Disconnect(); return false; }
        }
        connected_ = true;
        trace("connect_end");
        return true;
    }

    int Send(const std::string& data) override
    {
        if (!connected_) { fail(ENOTCONN); return -1; }
        std::size_t sent = 0;
        while (sent < data.size() && !expired()) {
            const int count = secure_
                ? esp_tls_conn_write(tls_, data.data() + sent, data.size() - sent)
                : send(descriptor_, data.data() + sent, data.size() - sent, 0);
            if (count > 0) { sent += count; context_->wireBytes += count; }
            else if (wouldBlock(count)) { pause(); }
            else { fail(count == 0 ? EPIPE : secure_ ? count : errno); return -1; }
        }
        if (sent != data.size() || expired()) { return -1; }
        // The HTTP client requests Connection: close. Drain only the bounded response,
        // after a GET request or the terminating chunk of a multipart upload.
        if (data.rfind("GET ", 0) == 0 || data == "0\r\n\r\n") {
            trace("response_begin");
            if (!receiveResponse()) { return -1; }
            trace("response_end");
        }
        return static_cast<int>(sent);
    }

    void Disconnect() override
    {
        const bool wasConnected = connected_;
        connected_ = false;
        if (tls_) { esp_tls_conn_destroy(tls_); tls_ = nullptr; }
        if (descriptor_ >= 0) { close(descriptor_); descriptor_ = -1; }
        if (wasConnected && disconnect_callback_) { disconnect_callback_(); }
        if (wasConnected) { trace("close"); }
    }
    int GetLastError() override { return context_->error.load(); }

private:
    bool expired()
    {
        if (context_->cancelled.load()) { return !fail(ECANCELED); }
        if (nowMs() >= context_->deadlineMs.load()) { return !fail(ETIMEDOUT); }
        return false;
    }
    bool fail(int code) { context_->error.store(code); trace("io_error"); return false; }
    void trace(const char* stage) const
    {
        ESP_LOGI("Capture", "capture_id=%s attempt=%d stage=%s elapsed_ms=%llu wire_bytes=%u error=%d busy=1",
            context_->captureId.c_str(), context_->attempt, stage,
            static_cast<unsigned long long>(nowMs() - context_->startedMs),
            static_cast<unsigned>(context_->wireBytes), context_->error.load());
    }
    void pause() { vTaskDelay(1); }
    bool wouldBlock(int result) const
    {
        return secure_ ? result == ESP_TLS_ERR_SSL_WANT_READ || result == ESP_TLS_ERR_SSL_WANT_WRITE
                       : result < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR);
    }
    bool resolve(const std::string& host, ip_addr_t& address)
    {
        if (ipaddr_aton(host.c_str(), &address)) { return true; }
        if (pendingDns.fetch_add(1) >= 4) { --pendingDns; return fail(EBUSY); }
        std::shared_ptr<DnsQuery> query;
        try {
            query = std::make_shared<DnsQuery>();
            query->host = host;
        } catch (...) { --pendingDns; return fail(ENOMEM); }
        auto* owner = new (std::nothrow) std::shared_ptr<DnsQuery>(query);
        if (!owner) { --pendingDns; return fail(ENOMEM); }
        const err_t queued = tcpip_try_callback([](void* argument) {
            auto* owner = static_cast<std::shared_ptr<DnsQuery>*>(argument);
            auto& query = **owner;
            const err_t result = dns_gethostbyname_addrtype(query.host.c_str(), &query.address,
                [](const char*, const ip_addr_t* address, void* context) { finishDns(context, address); },
                argument, LWIP_DNS_ADDRTYPE_IPV4);
            if (result != ERR_INPROGRESS) { finishDns(argument, result == ERR_OK ? &query.address : nullptr); }
        }, owner);
        if (queued != ERR_OK) { delete owner; --pendingDns; return fail(ENOMEM); }
        while (!query->ready.load() && !expired()) { pause(); }
        // A late DNS callback owns only this small bounded query, never a camera or socket.
        if (expired()) { return false; }
        if (!query->ready.load() || !query->valid) { return fail(EHOSTUNREACH); }
        address = query->address;
        return true;
    }
    bool receiveResponse()
    {
        std::size_t received = 0;
        while (!expired()) {
            char buffer[1024];
            const int count = secure_ ? esp_tls_conn_read(tls_, buffer, sizeof(buffer))
                                     : recv(descriptor_, buffer, sizeof(buffer), 0);
            if (count > 0) {
                received += count;
                if (received > 8192) { return fail(EMSGSIZE); }
                if (stream_callback_) { stream_callback_(std::string(buffer, count)); }
            } else if (count == 0) {
                Disconnect();
                return received != 0;
            } else if (wouldBlock(count)) { pause(); }
            else { return fail(secure_ ? count : errno); }
        }
        return false;
    }
    std::shared_ptr<CaptureIoContext> context_;
    bool secure_;
    int descriptor_ = -1;
    esp_tls_t* tls_ = nullptr;
};
} // namespace

std::unique_ptr<Http> CaptureNetwork::CreateHttp(int id) { return std::make_unique<HttpClient>(this, id); }
std::unique_ptr<Tcp> CaptureNetwork::CreateTcp(int) { return std::make_unique<CaptureTcp>(context_, false); }
std::unique_ptr<Tcp> CaptureNetwork::CreateSsl(int) { return std::make_unique<CaptureTcp>(context_, true); }

} // namespace stackchan::hermes
