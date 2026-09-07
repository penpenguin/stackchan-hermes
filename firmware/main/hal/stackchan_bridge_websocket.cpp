#include "stackchan_bridge_websocket.h"

#include <cstddef>
#include <stdexcept>
#include <utility>

#include <network_interface.h>
#include <web_socket.h>
#include <stackchan_bridge_client/websocket_pong.h>

#ifdef ESP_PLATFORM
#include <esp_pthread.h>
#endif

namespace stackchan::hermes {
namespace {

#ifdef ESP_PLATFORM
constexpr std::size_t kConnectionWorkerStackSize = 8 * 1024;

class ScopedConnectionThreadConfig {
public:
    ScopedConnectionThreadConfig()
    {
        hasPrevious_ = esp_pthread_get_cfg(&previous_) == ESP_OK;
        auto configuration = hasPrevious_ ? previous_ : esp_pthread_get_default_config();
        configuration.stack_size = kConnectionWorkerStackSize;
        configuration.inherit_cfg = false;
        configuration.thread_name = "hermes_ws_conn";
        applied_ = esp_pthread_set_cfg(&configuration) == ESP_OK;
    }

    ~ScopedConnectionThreadConfig()
    {
        if (!applied_) {
            return;
        }
        const auto configuration =
            hasPrevious_ ? previous_ : esp_pthread_get_default_config();
        (void)esp_pthread_set_cfg(&configuration);
    }

