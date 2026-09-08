#include <stackchan_bridge_client/session.h>

#include <algorithm>
#include <utility>

#include <stackchan_bridge_client/settings.h>

namespace stackchan::bridge_client {
namespace {

constexpr std::size_t kSeenMessageIdLimit = 256;
constexpr std::size_t kCommandResultCacheLimit = kSeenMessageIdLimit;
constexpr std::size_t kCommandResultCacheByteLimit = 256 * 1024;

bool isSafeHeaderValue(const std::string& value)
{
    for (unsigned char character : value) {
        if (character < 0x20 || character == 0x7F) {
            return false;
        }
    }
    return true;
}

}  // namespace

BridgeClient::BridgeClient(WebSocketTransport& transport, BridgeClientConfig config)
    : transport_(transport),
      config_(std::move(config)),
      audioOutput_(static_cast<int>(config_.audioOutputPrerollMs))
{
}

ClientError BridgeClient::initialize()
{
    BridgeEndpointSources endpoints;
    endpoints.nvsUrl = config_.bridgeUrl;
    const bool endpointIsValid = config_.bridgeUrl.empty()
        ? static_cast<bool>(config_.bridgeUrlResolver)
        : resolveBridgeEndpoint(endpoints).ok;
    if (config_.deviceToken.empty() || config_.deviceToken.size() > 512
        || !isSafeHeaderValue(config_.deviceToken)
        || !endpointIsValid
        || config_.audioInputMaxDurationMs < 1'000
        || config_.audioInputMaxDurationMs > 15'000
        || config_.audioOutputPrerollMs > kAudioOutputQueuePackets * config_.hello.audio.frameMs
        || buildHelloJson(config_.helloEnvelope, config_.hello, helloJson_) != ProtocolError::None) {
        transitionState(DeviceEvent::HardwareOrConfigFailure);
        return ClientError::InvalidConfig;
    }
    if (transitionState(DeviceEvent::InitializationSucceeded) != TransitionError::None) {
        return ClientError::InvalidState;
    }
    transport_.setReceiveBufferSize(kMaxJsonBytes);
    transport_.onConnected([this]() {
        if (!transport_.sendText(helloJson_)) {
            reconnectPending_ = true;
            transport_.close();
            return;
        }
        handshakeTimerArmed_   = true;
        handshakeTimerStarted_ = false;
    });
    transport_.onDisconnected([this]() {
        handleTransportDisconnected();
    });
    transport_.onError([this](int) {
        handleTransportDisconnected();
        transport_.close();
    });
    transport_.onPong([this]() {
        if (heartbeatTimerArmed_) {
            awaitingPong_ = false;
        }
    });
    transport_.onData([this](const char* data, std::size_t size, bool binary) {
        const DeviceState currentState = stateMachine_.state();
        if (currentState == DeviceState::ConnectingBridge) {
            if (binary || data == nullptr) {
                transport_.close();
                return;
            }
            HelloAck acknowledgement;
            if (parseHelloAckJson(std::string(data, size), acknowledgement)
                    != ProtocolError::None
                || transitionState(DeviceEvent::HelloAcknowledged)
                    != TransitionError::None) {
                transport_.close();
                return;
            }
            helloAcknowledgement_ = std::move(acknowledgement);
            handshakeTimerArmed_  = false;
            handshakeTimerStarted_ = false;
            stableTimerArmed_     = true;
            stableTimerStarted_   = false;
            heartbeatTimerArmed_   = true;
            heartbeatTimerStarted_ = false;
            return;
        }
        if (currentState != DeviceState::Idle && currentState != DeviceState::Listening
            && currentState != DeviceState::Speaking) {
            return;
        }
        if (data == nullptr) {
            reportPeerError(PeerErrorCode::InvalidMessage, "Invalid protocol message");
            return;
        }
        if (binary) {
            AudioOutputError pushError;
            {
                std::lock_guard<std::mutex> lock(audioOutputMutex_);
                const std::string streamId = audioOutput_.streamId();
                pushError = audioOutput_.push(
                    reinterpret_cast<const std::uint8_t*>(data), size
                );
                if (pushError == AudioOutputError::QueueOverflow && !streamId.empty()) {
                    if (pendingOverflow_.streamId != streamId) {
                        pendingOverflow_ = {streamId, 0};
                    }
                    if (pendingOverflow_.droppedPackets < 65'535) {
                        ++pendingOverflow_.droppedPackets;
                    }
                }
            }
            if (pushError == AudioOutputError::InvalidState) {
                reportPeerError(PeerErrorCode::InvalidState, "Audio output stream is not active");
            } else if (pushError == AudioOutputError::PacketTooLarge
                       || pushError == AudioOutputError::InvalidArgument) {
                reportPeerError(PeerErrorCode::InvalidMessage, "Invalid audio output packet");
            }
            return;
        }

        const std::string text(data, size);
        std::string acknowledgedCapture;
        if (parseCameraCompletedAck(text, acknowledgedCapture)) {
            if (config_.cameraCompletedAcknowledged) { config_.cameraCompletedAcknowledged(acknowledgedCapture); }
            return;
        }
        AudioOutputControl audioControl;
        const AudioOutputParseError audioParseError =
            parseAudioOutputControlJson(text, audioControl);
        if (audioParseError == AudioOutputParseError::None) {
            if (hasSeenMessageId(audioControl.messageId)) {
                return;
            }
            rememberMessageId(audioControl.messageId);
            if (audioControl.type == AudioOutputControlType::Start) {
                if (audioInputOpen_
                    && endAudioInput(AudioInputEndReason::Silence)
                        != AudioInputError::None) {
                    return;
                }
                bool accepted = false;
                {
                    std::lock_guard<std::mutex> lock(audioOutputMutex_);
                    if (audioOutput_.start(audioControl.stream) == AudioOutputError::None) {
                        if (transitionState(DeviceEvent::PlaybackStarted)
                            != TransitionError::None) {
                            audioOutput_.reset();
                        } else {
                            recentlyCancelledAudioOutputTurnId_.clear();
                            accepted = true;
                        }
                    }
                }
                if (!accepted) {
                    reportPeerError(
                        PeerErrorCode::InvalidState,
                        "Audio output stream is already active"
                    );
                }
            } else {
                if (audioControl.stream.turnId == locallyCancelledAudioOutputTurnId_
                    && audioControl.stream.streamId == locallyCancelledAudioOutputStreamId_) {
                    // The local barge-in already flushed this stream. Its delayed end
                    // must not affect the new input or playback state.
                    return;
                }
                bool flushPlayback = false;
                {
                    std::lock_guard<std::mutex> lock(audioOutputMutex_);
                    flushPlayback = audioControl.reason != AudioOutputEndReason::Completed
                        && audioOutput_.isOpen()
                        && audioOutput_.turnId() == audioControl.stream.turnId
                        && audioOutput_.streamId() == audioControl.stream.streamId;
                }
                if (flushPlayback && config_.playbackFlushHandler) {
                    config_.playbackFlushHandler();
                }
                bool accepted = false;
                {
                    std::lock_guard<std::mutex> lock(audioOutputMutex_);
                    accepted = audioOutput_.finish(
                                   audioControl.stream.turnId,
                                   audioControl.stream.streamId,
                                   audioControl.reason
                               ) == AudioOutputError::None;
                    if (accepted && audioControl.reason == AudioOutputEndReason::Cancelled) {
                        recentlyCancelledAudioOutputTurnId_ = audioControl.stream.turnId;
                    }
                }
                if (!accepted) {
                    reportPeerError(
                        PeerErrorCode::InvalidState,
                        "Audio output stream does not match"
                    );
                } else if (audioControl.reason != AudioOutputEndReason::Completed) {
                    transitionState(DeviceEvent::PlaybackEnded);
                }
            }
            return;
        }

        RemoteErrorMessage remoteError;
        const RemoteErrorParseError remoteErrorParseError =
            parseRemoteErrorJson(text, remoteError);
        if (remoteErrorParseError == RemoteErrorParseError::None) {
            if (hasSeenMessageId(remoteError.messageId)) {
                return;
            }
            rememberMessageId(remoteError.messageId);
            if (remoteError.code == RemoteErrorCode::AudioDecodeError
                && audioInputOpen_ && remoteError.turnId == audioInputTurnId_
                && remoteError.streamId == audioInputStreamId_) {
                audioInputTurnId_.clear();
                audioInputStreamId_.clear();
                audioInputOpen_ = false;
                audioInputTimerArmed_ = false;
                audioInputTimerStarted_ = false;
                transitionState(DeviceEvent::InputEnded);
            }
            return;
        }

        Command command;
        const CommandParseError commandParseError = parseCommandJson(text, command);
        if (commandParseError != CommandParseError::None) {
            const bool invalidArgument = audioParseError == AudioOutputParseError::InvalidArgument
                || remoteErrorParseError == RemoteErrorParseError::InvalidArgument
                || commandParseError == CommandParseError::InvalidArgument;
            reportPeerError(
                invalidArgument ? PeerErrorCode::InvalidArgument
                                : PeerErrorCode::InvalidMessage,
                invalidArgument ? "Invalid protocol arguments" : "Invalid protocol message"
            );
            return;
        }
        if (!config_.commandHandler || !config_.envelopeFactory) {
            reportPeerError(PeerErrorCode::InvalidState, "Command handling is unavailable");
            return;
        }
        const auto cached = std::find_if(
            commandResultCache_.begin(),
            commandResultCache_.end(),
            [&command](const CachedCommandResult& entry) {
                return entry.command.requestId == command.requestId;
            }
        );
        if (cached != commandResultCache_.end()) {
            rememberMessageId(command.messageId);
            if (!isSameCommandRequest(cached->command, command)) {
                reportPeerError(
                    PeerErrorCode::InvalidMessage,
                    "Request ID was reused with different command content"
                );
            } else if (!transport_.sendText(cached->response)) {
                reconnectPending_ = true;
                reconnectScheduled_ = false;
                transport_.close();
            }
            return;
        }
        if (reconnectPending_ || hasSeenMessageId(command.messageId)) {
            return;
        }
        // Reserve room for the largest result before executing any side effects.
        // Never evict results while this connection can still receive retries.
        const std::size_t commandStorageBytes = text.size() + sizeof(CachedCommandResult);
        if (commandResultCache_.size() >= kCommandResultCacheLimit
            || commandResultCacheBytes_ + commandStorageBytes + kMaxJsonBytes
                > kCommandResultCacheByteLimit) {
            reportPeerError(
                PeerErrorCode::InvalidState,
                "Command replay history is full; reconnect required"
            );
            reconnectPending_ = true;
            reconnectScheduled_ = false;
            transport_.close();
            return;
        }
        rememberMessageId(command.messageId);
        CommandExecutionResult result;
        if (command.name == CommandName::SpeechCancel) {
            AudioOutputError cancelError;
            bool repeatedCancellation = false;
            {
                std::lock_guard<std::mutex> lock(audioOutputMutex_);
                cancelError = audioOutput_.cancelTurn(command.turnId);
                repeatedCancellation = cancelError == AudioOutputError::InvalidState
                    && recentlyCancelledAudioOutputTurnId_ == command.turnId;
            }
            if (cancelError != AudioOutputError::None && !repeatedCancellation) {
                result.errorCode = CommandErrorCode::InvalidState;
                result.errorMessage = "Speech turn is not active";
            } else {
                recentlyCancelledAudioOutputTurnId_.clear();
                result = config_.commandHandler(command);
                if (stateMachine_.state() == DeviceState::Speaking) {
                    transitionState(DeviceEvent::PlaybackEnded);
                }
            }
        } else {
            result = config_.commandHandler(command);
        }
        std::string response;
        if (buildCommandResultJson(
                config_.envelopeFactory(), command.requestId, result, response
            ) != CommandResultBuildError::None
            || !transport_.sendText(response)) {
            reconnectPending_ = true;
            transport_.close();
            return;
        }
        commandResultCacheBytes_ += commandStorageBytes + response.size();
        commandResultCache_.push_back({std::move(command), std::move(response)});
    });
    return ClientError::None;
}

void BridgeClient::handleTransportDisconnected()
{
    helloAcknowledgement_.reset();
    {
        std::lock_guard<std::mutex> lock(audioOutputMutex_);
        audioOutput_.reset();
        pendingUnderrun_ = {};
        pendingOverflow_ = {};
    }
    audioInputTurnId_.clear();
    audioInputStreamId_.clear();
    audioInputOpen_ = false;
    audioInputTimerArmed_ = false;
    audioInputTimerStarted_ = false;
    recentlyCancelledAudioOutputTurnId_.clear();
    locallyCancelledAudioOutputTurnId_.clear();
    locallyCancelledAudioOutputStreamId_.clear();
    stableTimerArmed_   = false;
    stableTimerStarted_ = false;
    handshakeTimerArmed_   = false;
    handshakeTimerStarted_ = false;
    heartbeatTimerArmed_   = false;
    heartbeatTimerStarted_ = false;
    invalidMessageWindow_.reset();
    awaitingPong_ = false;
    seenMessageIds_.clear();
    commandResultCache_.clear();
    commandResultCacheBytes_ = 0;
    transitionState(DeviceEvent::BridgeDisconnected);
    reconnectPending_   = true;
    reconnectScheduled_ = false;
}

ClientError BridgeClient::wifiConnected()
{
    if (stateMachine_.state() != DeviceState::ConnectingWifi) {
        return ClientError::InvalidState;
    }
    if (transitionState(DeviceEvent::WifiConnected) != TransitionError::None) {
        return ClientError::InvalidState;
    }
    transport_.setHeader("Authorization", "Bearer " + config_.deviceToken);
    transport_.setHeader("X-StackChan-Device-Id", config_.hello.deviceId);
    const ClientError resolution = resolveBridgeUrl();
    if (resolution != ClientError::None) {
        reconnectPending_ = true;
        reconnectScheduled_ = false;
        return resolution;
    }
    reconnectPending_ = false;
    reconnectScheduled_ = false;
    if (!transport_.connect(config_.bridgeUrl)) {
        reconnectPending_ = true;
        return ClientError::TransportFailure;
    }
    return ClientError::None;
}

ClientError BridgeClient::reconnect()
{
    if (stateMachine_.state() != DeviceState::ConnectingBridge) {
        return ClientError::InvalidState;
    }
    const ClientError resolution = resolveBridgeUrl();
    if (resolution != ClientError::None) {
        reconnectPending_ = true;
        return resolution;
    }
    reconnectPending_   = false;
    reconnectScheduled_ = false;
    if (!transport_.connect(config_.bridgeUrl)) {
        reconnectPending_ = true;
        return ClientError::TransportFailure;
    }
    return ClientError::None;
}

ClientError BridgeClient::resolveBridgeUrl()
{
    if (!config_.bridgeUrlResolver) {
        return config_.bridgeUrl.empty() ? ClientError::InvalidConfig : ClientError::None;
    }
    BridgeEndpointSources endpoints;
    endpoints.nvsUrl = config_.bridgeUrlResolver();
    const auto resolved = resolveBridgeEndpoint(endpoints);
    if (!resolved.ok) {
        return ClientError::TransportFailure;
    }
    const bool changed = config_.bridgeUrl != resolved.url;
    config_.bridgeUrl = resolved.url;
    if (changed && config_.bridgeUrlChanged) {
        config_.bridgeUrlChanged(config_.bridgeUrl);
    }
    return ClientError::None;
}

void BridgeClient::update(std::uint32_t nowMs)
{
    lastUpdateMs_ = nowMs;
    transport_.poll();
    sendPendingAudioBufferEvent(AudioBufferEventType::Underrun, pendingUnderrun_);
    sendPendingAudioBufferEvent(AudioBufferEventType::Overflow, pendingOverflow_);
    if (audioInputTimerArmed_) {
        if (!audioInputTimerStarted_) {
            audioInputStartedAtMs_ = nowMs;
            audioInputTimerStarted_ = true;
        } else if (nowMs - audioInputStartedAtMs_ >= config_.audioInputMaxDurationMs) {
            endAudioInput(AudioInputEndReason::MaxDuration);
        }
    }
    if (handshakeTimerArmed_) {
        if (!handshakeTimerStarted_) {
            handshakeStartedAtMs_ = nowMs;
            handshakeTimerStarted_ = true;
        } else if (nowMs - handshakeStartedAtMs_ >= 5000) {
            handshakeTimerArmed_   = false;
            handshakeTimerStarted_ = false;
            reconnectPending_      = true;
            reconnectScheduled_    = false;
            transport_.close();
        }
    }
    if (heartbeatTimerArmed_ && helloAcknowledgement_) {
        if (!heartbeatTimerStarted_) {
            lastHeartbeatAtMs_ = nowMs;
            heartbeatTimerStarted_ = true;
        } else if (awaitingPong_ && nowMs - firstUnansweredPingAtMs_ >= 45'000) {
            heartbeatTimerArmed_ = false;
            awaitingPong_ = false;
            reconnectPending_ = true;
            reconnectScheduled_ = false;
            transport_.close();
        } else if (nowMs - lastHeartbeatAtMs_ >= helloAcknowledgement_->heartbeatIntervalMs) {
            if (!awaitingPong_) {
                firstUnansweredPingAtMs_ = nowMs;
                awaitingPong_ = true;
            }
            transport_.ping();
            lastHeartbeatAtMs_ = nowMs;
        }
    }
    if (stableTimerArmed_ && helloAcknowledgement_) {
        if (!stableTimerStarted_) {
            stableStartedAtMs_ = nowMs;
            stableTimerStarted_ = true;
        } else if (nowMs - stableStartedAtMs_ >= 30000) {
            reconnectBackoff_.observeStableConnection(30);
            stableTimerArmed_   = false;
            stableTimerStarted_ = false;
        }
    }
    if (!reconnectPending_) {
        return;
    }
    if (!reconnectScheduled_) {
        reconnectDelayMs_ = reconnectBackoff_.nextDelaySeconds() * 1000;
        reconnectScheduledAtMs_ = nowMs;
        reconnectScheduled_     = true;
        return;
    }
    if (nowMs - reconnectScheduledAtMs_ < reconnectDelayMs_) {
        return;
    }
    reconnectScheduled_ = false;
    reconnect();
}

void BridgeClient::reportPeerError(PeerErrorCode code, const char* message)
{
    bool sent = false;
    if (helloAcknowledgement_ && config_.envelopeFactory && message != nullptr) {
        std::string response;
        sent = buildPeerErrorJson(config_.envelopeFactory(), code, message, response)
                == PeerErrorBuildError::None
            && transport_.sendText(response);
    }
    const bool terminal = invalidMessageWindow_.observe(lastUpdateMs_);
    if (!sent || terminal) {
        reconnectPending_ = true;
        reconnectScheduled_ = false;
        transport_.close();
    }
}

bool BridgeClient::hasSeenMessageId(const std::string& messageId) const
{
    return std::find(seenMessageIds_.begin(), seenMessageIds_.end(), messageId)
        != seenMessageIds_.end();
}

void BridgeClient::rememberMessageId(const std::string& messageId)
{
    if (hasSeenMessageId(messageId)) {
        return;
    }
    if (seenMessageIds_.size() == kSeenMessageIdLimit) {
        seenMessageIds_.pop_front();
    }
    seenMessageIds_.push_back(messageId);
}

TransitionError BridgeClient::transitionState(DeviceEvent event)
{
    const DeviceState previous = stateMachine_.state();
    const TransitionError error = stateMachine_.transition(event);
    if (error == TransitionError::None && stateMachine_.state() != previous
        && config_.stateChanged) {
        config_.stateChanged(stateMachine_.state());
    }
    return error;
}

AudioInputError BridgeClient::beginAudioInput(
    const std::string& turnId,
    const std::string& streamId,
    AudioInputTrigger trigger
)
{
    const DeviceState currentState = stateMachine_.state();
    const bool bargeIn = currentState == DeviceState::Speaking;
    if ((currentState != DeviceState::Idle && !bargeIn) || audioInputOpen_
        || !config_.envelopeFactory) {
        return AudioInputError::InvalidState;
    }
    std::string message;
    if (buildAudioInputStartJson(
            config_.envelopeFactory(),
            turnId,
            streamId,
            trigger,
            config_.hello.audio.frameMs,
            message
        ) != AudioInputBuildError::None) {
        return AudioInputError::InvalidArgument;
    }
    if (bargeIn) {
        if (config_.playbackFlushHandler) {
            config_.playbackFlushHandler();
        }
        {
            std::lock_guard<std::mutex> lock(audioOutputMutex_);
            locallyCancelledAudioOutputTurnId_ = audioOutput_.turnId();
            locallyCancelledAudioOutputStreamId_ = audioOutput_.streamId();
            recentlyCancelledAudioOutputTurnId_ = audioOutput_.turnId();
            audioOutput_.reset();
            pendingUnderrun_ = {};
            pendingOverflow_ = {};
        }
        if (transitionState(DeviceEvent::BargeInTriggered) != TransitionError::None) {
            return AudioInputError::InvalidState;
        }
    }
    if (!transport_.sendText(message)) {
        reconnectPending_ = true;
        transport_.close();
        return AudioInputError::TransportFailure;
    }
    if (!bargeIn
        && transitionState(DeviceEvent::LocalInputAccepted) != TransitionError::None) {
        return AudioInputError::InvalidState;
    }
    audioInputTurnId_ = turnId;
    audioInputStreamId_ = streamId;
    audioInputOpen_ = true;
    audioInputTimerArmed_ = true;
    audioInputTimerStarted_ = false;
    return AudioInputError::None;
}

AudioInputError BridgeClient::sendAudioInputPacket(
    const std::uint8_t* data,
    std::size_t size
)
{
    if (!audioInputOpen_ || stateMachine_.state() != DeviceState::Listening) {
        return AudioInputError::InvalidState;
    }
    if (size > kMaxAudioPacketBytes) {
        return AudioInputError::PacketTooLarge;
    }
    if (data == nullptr || size == 0) {
        return AudioInputError::InvalidArgument;
    }
    if (!transport_.sendBinary(data, size)) {
        reconnectPending_ = true;
        transport_.close();
        return AudioInputError::TransportFailure;
    }
    return AudioInputError::None;
}

AudioInputError BridgeClient::endAudioInput(AudioInputEndReason reason)
{
    if (!audioInputOpen_ || stateMachine_.state() != DeviceState::Listening
        || !config_.envelopeFactory) {
        return AudioInputError::InvalidState;
    }
    std::string message;
    if (buildAudioInputEndJson(
            config_.envelopeFactory(),
            audioInputTurnId_,
            audioInputStreamId_,
            reason,
            message
        ) != AudioInputBuildError::None) {
        return AudioInputError::InvalidArgument;
    }
    if (!transport_.sendText(message)) {
        reconnectPending_ = true;
        transport_.close();
        return AudioInputError::TransportFailure;
    }
    audioInputTurnId_.clear();
    audioInputStreamId_.clear();
    audioInputOpen_ = false;
    audioInputTimerArmed_ = false;
    audioInputTimerStarted_ = false;
    if (transitionState(DeviceEvent::InputEnded) != TransitionError::None) {
        return AudioInputError::InvalidState;
    }
    return AudioInputError::None;
}

ClientError BridgeClient::sendTouchTap(int x, int y)
{
    const DeviceState currentState = stateMachine_.state();
    if ((currentState != DeviceState::Idle && currentState != DeviceState::Listening
         && currentState != DeviceState::Speaking)
        || !helloAcknowledgement_ || !config_.envelopeFactory
        || !config_.hello.capabilities.touch) {
        return ClientError::InvalidState;
    }
    std::string message;
    if (buildTouchTapEventJson(
            config_.envelopeFactory(),
            config_.hello.deviceId,
            x,
            y,
            message
        ) != EventBuildError::None) {
        return ClientError::ProtocolFailure;
    }
    if (!transport_.sendText(message)) {
        reconnectPending_ = true;
        transport_.close();
        return ClientError::TransportFailure;
    }
    return ClientError::None;
}

ClientError BridgeClient::sendCameraCompleted(
    const std::string& captureId,
    bool ok,
    CameraCompletionError error, const std::string& digest, std::size_t sizeBytes
)
{
    const DeviceState currentState = stateMachine_.state();
    if ((currentState != DeviceState::Idle && currentState != DeviceState::Listening
         && currentState != DeviceState::Speaking)
        || !helloAcknowledgement_ || !config_.envelopeFactory) {
        return ClientError::InvalidState;
    }
    std::string message;
    if (buildCameraCompletedEventJson(
            config_.envelopeFactory(),
            config_.hello.deviceId,
            captureId,
            ok,
            error,
            message, digest, sizeBytes
        ) != CameraEventBuildError::None) {
        return ClientError::ProtocolFailure;
    }
    if (!transport_.sendText(message)) {
        reconnectPending_ = true;
        transport_.close();
        return ClientError::TransportFailure;
    }
    return ClientError::None;
}

ClientError BridgeClient::reportAudioDecodeFailure()
{
    {
        std::lock_guard<std::mutex> lock(audioOutputMutex_);
        audioOutput_.reset();
        pendingUnderrun_ = {};
        pendingOverflow_ = {};
    }
    if (stateMachine_.state() == DeviceState::Speaking) {
        transitionState(DeviceEvent::PlaybackEnded);
    }
    const DeviceState currentState = stateMachine_.state();
    if ((currentState != DeviceState::Idle && currentState != DeviceState::Listening)
        || !helloAcknowledgement_ || !config_.envelopeFactory) {
        return ClientError::InvalidState;
    }
    std::string message;
    if (buildDeviceFaultEventJson(
            config_.envelopeFactory(),
            config_.hello.deviceId,
            DeviceFaultEventType::DeviceError,
            DeviceFaultCode::AudioDecodeError,
            "Audio playback could not be decoded",
            message
        ) != EventBuildError::None) {
        return ClientError::ProtocolFailure;
    }
    if (!transport_.sendText(message)) {
        reconnectPending_ = true;
        transport_.close();
        return ClientError::TransportFailure;
    }
    return ClientError::None;
}

bool BridgeClient::popAudioOutputPacket(std::vector<std::uint8_t>& output)
{
    bool popped = false;
    {
        std::lock_guard<std::mutex> lock(audioOutputMutex_);
        popped = audioOutput_.pop(output);
    }
    if (!popped) {
        return false;
    }
    return true;
}

bool BridgeClient::deliverAudioOutputPacket(
    bool downstreamPlaybackIdle,
    const std::function<bool(
        int sampleRate,
        int frameMs,
        const std::vector<std::uint8_t>& packet
    )>& consumer
)
{
    bool delivered = false;
    {
        std::lock_guard<std::mutex> lock(audioOutputMutex_);
        const std::size_t previousUnderflows = audioOutput_.underflowCount();
        const std::string streamId = audioOutput_.streamId();
        if (downstreamPlaybackIdle || audioOutput_.queuedPackets() > 0) {
            delivered = audioOutput_.deliverNext(
                [&](const AudioOutputStream& stream, const std::vector<std::uint8_t>& packet) {
                    return consumer && consumer(stream.sampleRate, stream.frameMs, packet);
                }
            );
        }
        const std::size_t currentUnderflows = audioOutput_.underflowCount();
        if (currentUnderflows > previousUnderflows && !streamId.empty()) {
            if (pendingUnderrun_.streamId != streamId) {
                pendingUnderrun_ = {streamId, 0};
            }
            const std::size_t added = currentUnderflows - previousUnderflows;
            pendingUnderrun_.droppedPackets = static_cast<std::uint32_t>(
                std::min<std::size_t>(
                    65'535,
                    static_cast<std::size_t>(pendingUnderrun_.droppedPackets) + added
                )
            );
        }
    }
    return delivered;
}

bool BridgeClient::audioOutputDeliveryComplete() const
{
    std::lock_guard<std::mutex> lock(audioOutputMutex_);
    return audioOutput_.deliveryComplete();
}

ClientError BridgeClient::acknowledgeAudioOutputPlayback()
{
    std::lock_guard<std::mutex> lock(audioOutputMutex_);
    if (stateMachine_.state() != DeviceState::Speaking || !audioOutput_.deliveryComplete()) {
        return ClientError::InvalidState;
    }
    if (audioOutput_.acknowledgePlayback(audioOutput_.turnId(), audioOutput_.streamId())
        != AudioOutputError::None) {
        return ClientError::InvalidState;
    }
    return transitionState(DeviceEvent::PlaybackEnded) == TransitionError::None
        ? ClientError::None
        : ClientError::InvalidState;
}

void BridgeClient::sendPendingAudioBufferEvent(
    AudioBufferEventType type,
    PendingAudioBufferEvent& pending
)
{
    const DeviceState currentState = stateMachine_.state();
    if ((currentState != DeviceState::Idle && currentState != DeviceState::Listening
         && currentState != DeviceState::Speaking)
        || !helloAcknowledgement_ || !config_.envelopeFactory) {
        return;
    }
    PendingAudioBufferEvent snapshot;
    {
        std::lock_guard<std::mutex> lock(audioOutputMutex_);
        snapshot = pending;
    }
    if (snapshot.streamId.empty() || snapshot.droppedPackets == 0) {
        return;
    }
    std::string message;
    if (buildAudioBufferEventJson(
            config_.envelopeFactory(),
            config_.hello.deviceId,
            snapshot.streamId,
            type,
            snapshot.droppedPackets,
            message
        ) != AudioBufferEventBuildError::None) {
        std::lock_guard<std::mutex> lock(audioOutputMutex_);
        if (pending.streamId == snapshot.streamId) {
            pending = {};
        }
        return;
    }
    if (!transport_.sendText(message)) {
        reconnectPending_ = true;
        transport_.close();
        return;
    }
    std::lock_guard<std::mutex> lock(audioOutputMutex_);
    if (pending.streamId != snapshot.streamId) {
        return;
    }
    if (pending.droppedPackets <= snapshot.droppedPackets) {
        pending = {};
    } else {
        pending.droppedPackets -= snapshot.droppedPackets;
    }
}

std::size_t BridgeClient::droppedAudioOutputPackets() const
{
    std::lock_guard<std::mutex> lock(audioOutputMutex_);
    return audioOutput_.droppedPackets();
}

std::size_t BridgeClient::queuedAudioOutputPackets() const
{
    std::lock_guard<std::mutex> lock(audioOutputMutex_);
    return audioOutput_.queuedPackets();
}

const std::string& BridgeClient::bridgeUrl() const
{
    return config_.bridgeUrl;
}

DeviceState BridgeClient::state() const
{
    return stateMachine_.state();
}

const HelloAck* BridgeClient::helloAcknowledgement() const
{
    return helloAcknowledgement_ ? &*helloAcknowledgement_ : nullptr;
}

}  // namespace stackchan::bridge_client
