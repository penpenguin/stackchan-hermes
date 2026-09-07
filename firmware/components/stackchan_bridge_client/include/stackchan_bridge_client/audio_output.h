#pragma once

#include <cstddef>
#include <cstdint>
#include <deque>
#include <functional>
#include <string>
#include <vector>

#include <stackchan_bridge_client/protocol.h>

namespace stackchan::bridge_client {

constexpr std::size_t kMaxAudioPacketBytes = 1275;
constexpr std::size_t kAudioOutputQueuePackets = 32;
constexpr int kPlaybackPrerollMs = 500;

struct AudioOutputStream {
    std::string turnId;
    std::string streamId;
    std::string codec;
    int sampleRate = 0;
    int channels = 0;
    int frameMs = 0;
    int expectedDurationMs = 0;
};

enum class AudioOutputEndReason {
    Completed,
    Cancelled,
    BargeIn,
    TtsError,
    DeviceError,
    Disconnect,
};

enum class AudioOutputError {
    None,
    InvalidArgument,
    InvalidState,
    PacketTooLarge,
    QueueOverflow,
    WrongStream,
};

enum class AudioOutputControlType {
    Start,
    End,
};

enum class AudioOutputParseError {
    None,
    MessageTooLarge,
    InvalidMessage,
    InvalidArgument,
};

enum class AudioBufferEventType {
    Underrun,
    Overflow,
};

enum class AudioBufferEventBuildError {
    None,
    InvalidArgument,
    MessageTooLarge,
};

struct AudioOutputControl {
    AudioOutputControlType type = AudioOutputControlType::Start;
    std::string messageId;
    AudioOutputStream stream;
    AudioOutputEndReason reason = AudioOutputEndReason::Completed;
};

AudioOutputParseError parseAudioOutputControlJson(
    const std::string& input,
    AudioOutputControl& output
);

AudioBufferEventBuildError buildAudioBufferEventJson(
    const EnvelopeMetadata& envelope,
    const std::string& deviceId,
    const std::string& streamId,
    AudioBufferEventType type,
    std::uint32_t droppedPackets,
    std::string& output
);

class AudioOutputBuffer {
public:
    explicit AudioOutputBuffer(int playbackPrerollMs = kPlaybackPrerollMs);
    AudioOutputError start(const AudioOutputStream& stream);
    AudioOutputError push(const std::uint8_t* data, std::size_t size);
    AudioOutputError finish(
        const std::string& turnId,
        const std::string& streamId,
        AudioOutputEndReason reason
    );
    AudioOutputError cancelTurn(const std::string& turnId);
    AudioOutputError acknowledgePlayback(
        const std::string& turnId,
        const std::string& streamId
    );
    bool pop(std::vector<std::uint8_t>& output);
    bool deliverNext(const std::function<bool(
        const AudioOutputStream& stream,
        const std::vector<std::uint8_t>& packet
    )>& consumer);
    void reset();

    bool isOpen() const;
    bool deliveryComplete() const;
    bool readyForPlayback() const;
    std::size_t queuedPackets() const;
    std::size_t droppedPackets() const;
    std::size_t underflowCount() const;
    const std::string& turnId() const;
    const std::string& streamId() const;

private:
    void clearContext();
    bool detectUnderflow();

    AudioOutputStream stream_;
    int playbackPrerollMs_ = kPlaybackPrerollMs;
    std::deque<std::vector<std::uint8_t>> queue_;
    std::size_t droppedPackets_ = 0;
    std::size_t underflowCount_ = 0;
    bool contextActive_ = false;
    bool open_ = false;
    bool ended_ = false;
    bool prerollSatisfied_ = false;
    bool underflowActive_ = false;
};

}  // namespace stackchan::bridge_client