    bool applied() const
    {
        return applied_;
    }

private:
    esp_pthread_cfg_t previous_ = {};
    bool hasPrevious_ = false;
    bool applied_ = false;
};
#endif

constexpr std::size_t kMaxPendingCallbacks = 256;

}  // namespace

OfficialWebSocketTransport::OfficialWebSocketTransport(NetworkInterface& network)
    : network_(network)
{
}

OfficialWebSocketTransport::~OfficialWebSocketTransport()
{
    shuttingDown_.store(true);
    close();
    if (connectionWorker_.joinable()) {
        connectionWorker_.join();
    }
    std::shared_ptr<WebSocket> socket;
    {
        std::lock_guard<std::mutex> lock(socketMutex_);
        socket = std::move(socket_);
    }
    socket.reset();
}

void OfficialWebSocketTransport::setHeader(const std::string& name, const std::string& value)
{
    headers_[name] = value;
    const auto socket = socketSnapshot();
    if (socket) {
        socket->SetHeader(name.c_str(), value.c_str());
    }
}

void OfficialWebSocketTransport::setReceiveBufferSize(std::size_t size)
{
    receiveBufferSize_ = size;
    const auto socket = socketSnapshot();
    if (socket) {
        socket->SetReceiveBufferSize(size);
    }
}

void OfficialWebSocketTransport::onConnected(std::function<void()> callback)
{
    connectedCallback_ = std::move(callback);
}

void OfficialWebSocketTransport::onDisconnected(std::function<void()> callback)
{
    disconnectedCallback_ = std::move(callback);
}

void OfficialWebSocketTransport::onData(
    std::function<void(const char*, std::size_t, bool)> callback
)
{
    dataCallback_ = std::move(callback);
}

void OfficialWebSocketTransport::onError(std::function<void(int)> callback)
{
    errorCallback_ = std::move(callback);
}

void OfficialWebSocketTransport::onPong(std::function<void()> callback)
{
    pongCallback_ = std::move(callback);
}

bool OfficialWebSocketTransport::connect(const std::string& url)
{
    bool expected = false;
    if (!connectionRunning_.compare_exchange_strong(expected, true)) {
        return false;
    }
    if (connectionWorker_.joinable()) {
        connectionWorker_.join();
    }
    closeRequested_.store(false);

#ifdef ESP_PLATFORM
    ScopedConnectionThreadConfig threadConfig;
    if (!threadConfig.applied()) {
        connectionRunning_.store(false);
        return false;
    }
#endif

    const std::uint64_t generation = connectionGeneration_.fetch_add(1) + 1;
    ConnectionCallbacks callbacks{
        connectedCallback_,
        disconnectedCallback_,
        dataCallback_,
        errorCallback_,
        pongCallback_,
    };
    try {
        connectionWorker_ = std::thread(
            &OfficialWebSocketTransport::runConnection,
            this,
            url,
            generation,
            std::move(callbacks)
        );
    } catch (...) {
        connectionRunning_.store(false);
        return false;
    }
    return true;
}

bool OfficialWebSocketTransport::sendText(const std::string& text)
{
    const auto socket = socketSnapshot();
    return socket && socket->IsConnected() && socket->Send(text);
}

bool OfficialWebSocketTransport::sendBinary(const std::uint8_t* data, std::size_t size)
{
    const auto socket = socketSnapshot();
    return socket && socket->IsConnected() && data != nullptr && size > 0
        && socket->Send(data, size, true, true);
}

void OfficialWebSocketTransport::ping()
{
    const auto socket = socketSnapshot();
    if (socket && socket->IsConnected()) {
        socket->Ping();
    }
}

void OfficialWebSocketTransport::close()
{
    closeRequested_.store(true);
    const auto socket = socketSnapshot();
    if (socket) {
        socket->Close();
    }
}

void OfficialWebSocketTransport::poll()
{
    if (pendingCallbackOverflow_.exchange(false) && errorCallback_) {
        errorCallback_(-1);
    }
    std::deque<PendingCallback> pending;
    {
        std::lock_guard<std::mutex> lock(pendingCallbacksMutex_);
        pending.swap(pendingCallbacks_);
    }
    for (auto& entry : pending) {
        if (entry.generation != connectionGeneration_.load() || shuttingDown_.load()
            || (entry.requiresOpenConnection && closeRequested_.load())) {
            continue;
        }
        entry.callback();
    }
}

std::shared_ptr<WebSocket> OfficialWebSocketTransport::socketSnapshot()
{
    std::lock_guard<std::mutex> lock(socketMutex_);
    return socket_;
}

void OfficialWebSocketTransport::enqueueCallback(
    std::uint64_t generation,
    bool requiresOpenConnection,
    std::function<void()> callback
)
{
    if (!callback || shuttingDown_.load()) {
        return;
    }
    std::lock_guard<std::mutex> lock(pendingCallbacksMutex_);
    if (pendingCallbacks_.size() >= kMaxPendingCallbacks) {
        pendingCallbackOverflow_.store(true);
        return;
    }
    pendingCallbacks_.push_back({generation, requiresOpenConnection, std::move(callback)});
}

void OfficialWebSocketTransport::runConnection(
    std::string url,
    std::uint64_t generation,
    ConnectionCallbacks callbacks
) noexcept
{
    bool failed = false;
    try {
        std::shared_ptr<WebSocket> previous;
        {
            std::lock_guard<std::mutex> lock(socketMutex_);
            previous = std::move(socket_);
        }
        previous.reset();

        if (!closeRequested_.load() && !shuttingDown_.load()) {
            auto created = network_.CreateWebSocket(1);
            if (!created) {
                failed = true;
            } else {
                auto socket = std::shared_ptr<WebSocket>(std::move(created));
                if (!bridge_client::setWebSocketPongCallback(
                        socket.get(), [this, generation, callback = callbacks.pong]() {
                            enqueueCallback(generation, true, callback);
                        }
                    )) {
                    throw std::runtime_error("WebSocket pong observer capacity exceeded");
                }
                socket->SetReceiveBufferSize(receiveBufferSize_);
                for (const auto& [name, value] : headers_) {
                    socket->SetHeader(name.c_str(), value.c_str());
                }
                socket->OnConnected([this, generation, callback = callbacks.connected]() {
                    enqueueCallback(generation, true, callback);
                });
                socket->OnDisconnected(
                    [this, generation, callback = callbacks.disconnected]() {
                        enqueueCallback(generation, false, callback);
                    }
                );
                socket->OnData(
                    [this, generation, callback = callbacks.data](
                        const char* data,
                        std::size_t size,
                        bool binary
                    ) {
                        if (connectionGeneration_.load() != generation
                            || closeRequested_.load() || shuttingDown_.load() || !callback) {
                            return;
                        }
                        const bool nullData = data == nullptr;
                        std::string payload = nullData ? std::string{} : std::string(data, size);
                        enqueueCallback(
                            generation,
                            true,
                            [callback, payload = std::move(payload), nullData, size, binary]() {
                                callback(nullData ? nullptr : payload.data(), size, binary);
                            }
                        );
                    }
                );
                socket->OnError([this, generation, callback = callbacks.error](int error) {
                    if (callback) {
                        enqueueCallback(generation, false, [callback, error]() {
                            callback(error);
                        });
                    }
                });
                {
                    std::lock_guard<std::mutex> lock(socketMutex_);
                    socket_ = socket;
                }
                if (closeRequested_.load() || shuttingDown_.load()) {
                    socket->Close();
                } else if (!socket->Connect(url.c_str())) {
                    failed = true;
                }
                if (failed || closeRequested_.load() || shuttingDown_.load()) {
                    {
                        std::lock_guard<std::mutex> lock(socketMutex_);
                        if (socket_ == socket) {
                            socket_.reset();
                        }
                    }
                    socket.reset();
                }
            }
        }
    } catch (...) {
        failed = true;
    }

    if (failed && connectionGeneration_.load() == generation
        && !closeRequested_.load() && !shuttingDown_.load() && callbacks.error) {
        enqueueCallback(generation, true, [callback = callbacks.error]() {
            callback(-1);
        });
    }
    connectionRunning_.store(false);
}

}  // namespace stackchan::hermes
