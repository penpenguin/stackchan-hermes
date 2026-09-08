#pragma once
#include <algorithm>
#include <atomic>
#include <vector>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <string>
#include <sys/socket.h>
#include <sys/select.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <unistd.h>
#include <fcntl.h>
#include <cstdarg>

using ip_addr_t = in_addr;
using err_t = int;
constexpr int ERR_OK = 0, ERR_INPROGRESS = -5, LWIP_DNS_ADDRTYPE_IPV4 = 0;
constexpr int ESP_TLS_ERR_SSL_WANT_READ = -10, ESP_TLS_ERR_SSL_WANT_WRITE = -11;
enum esp_tls_conn_state_t { ESP_TLS_INIT, ESP_TLS_CONNECTING, ESP_TLS_HANDSHAKE, ESP_TLS_FAIL, ESP_TLS_DONE };
struct esp_tls_t {
    esp_tls_conn_state_t conn_state = ESP_TLS_INIT;
    int sockfd = -1;
    fd_set rset{}, wset{};
};
struct esp_tls_cfg_t { bool non_block = false; int timeout_ms = 0; int (*crt_bundle_attach)(void*) = nullptr; const char* common_name = nullptr; };
namespace camera_fake {
inline std::atomic<std::uint64_t> now{0};
inline bool stallDns = false, stallConnect = false, stallSend = false, zeroSend = false, stallResponse = false;
inline bool failTask = false, failTls = false;
inline int liveSockets = 0, waits = 0, taskCreates = 0;
inline unsigned connectReadyAt = 0, tlsPolls = 0, emptyTlsPolls = 0;
inline unsigned handshakePolls = 0;
inline bool rejectHandshake = false;
inline std::string verifiedHostname;
inline std::string response, receivedWrites;
inline std::vector<std::string> responses;
inline std::size_t responseIndex = 0;

inline std::size_t responseOffset = 0;
inline void nextResponse() { responseOffset = 0; if (responseIndex < responses.size()) response = responses[responseIndex++]; }
inline void (*dnsCallback)(const char*, const ip_addr_t*, void*) = nullptr;
inline void* dnsArgument = nullptr;
inline void reset() {
    now = 0; stallDns = stallConnect = stallSend = zeroSend = stallResponse = failTask = failTls = false;
    responses.clear(); responseIndex = 0;
    connectReadyAt = tlsPolls = emptyTlsPolls = handshakePolls = 0;
    rejectHandshake = false; verifiedHostname.clear();
    liveSockets = waits = taskCreates = 0; response.clear(); receivedWrites.clear(); responseOffset = 0;
}
}
inline std::int64_t esp_timer_get_time() { return camera_fake::now * 1000; }
inline int fake_socket(int, int, int) { ++camera_fake::liveSockets; camera_fake::nextResponse(); return 4; }
inline int fake_close(int) { --camera_fake::liveSockets; return 0; }
inline int fake_fcntl(int, int, ...) { return 0; }
inline int fake_connect(int, const sockaddr*, socklen_t) { if(camera_fake::stallConnect) { errno=EINPROGRESS; return -1; } return 0; }
inline int fake_select(int, fd_set*, fd_set*, fd_set*, timeval*) { return camera_fake::stallConnect ? 0 : 1; }
inline int fake_getsockopt(int,int,int,void* value,socklen_t*) { *static_cast<int*>(value)=0; return 0; }
inline int fake_send(int, const void* data, std::size_t size, int) {
    if(camera_fake::zeroSend) return 0;
    if(camera_fake::stallSend) { errno=EAGAIN; return -1; }
    const auto count=std::min<std::size_t>(3,size);
    camera_fake::receivedWrites.append(static_cast<const char*>(data),count);
    return count;
}
inline int fake_recv(int, void* data, std::size_t size, int) {
    if(camera_fake::stallResponse) { errno=EAGAIN; return -1; }
    const auto count=std::min(size,camera_fake::response.size()-camera_fake::responseOffset);
    std::memcpy(data,camera_fake::response.data()+camera_fake::responseOffset,count);
    camera_fake::responseOffset+=count;
    return count;
}
inline hostent* fake_gethostbyname(const char*) {
    static char address[4]={127,0,0,1}; static char* addresses[]={address,nullptr};
    static hostent result{nullptr,nullptr,AF_INET,4,addresses}; return &result;
}
inline esp_tls_t* esp_tls_init() { if(camera_fake::failTls) return nullptr; ++camera_fake::liveSockets; camera_fake::nextResponse(); return new esp_tls_t; }
using esp_err_t=int;
using esp_tls_error_handle_t=void*;
constexpr int ESP_OK=0;
#define ESP_ERROR_CHECK(value) ((void)(value))
inline int esp_tls_conn_new_sync(const char*,int,int,const esp_tls_cfg_t*,esp_tls_t*) { return 1; }
inline int esp_tls_get_error_handle(esp_tls_t*,esp_tls_error_handle_t*) { return -1; }
inline int esp_tls_get_and_clear_last_error(esp_tls_error_handle_t,int*,int*) { return -1; }
inline int esp_tls_get_conn_sockfd(esp_tls_t*,int* fd) { *fd=-1; return 0; }
inline int esp_tls_conn_destroy(esp_tls_t* tls) { delete tls; --camera_fake::liveSockets; return 0; }
inline int esp_crt_bundle_attach(void*) { return 0; }
inline int esp_tls_conn_new_async(const char*,int,int,const esp_tls_cfg_t* cfg,esp_tls_t* tls) {
    if(!cfg->non_block || !cfg->common_name || !cfg->crt_bundle_attach || cfg->timeout_ms<=0) std::abort();
    camera_fake::verifiedHostname = cfg->common_name;
    if (tls->conn_state == ESP_TLS_INIT) {
        tls->sockfd = 4;
        FD_ZERO(&tls->rset); FD_SET(tls->sockfd, &tls->rset);
        tls->wset = tls->rset;
        tls->conn_state = ESP_TLS_CONNECTING;
    }
    if (tls->conn_state == ESP_TLS_CONNECTING) {
        ++camera_fake::tlsPolls;
        const bool watched = FD_ISSET(tls->sockfd, &tls->rset) || FD_ISSET(tls->sockfd, &tls->wset);
        if (!watched) ++camera_fake::emptyTlsPolls;
        if (!watched || camera_fake::stallConnect || camera_fake::now < camera_fake::connectReadyAt) {
            // Model IDF 5.5.4: select() clears its input sets on timeout and the SDK
            // initializes them only in ESP_TLS_INIT, not the next CONNECTING poll.
            FD_ZERO(&tls->rset); FD_ZERO(&tls->wset);
            camera_fake::now += cfg->timeout_ms;
            return 0;
        }
        tls->conn_state = ESP_TLS_HANDSHAKE;
    }
    ++camera_fake::handshakePolls;
    if (camera_fake::rejectHandshake) { tls->conn_state = ESP_TLS_FAIL; return -1; }
    tls->conn_state = ESP_TLS_DONE;
    return 1;
}
inline int esp_tls_conn_write(esp_tls_t*,const void* data,std::size_t size) { return camera_fake::stallSend?ESP_TLS_ERR_SSL_WANT_WRITE:fake_send(4,data,size,0); }
inline int esp_tls_conn_read(esp_tls_t*,void* data,std::size_t size) { return camera_fake::stallResponse?ESP_TLS_ERR_SSL_WANT_READ:fake_recv(4,data,size,0); }
inline int ipaddr_aton(const char* value,ip_addr_t* address) { return inet_aton(value,address); }
inline char* ipaddr_ntoa_r(const ip_addr_t* address,char* value,int size) { return const_cast<char*>(inet_ntop(AF_INET,address,value,size)); }
inline ip_addr_t* ip_2_ip4(ip_addr_t* value) { return value; }
inline std::uint32_t ip4_addr_get_u32(const ip_addr_t* value) { return value->s_addr; }
inline err_t tcpip_try_callback(void(*callback)(void*),void* argument) { callback(argument); return ERR_OK; }
inline err_t dns_gethostbyname_addrtype(const char*,ip_addr_t* address,void(*callback)(const char*,const ip_addr_t*,void*),void* argument,int) {
    if(camera_fake::stallDns) { camera_fake::dnsCallback=callback; camera_fake::dnsArgument=argument; return ERR_INPROGRESS; }
    inet_aton("127.0.0.1",address); return ERR_OK;
}
using TickType_t=unsigned;
using BaseType_t=int;
using TaskHandle_t=void*;
constexpr int pdFALSE=0,pdTRUE=1,pdPASS=1;
constexpr unsigned BIT0=1, BIT1=2;
#define pdMS_TO_TICKS(ms) (ms)
inline void vTaskDelay(unsigned ticks) { camera_fake::now+=std::max(1u,ticks); }
inline void vTaskDelete(void*) {}
inline int xTaskCreate(void(*)(void*),const char*,unsigned,void*,int,TaskHandle_t*) { ++camera_fake::taskCreates; return camera_fake::failTask ? 0 : pdPASS; }
using EventBits_t=unsigned;
using EventGroupHandle_t=unsigned*;
inline EventGroupHandle_t xEventGroupCreate() { return new unsigned(0); }
inline void vEventGroupDelete(EventGroupHandle_t event) { delete event; }
inline unsigned xEventGroupSetBits(EventGroupHandle_t event,unsigned bits) { return *event|=bits; }
inline unsigned xEventGroupClearBits(EventGroupHandle_t event,unsigned bits) { auto old=*event; *event&=~bits; return old; }
inline unsigned xEventGroupWaitBits(EventGroupHandle_t event,unsigned,bool,bool,unsigned) { ++camera_fake::waits; return *event; }
#define socket fake_socket
#define close fake_close
#define fcntl fake_fcntl
#define connect fake_connect
#define select fake_select
#define getsockopt fake_getsockopt
#define send fake_send
#define recv fake_recv
#define gethostbyname fake_gethostbyname
