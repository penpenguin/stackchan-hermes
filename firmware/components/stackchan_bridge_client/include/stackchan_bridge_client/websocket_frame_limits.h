#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>

namespace stackchan::bridge_client {

enum class WebSocketFrameHeaderStatus {
    NeedMoreData,
    Complete,
    MessageTooLarge,
    ProtocolError,
};

struct WebSocketFrameHeader {
    WebSocketFrameHeaderStatus status = WebSocketFrameHeaderStatus::NeedMoreData;
    std::size_t headerBytes = 0;
    std::uint64_t payloadBytes = 0;
    std::uint8_t opcode = 0;
    bool final = false;
};

inline WebSocketFrameHeader inspectWebSocketFrameHeader(
    const std::uint8_t* data,
    std::size_t size,
    std::size_t remainingMessageBytes
)
{
    WebSocketFrameHeader result;
    if (data == nullptr || size < 2) {
        return result;
    }

    result.final = (data[0] & 0x80U) != 0;
    result.opcode = data[0] & 0x0FU;
    const bool reservedBitsSet = (data[0] & 0x70U) != 0;
    const bool masked = (data[1] & 0x80U) != 0;
    const bool knownOpcode = result.opcode <= 0x02U
        || result.opcode == 0x08U
        || result.opcode == 0x09U
        || result.opcode == 0x0AU;
    if (reservedBitsSet || masked || !knownOpcode) {
        result.status = WebSocketFrameHeaderStatus::ProtocolError;
        return result;
    }

    const std::uint8_t encodedLength = data[1] & 0x7FU;
    result.headerBytes = 2;
    result.payloadBytes = encodedLength;
    if (encodedLength == 126U) {
        if (size < 4) {
            return result;
        }
        result.headerBytes = 4;
        result.payloadBytes =
            (static_cast<std::uint64_t>(data[2]) << 8U) | data[3];
        if (result.payloadBytes < 126U) {
            result.status = WebSocketFrameHeaderStatus::ProtocolError;
            return result;
        }
    } else if (encodedLength == 127U) {
        if (size < 10) {
            return result;
        }
        result.headerBytes = 10;
        if ((data[2] & 0x80U) != 0) {
            result.status = WebSocketFrameHeaderStatus::ProtocolError;
            return result;
        }
        result.payloadBytes = 0;
        for (std::size_t index = 0; index < 8; ++index) {
            result.payloadBytes = (result.payloadBytes << 8U) | data[2 + index];
        }
        if (result.payloadBytes < 65'536U) {
            result.status = WebSocketFrameHeaderStatus::ProtocolError;
            return result;
        }
    }

    const bool controlFrame = result.opcode >= 0x08U;
    if (controlFrame && (!result.final || result.payloadBytes > 125U)) {
        result.status = WebSocketFrameHeaderStatus::ProtocolError;
        return result;
    }
    if (result.payloadBytes > remainingMessageBytes
        || result.payloadBytes > std::numeric_limits<std::size_t>::max()) {
        result.status = WebSocketFrameHeaderStatus::MessageTooLarge;
        return result;
    }
    result.status = WebSocketFrameHeaderStatus::Complete;
    return result;
}

}  // namespace stackchan::bridge_client
