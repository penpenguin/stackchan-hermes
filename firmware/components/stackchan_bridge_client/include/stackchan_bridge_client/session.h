#pragma once

#include <cstddef>
#include <deque>
#include <functional>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

#include <stackchan_bridge_client/audio_input.h>
#include <stackchan_bridge_client/audio_output.h>
#include <stackchan_bridge_client/camera_capture.h>
#include <stackchan_bridge_client/command.h>
#include <stackchan_bridge_client/event.h>
#include <stackchan_bridge_client/protocol.h>
#include <stackchan_bridge_client/protocol_guard.h>
#include <stackchan_bridge_client/reconnect.h>
#include <stackchan_bridge_client/state_machine.h>

namespace stackchan::bridge_client {

class WebSocketTransport {
public:
    virtual ~WebSocketTransport() = default;

    virtual void setHeader(const std::string& name, const std::string& value) = 0;
    virtual void setReceiveBufferSize(std::size_t size) = 0;
    virtual void onConnected(std::function<void()> callback) = 0;
    virtual void onDisconnected(std::function<void()> callback) = 0;
    virtual void onData(std::function<void(const char*, std::size_t, bool)> callback) = 0;
    virtual void onError(std::function<void(int)> callback) = 0;
    virtual void onPong(std::function<void()> callback) = 0;
    virtual bool connect(const std::string& url) = 0;
    virtual bool sendText(const std::string& text) = 0;
    virtual bool sendBinary(const std::uint8_t* data, std::size_t size) = 0;
    virtual void ping() = 0;
    virtual void close() = 0;
    virtual void poll() = 0;
};

struct BridgeClientConfig {
    std::string bridgeUrl;
    std::function<std::string()> bridgeUrlResolver;
    std::function<void(const std::string&)> bridgeUrlChanged;
    std::string deviceToken;
    std::uint32_t audioInputMaxDurationMs = 15'000;
    std::uint32_t audioOutputPrerollMs = 500;
    EnvelopeMetadata helloEnvelope;
    HelloPayload hello;
    std::function<CommandExecutionResult(const Command&)> commandHandler;
    std::function<EnvelopeMetadata()> envelopeFactory;
    std::function<void()> playbackFlushHandler;
    std::function<void(DeviceState)> stateChanged;
    std::function<void(const std::string&)> cameraCompletedAcknowledged;
};

enum class ClientError {
    None,
    InvalidConfig,
    InvalidState,
    TransportFailure,
    ProtocolFailure,
};

class BridgeClient {
public:
    BridgeClient(WebSocketTransport& transport, BridgeClientConfig config);

    ClientError initialize();
    ClientError wifiConnected();
    ClientError reconnect();
    void update(std::uint32_t nowMs);
    AudioInputError beginAudioInput(
        const std::string& turnId,
        const std::string& streamId,
        AudioInputTrigger trigger
    );
    AudioInputError sendAudioInputPacket(const std::uint8_t* data, std::size_t size);
    AudioInputError endAudioInput(AudioInputEndReason reason);
    ClientError sendTouchTap(int x, int y);
    ClientError sendCameraCompleted(
        const std::string& captureId,
        bool ok,
        CameraCompletionError error,
        const std::string& digest = {}, std::size_t sizeBytes = 0
    );
    ClientError reportAudioDecodeFailure();
    bool popAudioOutputPacket(std::vector<std::uint8_t>& output);
    bool deliverAudioOutputPacket(
        bool downstreamPlaybackIdle,
        const std::function<bool(
            int sampleRate,
            int frameMs,
            const std::vector<std::uint8_t>& packet
        )>& consumer
    );
    bool audioOutputDeliveryComplete() const;
    ClientError acknowledgeAudioOutputPlayback();
    std::size_t queuedAudioOutputPackets() const;
    std::size_t droppedAudioOutputPackets() const;
    const std::string& bridgeUrl() const;
    DeviceState state() const;
    const HelloAck* helloAcknowledgement() const;

private:
    struct PendingAudioBufferEvent {
        std::string streamId;
        std::uint32_t droppedPackets = 0;
    };

    struct CachedCommandResult {
        Command command;
        std::string response;
    };

    void sendPendingAudioBufferEvent(
        AudioBufferEventType type,
        PendingAudioBufferEvent& pending
    );
    void handleTransportDisconnected();
    ClientError resolveBridgeUrl();
    void reportPeerError(PeerErrorCode code, const char* message);
    TransitionError transitionState(DeviceEvent event);
    bool hasSeenMessageId(const std::string& messageId) const;
    void rememberMessageId(const std::string& messageId);

    WebSocketTransport& transport_;
    BridgeClientConfig config_;
    DeviceStateMachine stateMachine_;
    AudioOutputBuffer audioOutput_;
    mutable std::mutex audioOutputMutex_;
    PendingAudioBufferEvent pendingUnderrun_;
    PendingAudioBufferEvent pendingOverflow_;
    std::string helloJson_;
    std::optional<HelloAck> helloAcknowledgement_;
    ReconnectBackoff reconnectBackoff_;
    InvalidMessageWindow invalidMessageWindow_;
    std::deque<std::string> seenMessageIds_;
    std::deque<CachedCommandResult> commandResultCache_;
    std::size_t commandResultCacheBytes_ = 0;
    std::uint32_t lastUpdateMs_ = 0;
    bool reconnectPending_   = false;
    bool reconnectScheduled_ = false;
    std::uint32_t reconnectScheduledAtMs_ = 0;
    std::uint32_t reconnectDelayMs_       = 0;
    bool stableTimerArmed_   = false;
    bool stableTimerStarted_ = false;
    std::uint32_t stableStartedAtMs_ = 0;
    bool handshakeTimerArmed_   = false;
    bool handshakeTimerStarted_ = false;
    std::uint32_t handshakeStartedAtMs_ = 0;
    bool heartbeatTimerArmed_   = false;
    bool heartbeatTimerStarted_ = false;
    std::uint32_t lastHeartbeatAtMs_ = 0;
    bool awaitingPong_ = false;
    std::uint32_t firstUnansweredPingAtMs_ = 0;
    std::string audioInputTurnId_;
    std::string audioInputStreamId_;
    std::string recentlyCancelledAudioOutputTurnId_;
    std::string locallyCancelledAudioOutputTurnId_;
    std::string locallyCancelledAudioOutputStreamId_;
    bool audioInputOpen_ = false;
    bool audioInputTimerArmed_ = false;
    bool audioInputTimerStarted_ = false;
    std::uint32_t audioInputStartedAtMs_ = 0;
};

}  // namespace stackchan::bridge_client
