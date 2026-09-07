// Modified from 78/esp-ml307 3.6.5 src/web_socket.cc (Apache-2.0).
// Changes: bound handshake/frame accumulation, validate the RFC handshake response, and reject
// oversized messages from headers; use system randomness for handshake keys and frame masks;
// clear handshake event bits before every new connection attempt; notify heartbeat pong observers.
// License: third_party/esp-ml307-LICENSE.

#include <web_socket.h>

#include <algorithm>
#include <cstring>
#include <utility>

#include <esp_log.h>
#include <esp_random.h>
#include <network_interface.h>
#include <stackchan_bridge_client/websocket_handshake.h>
#include <stackchan_bridge_client/websocket_frame_limits.h>
#include <stackchan_bridge_client/websocket_pong.h>

namespace {

constexpr char kTag[] = "WebSocket";

std::string base64Encode(const unsigned char* data, std::size_t size)
{
    constexpr char alphabet[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string encoded;
    unsigned char input[3]{};
    unsigned char output[4]{};
    std::size_t offset = 0;
    while (offset < size) {
        const std::size_t chunkSize = std::min<std::size_t>(3, size - offset);
        for (std::size_t index = 0; index < 3; ++index) {
            input[index] = index < chunkSize ? data[offset + index] : 0;
        }
        output[0] = (input[0] & 0xFCU) >> 2U;
        output[1] = ((input[0] & 0x03U) << 4U) | ((input[1] & 0xF0U) >> 4U);
        output[2] = ((input[1] & 0x0FU) << 2U) | ((input[2] & 0xC0U) >> 6U);
        output[3] = input[2] & 0x3FU;
        for (std::size_t index = 0; index < 4; ++index) {
            encoded.push_back(index <= chunkSize ? alphabet[output[index]] : '=');
        }
        offset += chunkSize;
    }
    return encoded;
}

}  // namespace

WebSocket::WebSocket(NetworkInterface* network, int connectId)
    : network_(network), connect_id_(connectId)
{
    handshake_event_group_ = xEventGroupCreate();
}

WebSocket::~WebSocket()
{
    stackchan::bridge_client::clearWebSocketPongCallback(this);
    if (tcp_) {
        tcp_->Disconnect();
    }
    if (handshake_event_group_) {
        vEventGroupDelete(handshake_event_group_);
    }
}

void WebSocket::SetHeader(const char* key, const char* value)
{
    headers_[key] = value;
}

void WebSocket::SetReceiveBufferSize(std::size_t size)
{
    receive_buffer_size_ = size;
}

bool WebSocket::IsConnected() const
{
    return connected_;
}

bool WebSocket::Connect(const char* uri)
{
    if (uri == nullptr || receive_buffer_size_ == 0) {
        return false;
    }
    const std::string uriValue(uri);
    const std::size_t schemeEnd = uriValue.find("://");
    if (schemeEnd == std::string::npos) {
        ESP_LOGE(kTag, "Invalid URI format");
        return false;
    }
    const std::string protocol = uriValue.substr(0, schemeEnd);
    const std::size_t hostStart = schemeEnd + 3;
    const std::size_t pathStart = uriValue.find('/', hostStart);
    const std::string authority = uriValue.substr(hostStart, pathStart - hostStart);
    const std::string path = pathStart == std::string::npos ? "/" : uriValue.substr(pathStart);
    const std::size_t portSeparator = authority.rfind(':');
    const std::string host = portSeparator == std::string::npos
        ? authority
        : authority.substr(0, portSeparator);
    const std::string port = portSeparator == std::string::npos
        ? (protocol == "wss" ? "443" : "80")
        : authority.substr(portSeparator + 1);
    if (host.empty() || port.empty()) {
        return false;
    }

    SetHeader("Upgrade", "websocket");
    SetHeader("Connection", "Upgrade");
    SetHeader("Sec-WebSocket-Version", "13");
    unsigned char randomKey[16]{};
    esp_fill_random(randomKey, sizeof(randomKey));
    const std::string encodedKey = base64Encode(randomKey, sizeof(randomKey));
    SetHeader("Sec-WebSocket-Key", encodedKey.c_str());

    tcp_ = protocol == "wss" || protocol == "https"
        ? network_->CreateSsl(connect_id_)
        : network_->CreateTcp(connect_id_);
    if (!tcp_) {
        return false;
    }
    connected_ = false;
    handshake_completed_ = false;
    xEventGroupClearBits(handshake_event_group_, HANDSHAKE_SUCCESS_BIT | HANDSHAKE_FAILED_BIT);
    receive_buffer_.clear();
    current_message_.clear();
    is_fragmented_ = false;
    tcp_->OnStream([this](const std::string& data) {
        OnTcpData(data);
    });
    tcp_->OnDisconnected([this]() {
        const bool wasConnected = connected_;
        connected_ = false;
        if (wasConnected && on_disconnected_) {
            on_disconnected_();
        }
    });
    if (!tcp_->Connect(host, std::stoi(port))) {
        ESP_LOGE(kTag, "Failed to connect to server");
        return false;
    }

    std::string request = "GET " + path + " HTTP/1.1\r\n";
    if (headers_.find("Host") == headers_.end()) {
        request += "Host: " + host + "\r\n";
    }
    for (const auto& [name, value] : headers_) {
        request += name + ": " + value + "\r\n";
    }
    request += "\r\n";
    if (tcp_->Send(request) < 0) {
        ESP_LOGE(kTag, "Failed to send WebSocket handshake request");
        return false;
    }

    const EventBits_t bits = xEventGroupWaitBits(
        handshake_event_group_,
        HANDSHAKE_SUCCESS_BIT | HANDSHAKE_FAILED_BIT,
        pdFALSE,
        pdFALSE,
        pdMS_TO_TICKS(10'000)
    );
    if ((bits & HANDSHAKE_SUCCESS_BIT) != 0) {
        connected_ = true;
        if (on_connected_) {
            on_connected_();
        }
        return true;
    }
    ESP_LOGE(kTag, "WebSocket handshake failed or timed out");
    return false;
}

bool WebSocket::Send(const std::string& data)
{
    return Send(data.data(), data.size(), false);
}

bool WebSocket::Send(const void* data, std::size_t size, bool binary, bool final)
{
    if (!tcp_ || data == nullptr || size > 65'535) {
        return false;
    }
    std::string frame;
    frame.reserve(size + 8);
    std::uint8_t firstByte = final ? 0x80U : 0x00U;
    firstByte |= binary ? 0x02U : (continuation_ ? 0x00U : 0x01U);
    frame.push_back(static_cast<char>(firstByte));
    if (size < 126) {
        frame.push_back(static_cast<char>(0x80U | size));
    } else {
        frame.push_back(static_cast<char>(0x80U | 126U));
        frame.push_back(static_cast<char>((size >> 8U) & 0xFFU));
        frame.push_back(static_cast<char>(size & 0xFFU));
    }
    std::uint8_t mask[4]{};
    esp_fill_random(mask, sizeof(mask));
    frame.append(reinterpret_cast<const char*>(mask), sizeof(mask));
    const auto* payload = static_cast<const std::uint8_t*>(data);
    for (std::size_t index = 0; index < size; ++index) {
        frame.push_back(static_cast<char>(payload[index] ^ mask[index % 4]));
    }
    continuation_ = !final;
    std::lock_guard<std::mutex> lock(send_mutex_);
    return tcp_->Send(frame) >= 0;
}

void WebSocket::Ping()
{
    SendControlFrame(0x09U, nullptr, 0);
}

void WebSocket::Close()
{
    xEventGroupSetBits(handshake_event_group_, HANDSHAKE_FAILED_BIT);
    if (connected_) {
        SendControlFrame(0x08U, nullptr, 0);
    }
}

void WebSocket::OnConnected(std::function<void()> callback)
{
    on_connected_ = std::move(callback);
}

void WebSocket::OnDisconnected(std::function<void()> callback)
{
    on_disconnected_ = std::move(callback);
}

void WebSocket::OnData(std::function<void(const char*, std::size_t, bool)> callback)
{
    on_data_ = std::move(callback);
}

void WebSocket::OnError(std::function<void(int)> callback)
{
    on_error_ = std::move(callback);
}

int WebSocket::GetLastError()
{
    return tcp_ ? tcp_->GetLastError() : 0;
}

void WebSocket::OnTcpData(const std::string& data)
{
    auto fail = [this](bool handshakeFailure) {
        receive_buffer_.clear();
        current_message_.clear();
        is_fragmented_ = false;
        connected_ = false;
        if (handshakeFailure) {
            xEventGroupSetBits(handshake_event_group_, HANDSHAKE_FAILED_BIT);
        } else if (on_error_) {
            on_error_(-1);
        }
    };

    std::size_t inputOffset = 0;
    while (!handshake_completed_ && inputOffset < data.size()) {
        if (receive_buffer_.size() == receive_buffer_size_) {
            fail(true);
            return;
        }
        receive_buffer_.push_back(data[inputOffset++]);
        if (receive_buffer_.size() >= 4
            && receive_buffer_.compare(receive_buffer_.size() - 4, 4, "\r\n\r\n") == 0) {
            const auto clientKey = headers_.find("Sec-WebSocket-Key");
            if (clientKey == headers_.end()
                || !stackchan::bridge_client::validateWebSocketHandshakeResponse(
                    receive_buffer_,
                    clientKey->second
                )) {
                fail(true);
                return;
            }
            receive_buffer_.clear();
            handshake_completed_ = true;
            xEventGroupSetBits(handshake_event_group_, HANDSHAKE_SUCCESS_BIT);
        }
    }
    if (!handshake_completed_) {
        return;
    }

    while (inputOffset < data.size() || !receive_buffer_.empty()) {
        while (receive_buffer_.size() < 2 && inputOffset < data.size()) {
            receive_buffer_.push_back(data[inputOffset++]);
        }
        if (receive_buffer_.size() < 2) {
            return;
        }
        const std::uint8_t encodedLength =
            static_cast<std::uint8_t>(receive_buffer_[1]) & 0x7FU;
        const std::size_t requiredHeaderBytes = encodedLength == 126U
            ? 4
            : (encodedLength == 127U ? 10 : 2);
        while (receive_buffer_.size() < requiredHeaderBytes && inputOffset < data.size()) {
            receive_buffer_.push_back(data[inputOffset++]);
        }
        if (receive_buffer_.size() < requiredHeaderBytes) {
            return;
        }

        const auto* header = reinterpret_cast<const std::uint8_t*>(receive_buffer_.data());
        const std::uint8_t opcode = header[0] & 0x0FU;
        if ((opcode == 0x00U && !is_fragmented_)
            || ((opcode == 0x01U || opcode == 0x02U) && is_fragmented_)) {
            fail(false);
            return;
        }
        const bool dataFrame = opcode <= 0x02U;
        const std::size_t remainingMessageBytes = dataFrame
            ? receive_buffer_size_ - current_message_.size()
            : receive_buffer_size_;
        const auto frameHeader = stackchan::bridge_client::inspectWebSocketFrameHeader(
            header,
            receive_buffer_.size(),
            remainingMessageBytes
        );
        if (frameHeader.status
            != stackchan::bridge_client::WebSocketFrameHeaderStatus::Complete) {
            fail(false);
            return;
        }
        const std::size_t frameBytes = frameHeader.headerBytes
            + static_cast<std::size_t>(frameHeader.payloadBytes);
        while (receive_buffer_.size() < frameBytes && inputOffset < data.size()) {
            const std::size_t needed = frameBytes - receive_buffer_.size();
            const std::size_t available = data.size() - inputOffset;
            const std::size_t copied = std::min(needed, available);
            receive_buffer_.append(data.data() + inputOffset, copied);
            inputOffset += copied;
        }
        if (receive_buffer_.size() < frameBytes) {
            return;
        }

        const char* payload = receive_buffer_.data() + frameHeader.headerBytes;
        const std::size_t payloadBytes = static_cast<std::size_t>(frameHeader.payloadBytes);
        switch (opcode) {
            case 0x00U:
                current_message_.insert(
                    current_message_.end(),
                    payload,
                    payload + payloadBytes
                );
                if (frameHeader.final) {
                    if (on_data_) {
                        on_data_(
                            current_message_.data(),
                            current_message_.size(),
                            is_binary_
                        );
                    }
                    current_message_.clear();
                    is_fragmented_ = false;
                }
                break;
            case 0x01U:
            case 0x02U:
                is_binary_ = opcode == 0x02U;
                if (frameHeader.final) {
                    if (on_data_) {
                        on_data_(payload, payloadBytes, is_binary_);
                    }
                } else {
                    current_message_.assign(payload, payload + payloadBytes);
                    is_fragmented_ = true;
                }
                break;
            case 0x08U:
                connected_ = false;
                if (on_disconnected_) {
                    on_disconnected_();
                }
                break;
            case 0x09U:
                SendControlFrame(0x0AU, payload, payloadBytes);
                break;
            case 0x0AU:
                if (payloadBytes == 0) {
                    stackchan::bridge_client::notifyWebSocketPong(this);
                }
                break;
            default:
                fail(false);
                return;
        }
        receive_buffer_.clear();
    }
}

bool WebSocket::SendControlFrame(
    std::uint8_t opcode,
    const void* data,
    std::size_t size
)
{
    if (!tcp_ || size > 125 || (data == nullptr && size != 0)) {
        return false;
    }
    std::string frame;
    frame.reserve(size + 6);
    frame.push_back(static_cast<char>(0x80U | opcode));
    frame.push_back(static_cast<char>(0x80U | size));
    std::uint8_t mask[4]{};
    esp_fill_random(mask, sizeof(mask));
    frame.append(reinterpret_cast<const char*>(mask), sizeof(mask));
    const auto* payload = static_cast<const std::uint8_t*>(data);
    for (std::size_t index = 0; index < size; ++index) {
        frame.push_back(static_cast<char>(payload[index] ^ mask[index % 4]));
    }
    std::lock_guard<std::mutex> lock(send_mutex_);
    return tcp_->Send(frame) >= 0;
}
