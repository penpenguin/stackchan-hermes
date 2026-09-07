#pragma once

#include <cstdint>
#include <string>

namespace stackchan::bridge_client {

inline constexpr std::size_t kMaxJsonBytes = 16384;

enum class ProtocolError {
    None,
    InvalidArgument,
    MessageTooLarge,
};

struct EnvelopeMetadata {
    std::string messageId;
    std::uint64_t sentAtMs = 0;
};

struct Capabilities {
    bool microphone = false;
    bool speaker    = false;
    bool camera     = false;
    bool touch      = false;
    bool head       = false;
    bool display    = false;
    bool avatar     = false;
    std::uint16_t ledCount = 0;
};

struct AudioFormat {
    std::string codec;
    std::uint32_t sampleRate = 0;
    std::uint8_t channels    = 0;
    std::uint8_t frameMs     = 0;
};

struct HelloPayload {
    std::string deviceId;
    std::string deviceName;
    std::string firmwareVersion;
    std::string hardwareModel;
    Capabilities capabilities;
    AudioFormat audio;
};

struct HelloAck {
    std::string connectionId;
    std::uint8_t selectedProtocolVersion = 0;
    std::uint32_t heartbeatIntervalMs    = 0;
    std::uint32_t maxCommandTimeoutMs    = 0;
    std::string serverVersion;
};

ProtocolError buildHelloJson(
    const EnvelopeMetadata& envelope,
    const HelloPayload& hello,
    std::string& output
);

ProtocolError parseHelloAckJson(const std::string& input, HelloAck& output);

}  // namespace stackchan::bridge_client
