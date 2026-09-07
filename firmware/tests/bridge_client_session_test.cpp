#include <cstdlib>
#include <cstdint>
#include <functional>
#include <iostream>
#include <map>
#include <string>
#include <vector>

#include <stackchan_bridge_client/session.h>

namespace {

using stackchan::bridge_client::BridgeClient;
using stackchan::bridge_client::BridgeClientConfig;
using stackchan::bridge_client::CameraCompletionError;
using stackchan::bridge_client::ClientError;
using stackchan::bridge_client::AudioInputEndReason;
using stackchan::bridge_client::AudioInputError;
using stackchan::bridge_client::AudioInputTrigger;
using stackchan::bridge_client::Command;
using stackchan::bridge_client::CommandExecutionResult;
using stackchan::bridge_client::CommandName;
using stackchan::bridge_client::DeviceState;
using stackchan::bridge_client::EnvelopeMetadata;
using stackchan::bridge_client::WebSocketTransport;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

class FakeWebSocketTransport final : public WebSocketTransport {
public:
    void setHeader(const std::string& name, const std::string& value) override
    {
        headers[name] = value;
    }

    void setReceiveBufferSize(std::size_t size) override
    {
        receiveBufferSize = size;
    }

    void onConnected(std::function<void()> callback) override
    {
        connectedCallback = std::move(callback);
    }

    void onDisconnected(std::function<void()> callback) override
    {
        disconnectedCallback = std::move(callback);
    }

    void onData(std::function<void(const char*, std::size_t, bool)> callback) override
    {
        dataCallback = std::move(callback);
    }

    void onError(std::function<void(int)> callback) override
    {
        errorCallback = std::move(callback);
    }

    void onPong(std::function<void()> callback) override
    {
        pongCallback = std::move(callback);
    }

    bool connect(const std::string& url) override
    {
        ++connectAttempts;
        connectedUrl = url;
        if (errorDuringConnect && errorCallback) {
            errorCallback(-1);
        }
        return connectResult;
    }

    bool sendText(const std::string& text) override
    {
        sentText = text;
        sentTexts.push_back(text);
        return sendResult;
    }

    bool sendBinary(const std::uint8_t* data, std::size_t size) override
    {
        ++binarySendCount;
        sentBinary.assign(data, data + size);
        return sendBinaryResult;
    }

    void ping() override
    {
        ++pingCount;
    }

    void close() override
    {
        closed = true;
    }

    void poll() override
    {
        ++pollCount;
    }

    std::map<std::string, std::string> headers;
    std::size_t receiveBufferSize = 0;
    std::function<void()> connectedCallback;
    std::function<void()> disconnectedCallback;
    std::function<void(const char*, std::size_t, bool)> dataCallback;
    std::function<void(int)> errorCallback;
    std::function<void()> pongCallback;
    std::string connectedUrl;
    std::string sentText;
    std::vector<std::string> sentTexts;
    std::vector<std::uint8_t> sentBinary;
    std::size_t connectAttempts = 0;
    std::size_t pingCount       = 0;
    std::size_t binarySendCount = 0;
    std::size_t pollCount       = 0;
    bool connectResult = true;
    bool errorDuringConnect = false;
    bool sendResult    = true;
    bool sendBinaryResult = true;
    bool closed        = false;
};

BridgeClientConfig validConfig()
{
    BridgeClientConfig config;
    config.bridgeUrl              = "ws://192.0.2.10:8765/v1/device/ws";
    config.deviceToken            = "test-only-device-token";
    config.helloEnvelope.messageId = "123e4567-e89b-12d3-a456-426614174000";
    config.helloEnvelope.sentAtMs  = 1234;
    config.hello.deviceId          = "stackchan-001";
    config.hello.deviceName        = "StackChan";
    config.hello.firmwareVersion   = "1.5.1-hermes";
    config.hello.hardwareModel     = "M5STACK-K151";
    config.hello.capabilities.microphone = true;
    config.hello.capabilities.speaker    = true;
    config.hello.capabilities.camera     = true;
    config.hello.capabilities.touch      = true;
    config.hello.capabilities.head       = false;
    config.hello.capabilities.display    = true;
    config.hello.capabilities.avatar     = true;
    config.hello.capabilities.ledCount   = 12;
    config.hello.audio.codec              = "opus";
    config.hello.audio.sampleRate         = 16000;
    config.hello.audio.channels           = 1;
    config.hello.audio.frameMs            = 60;
    return config;
}

void testUpdatePollsTransportCallbacks()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());

    expect(client.initialize() == ClientError::None, "client initialization failed");
    client.update(123);

    expect(transport.pollCount == 1, "client update did not poll transport callbacks");
}

std::string validAcknowledgement()
{
    return R"({
        "v": 1,
        "type": "hello_ack",
        "message_id": "123e4567-e89b-12d3-a456-426614174001",
        "sent_at_ms": 1235,
        "payload": {
            "connection_id": "123e4567-e89b-12d3-a456-426614174002",
            "selected_protocol_version": 1,
            "heartbeat_interval_ms": 15000,
            "max_command_timeout_ms": 5000,
            "server_version": "0.1.0"
        }
    })";
}

void testWifiConnectedConfiguresAuthenticatedConnection()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());

    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.state() == DeviceState::ConnectingWifi, "client did not wait for Wi-Fi");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    expect(client.state() == DeviceState::ConnectingBridge, "client did not connect to Bridge");
    expect(
        transport.headers["Authorization"] == "Bearer test-only-device-token",
        "Bearer authorization header was not configured"
    );
    expect(
        transport.headers["X-StackChan-Device-Id"] == "stackchan-001",
        "device identity header was not configured"
    );
    expect(
        transport.connectedUrl == "ws://192.0.2.10:8765/v1/device/ws",
        "wrong Bridge URL was connected"
    );
}

void testWifiConnectedResolvesBridgeUrlAfterWifiIsReady()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.bridgeUrl.clear();
    int resolverCalls = 0;
    config.bridgeUrlResolver = [&]() {
        ++resolverCalls;
        return std::string("ws://discovered.local:8765/v1/device/ws");
    };
    BridgeClient client(transport, std::move(config));

    expect(client.initialize() == ClientError::None, "deferred URL config was rejected");
    expect(resolverCalls == 0, "Bridge URL was resolved before Wi-Fi was ready");
    expect(client.wifiConnected() == ClientError::None, "discovered URL was rejected");
    expect(resolverCalls == 1, "Bridge URL resolver was not called exactly once");
    expect(
        transport.connectedUrl == "ws://discovered.local:8765/v1/device/ws",
        "discovered Bridge URL was not connected"
    );
    expect(
        client.bridgeUrl() == "ws://discovered.local:8765/v1/device/ws",
        "resolved Bridge URL was not exposed to upload adapters"
    );
}

void testDiscoveryMissIsRetriedAfterBackoff()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.bridgeUrl.clear();
    int resolverCalls = 0;
    config.bridgeUrlResolver = [&]() {
        ++resolverCalls;
        return resolverCalls == 1
            ? std::string{}
            : std::string("ws://192.0.2.25:8765/v1/device/ws");
    };
    BridgeClient client(transport, std::move(config));

    expect(client.initialize() == ClientError::None, "deferred URL config was rejected");
    expect(
        client.wifiConnected() == ClientError::TransportFailure,
        "discovery miss was treated as a permanent config failure"
    );
    expect(
        client.state() == DeviceState::ConnectingBridge,
        "discovery miss left the retryable connection state"
    );
    expect(transport.connectAttempts == 0, "discovery miss opened a socket");

    client.update(0);
    client.update(999);
    expect(resolverCalls == 1, "discovery was retried before backoff elapsed");
    client.update(1000);

    expect(resolverCalls == 2, "discovery was not retried after backoff");
    expect(transport.connectAttempts == 1, "resolved retry did not open a socket");
    expect(
        transport.connectedUrl == "ws://192.0.2.25:8765/v1/device/ws",
        "resolved retry used the wrong Bridge URL"
    );
}

void testReconnectReevaluatesDiscoveryAfterAddressChange()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.bridgeUrl.clear();
    int resolverCalls = 0;
    std::vector<std::string> resolvedUrls;
    config.bridgeUrlResolver = [&]() {
        ++resolverCalls;
        return resolverCalls == 1
            ? std::string("ws://192.0.2.25:8765/v1/device/ws")
            : std::string("ws://192.0.2.26:8765/v1/device/ws");
    };
    config.bridgeUrlChanged = [&](const std::string& url) {
        resolvedUrls.push_back(url);
    };
    BridgeClient client(transport, std::move(config));

    expect(client.initialize() == ClientError::None, "deferred URL config was rejected");
    expect(client.wifiConnected() == ClientError::None, "initial discovery failed");
    expect(
        transport.connectedUrl == "ws://192.0.2.25:8765/v1/device/ws",
        "initial discovery used the wrong URL"
    );
    expect(
        resolvedUrls == std::vector<std::string>({"ws://192.0.2.25:8765/v1/device/ws"}),
        "initial discovery URL was not propagated to dependent adapters"
    );

    transport.disconnectedCallback();
    client.update(0);
    client.update(1000);

    expect(resolverCalls == 2, "reconnect reused a stale discovered URL");
    expect(
        transport.connectedUrl == "ws://192.0.2.26:8765/v1/device/ws",
        "reconnect did not use the refreshed Bridge URL"
    );
    expect(
        resolvedUrls == std::vector<std::string>({
            "ws://192.0.2.25:8765/v1/device/ws",
            "ws://192.0.2.26:8765/v1/device/ws",
        }),
        "refreshed discovery URL was not propagated to dependent adapters"
    );
}

void testImmediateAsynchronousConnectFailureRemainsScheduledForRetry()
{
    FakeWebSocketTransport transport;
    transport.errorDuringConnect = true;
    BridgeClient client(transport, validConfig());

    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "connection attempt was rejected");
    expect(transport.connectAttempts == 1, "initial connection attempt was not made");

    transport.errorDuringConnect = false;
    client.update(0);
    client.update(1000);

    expect(
        transport.connectAttempts == 2,
        "immediate asynchronous connection failure was overwritten"
    );
}

void testImmediateAsynchronousReconnectFailureRemainsScheduledForRetry()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());

    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "initial connection was rejected");
    transport.disconnectedCallback();
    client.update(0);

    transport.errorDuringConnect = true;
    client.update(1000);
    expect(transport.connectAttempts == 2, "first reconnect was not attempted");

    transport.errorDuringConnect = false;
    client.update(1000);
    client.update(3000);
    expect(
        transport.connectAttempts == 3,
        "immediate asynchronous reconnect failure was overwritten"
    );
}

void testUnsafeAudioInputHardLimitIsRejectedBeforeConnecting()
{
    for (const std::uint32_t durationMs : {999U, 15'001U}) {
        FakeWebSocketTransport transport;
        auto config = validConfig();
        config.audioInputMaxDurationMs = durationMs;
        BridgeClient client(transport, std::move(config));

        expect(client.initialize() == ClientError::InvalidConfig, "unsafe hard limit was accepted");
        expect(transport.connectAttempts == 0, "unsafe hard limit opened a socket");
    }
}

void testOversizedAudioOutputPrerollIsRejectedBeforeConnecting()
{
    for (const std::uint8_t frameMs : {20, 40, 60}) {
        const std::uint32_t capacityMs = 32U * frameMs;
        for (const auto prerollMs : {capacityMs, capacityMs + 1, 5'001U}) {
            FakeWebSocketTransport transport;
            auto config = validConfig();
            config.hello.audio.frameMs = frameMs;
            config.audioOutputPrerollMs = prerollMs;
            BridgeClient client(transport, std::move(config));
            expect(client.initialize() == (prerollMs == capacityMs ? ClientError::None
                                                                  : ClientError::InvalidConfig),
                   "preroll validation did not match negotiated queue capacity");
            expect(transport.connectAttempts == 0, "preroll validation opened a socket");
        }
    }
}

void testConnectedSocketSendsHello()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());

    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(
        transport.receiveBufferSize == stackchan::bridge_client::kMaxJsonBytes,
        "transport receive buffer was not bounded to the JSON frame limit"
    );
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    expect(static_cast<bool>(transport.connectedCallback), "connected callback was not registered");

    transport.connectedCallback();

    expect(!transport.sentText.empty(), "connected socket did not send hello");
    expect(
        transport.sentText.find("\"type\":\"hello\"") != std::string::npos,
        "connected socket sent the wrong message"
    );
    expect(
        client.state() == DeviceState::ConnectingBridge,
        "client became ready before hello acknowledgement"
    );
}

void testValidHelloAcknowledgementMakesClientIdle()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    expect(static_cast<bool>(transport.connectedCallback), "connected callback was not registered");
    transport.connectedCallback();
    expect(static_cast<bool>(transport.dataCallback), "data callback was not registered");

    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    expect(client.state() == DeviceState::Idle, "valid hello_ack did not make client IDLE");
    expect(client.helloAcknowledgement() != nullptr, "hello acknowledgement was not retained");
    expect(
        client.helloAcknowledgement()->heartbeatIntervalMs == 15000,
        "negotiated heartbeat interval was not retained"
    );
}

void testStateTransitionsArePublishedToLocalPresentation()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    std::vector<DeviceState> states;
    config.stateChanged = [&](DeviceState state) {
        states.push_back(state);
    };
    BridgeClient client(transport, std::move(config));

    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":0}
    })";
    const std::string end = R"({
        "v":1,"type":"audio.output.end",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb9",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":22,
        "payload":{"reason":"completed"}
    })";
    transport.dataCallback(start.data(), start.size(), false);
    transport.dataCallback(end.data(), end.size(), false);
    expect(
        client.acknowledgeAudioOutputPlayback() == ClientError::None,
        "empty physical playback completion was not acknowledged"
    );

    const std::vector<DeviceState> expected = {
        DeviceState::ConnectingWifi,
        DeviceState::ConnectingBridge,
        DeviceState::Idle,
        DeviceState::Speaking,
        DeviceState::Idle,
    };
    expect(states == expected, "state changes were not published in transition order");
}

void testInvalidHelloAcknowledgementClosesSocket()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");

    const std::string invalidAcknowledgement = R"({"v":1,"type":"command"})";
    transport.dataCallback(
        invalidAcknowledgement.data(), invalidAcknowledgement.size(), false
    );

    expect(transport.closed, "invalid hello acknowledgement did not close socket");
    expect(
        client.state() == DeviceState::ConnectingBridge,
        "invalid hello acknowledgement changed client state"
    );
}

void testHelloSendFailureClosesSocket()
{
    FakeWebSocketTransport transport;
    transport.sendResult = false;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");

    transport.connectedCallback();

    expect(transport.closed, "hello send failure did not close socket");
    expect(
        client.state() == DeviceState::ConnectingBridge,
        "hello send failure changed client state"
    );
}

void testDisconnectAfterHandshakeStartsReconnectState()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
    expect(client.state() == DeviceState::Idle, "handshake did not reach IDLE");
    expect(
        static_cast<bool>(transport.disconnectedCallback),
        "disconnected callback was not registered"
    );

    transport.disconnectedCallback();

    expect(
        client.state() == DeviceState::ConnectingBridge,
        "disconnect did not enter reconnect state"
    );
    expect(
        client.helloAcknowledgement() == nullptr,
        "disconnect retained stale negotiated connection data"
    );
    expect(client.reconnect() == ClientError::None, "reconnect attempt failed");
    expect(transport.connectAttempts == 2, "reconnect did not open a fresh socket");
}

void testTransportErrorClosesSocketWithoutLeavingReconnectState()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    expect(static_cast<bool>(transport.errorCallback), "error callback was not registered");

    transport.errorCallback(-1);

    expect(transport.closed, "transport error did not close socket");
    expect(
        client.state() == DeviceState::ConnectingBridge,
        "transport error left reconnect state"
    );
}

void testTransportErrorAfterHandshakeStartsReconnectState()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
    expect(client.state() == DeviceState::Idle, "handshake did not reach IDLE");

    transport.errorCallback(-1);

    expect(transport.closed, "transport error did not close socket");
    expect(
        client.state() == DeviceState::ConnectingBridge,
        "post-handshake transport error did not enter reconnect state"
    );
    expect(
        client.helloAcknowledgement() == nullptr,
        "transport error retained stale negotiated connection data"
    );
    expect(client.reconnect() == ClientError::None, "transport error blocked reconnect");
    expect(transport.connectAttempts == 2, "reconnect did not open a fresh socket");
}

void testHeaderControlCharacterInTokenIsRejectedBeforeTransportUse()
{
    FakeWebSocketTransport transport;
    auto config        = validConfig();
    config.deviceToken = "token\r\nInjected: value";
    std::vector<DeviceState> states;
    config.stateChanged = [&](DeviceState state) {
        states.push_back(state);
    };
    BridgeClient client(transport, std::move(config));

    expect(client.initialize() == ClientError::InvalidConfig, "unsafe token was accepted");
    expect(client.state() == DeviceState::Error, "invalid config did not enter ERROR");
    expect(
        states == std::vector<DeviceState>({DeviceState::Error}),
        "invalid config did not publish ERROR presentation"
    );
    expect(transport.headers.empty(), "unsafe token reached transport headers");
    expect(transport.connectedUrl.empty(), "unsafe token opened a connection");
}

void testDisconnectReconnectsOnlyAfterFirstBackoffDelay()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    const std::size_t initialAttempts = transport.connectAttempts;

    transport.disconnectedCallback();
    client.update(10000);
    client.update(10999);
    expect(
        transport.connectAttempts == initialAttempts,
        "client reconnected before one-second backoff"
    );

    client.update(11000);
    expect(
        transport.connectAttempts == initialAttempts + 1,
        "client did not reconnect after one-second backoff"
    );
}

void testFailedReconnectUsesNextBackoffDelay()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectResult = false;
    transport.disconnectedCallback();

    client.update(0);
    client.update(1000);
    expect(transport.connectAttempts == 2, "first reconnect was not attempted");

    client.update(1000);
    client.update(2999);
    expect(transport.connectAttempts == 2, "second reconnect ignored two-second delay");
    client.update(3000);
    expect(transport.connectAttempts == 3, "second reconnect was not attempted");
}

void testStableConnectionResetsSessionBackoff()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectResult = false;
    transport.disconnectedCallback();

    client.update(0);
    client.update(1000);
    client.update(1000);
    client.update(3000);
    client.update(3000);
    transport.connectResult = true;
    client.update(7000);
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
    expect(client.state() == DeviceState::Idle, "reconnected handshake did not reach IDLE");

    client.update(7000);
    client.update(37000);
    transport.disconnectedCallback();
    client.update(37000);
    client.update(37999);
    expect(transport.connectAttempts == 4, "stable reset retried too early");
    client.update(38000);
    expect(transport.connectAttempts == 5, "stable connection did not reset backoff to one second");
}

void testMissingHelloAcknowledgementClosesAfterFiveSeconds()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();

    client.update(100);
    client.update(5099);
    expect(!transport.closed, "handshake closed before five-second timeout");
    client.update(5100);
    expect(transport.closed, "missing hello_ack did not close after five seconds");
    expect(
        client.state() == DeviceState::ConnectingBridge,
        "handshake timeout left reconnect state"
    );
}

void testNegotiatedHeartbeatPingsAtTheServerInterval()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    client.update(0);
    client.update(14999);
    expect(transport.pingCount == 0, "heartbeat ping was sent early");
    client.update(15000);
    expect(transport.pingCount == 1, "heartbeat ping was not sent at negotiated interval");
    client.update(30000);
    expect(transport.pingCount == 2, "second heartbeat ping was not sent");
}

void testUnansweredPingClosesAfter45SecondsAndCanReconnect()
{
    for (const std::uint32_t base : {0U, UINT32_MAX - 20'000U}) {
        FakeWebSocketTransport transport;
        BridgeClient client(transport, validConfig());
        expect(client.initialize() == ClientError::None, "client initialization failed");
        expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection failed");
        transport.connectedCallback();
        const auto acknowledgement = validAcknowledgement();
        transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
        client.update(base);
        for (const std::uint32_t elapsed : {15'000U, 30'000U, 45'000U, 59'999U}) {
            client.update(base + elapsed);
            expect(!transport.closed, "pong deadline closed the connection early");
        }
        client.update(base + 60'000U);
        expect(transport.closed, "unanswered ping did not close after 45 seconds");
        transport.disconnectedCallback();
        client.update(base + 60'000U);
        client.update(base + 62'000U);
        expect(transport.connectAttempts == 2, "pong timeout did not schedule reconnect");
        transport.closed = false;
        transport.connectedCallback();
        transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
        client.update(base + 62'000U);
        client.update(base + 77'000U);
        expect(!transport.closed, "new handshake inherited an expired pong deadline");
        expect(static_cast<bool>(transport.pongCallback), "pong callback was not registered");
        transport.pongCallback();
        client.update(base + 122'000U);
        expect(!transport.closed, "received pong did not clear the outstanding deadline");
        client.update(base + 167'000U);
        expect(transport.closed, "later missing pong did not expire");
    }
}

void testIdleClientExecutesCommandAndSendsCorrelatedResult()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    int commandCalls = 0;
    config.commandHandler = [&](const Command& command) {
        ++commandCalls;
        expect(command.name == CommandName::DeviceGetStatus, "wrong command was dispatched");
        CommandExecutionResult result;
        result.ok = true;
        result.fields = {{"state", std::string("IDLE")}};
        return result;
    };
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 2000;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::string command = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":19,
        "payload":{"name":"device.get_status","args":{}}
    })";
    transport.dataCallback(command.data(), command.size(), false);

    expect(commandCalls == 1, "command handler was not called exactly once");
    expect(
        transport.sentText.find(R"("type":"command_result")") != std::string::npos,
        "command result was not sent"
    );
    expect(
        transport.sentText.find(
            R"("request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")"
        ) != std::string::npos,
        "command result lost request correlation"
    );
    expect(
        transport.sentText.find(R"("message_id":"123e4567-e89b-12d3-a456-426614174099")")
            != std::string::npos,
        "command result did not use a fresh message ID"
    );
}

void testDuplicateCommandRequestReplaysWithoutExecution()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    int commandCalls = 0;
    config.commandHandler = [&](const Command&) {
        ++commandCalls;
        CommandExecutionResult result;
        result.ok = true;
        return result;
    };
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 2000;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::string first = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":19,
        "payload":{"name":"audio.set_volume","args":{"volume":40}}
    })";
    const std::string retry = R"({
        "v":1,"type":"command",
        "message_id":"619a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":20,
        "payload":{"name":"audio.set_volume","args":{"volume":40}}
    })";
    transport.dataCallback(first.data(), first.size(), false);
    const std::string firstResponse = transport.sentText;
    transport.dataCallback(retry.data(), retry.size(), false);

    expect(commandCalls == 1, "identical request was executed twice");
    expect(transport.sentText == firstResponse, "identical request did not replay its result");
}

void testCommandResultsRemainReplayableUntilBoundedHistoryClosesTheConnection()
{
    const auto uuid = [](int value) {
        const std::string suffix = std::to_string(value);
        return "00000000-0000-4000-8000-" + std::string(12 - suffix.size(), '0') + suffix;
    };
    const auto wire = [&uuid](int request, int message) {
        return R"({"v":1,"type":"command","message_id":")" + uuid(message)
            + R"(","request_id":")" + uuid(request + 1'000)
            + R"(","sent_at_ms":1,"payload":{"name":"audio.set_volume","args":{"volume":40}}})";
    };
    for (const bool largeResults : {false, true}) {
        FakeWebSocketTransport transport;
        auto config = validConfig();
        int commandCalls = 0;
        config.commandHandler = [&](const Command&) {
            ++commandCalls;
            CommandExecutionResult result;
            result.ok = true;
            if (largeResults) {
                for (int field = 0; field < 28; ++field) {
                    result.fields.push_back({"field" + std::to_string(field), std::string(512, 'x')});
                }
            }
            return result;
        };
        config.envelopeFactory = []() {
            return EnvelopeMetadata{"123e4567-e89b-12d3-a456-426614174099", 2'000};
        };
        BridgeClient client(transport, std::move(config));
        expect(client.initialize() == ClientError::None, "client initialization failed");
        expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
        transport.connectedCallback();
        const auto acknowledgement = validAcknowledgement();
        transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
        const auto first = wire(0, 0);
        transport.dataCallback(first.data(), first.size(), false);
        const auto firstResponse = transport.sentText;
        expect(commandCalls == 1 && !transport.closed, "initial command failed");

        for (int index = 1; index <= 256 && !transport.closed; ++index) {
            auto next = wire(index, index);
            if (largeResults && index == 15) {
                next.append(stackchan::bridge_client::kMaxJsonBytes - next.size(), ' ');
            }
            transport.dataCallback(next.data(), next.size(), false);
            if (index == 8 || index == 255) {
                expect(!transport.closed, "history closed before the required replay checkpoint");
                for (const auto& retry : {first, wire(0, 10'000 + index)}) {
                    transport.sentText.clear();
                    transport.dataCallback(retry.data(), retry.size(), false);
                    expect(commandCalls == index + 1, "an older request was re-executed");
                    expect(transport.sentText == firstResponse, "an older request lost its result");
                }
            }
        }
        expect(transport.closed, "command history grew without a connection boundary");
        expect(largeResults ? commandCalls > 8 && commandCalls < 256 : commandCalls == 256,
               "command history did not enforce its count/byte budgets before execution");
        const int callsBeforeReconnect = commandCalls;
        const auto next = wire(500, 500);
        transport.dataCallback(next.data(), next.size(), false);
        expect(commandCalls == callsBeforeReconnect, "closing history still executed new work");

        transport.disconnectedCallback();
        transport.closed = false;
        expect(client.reconnect() == ClientError::None, "history exhaustion could not reconnect");
        transport.connectedCallback();
        transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
        transport.dataCallback(next.data(), next.size(), false);
        expect(commandCalls == callsBeforeReconnect + 1 && !transport.closed,
               "fresh handshake did not release the previous history budget");
    }
}

void testConflictingDuplicateRequestIsRejectedWithoutExecution()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    int commandCalls = 0;
    config.commandHandler = [&](const Command&) {
        ++commandCalls;
        CommandExecutionResult result;
        result.ok = true;
        return result;
    };
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 2000;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::string first = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":19,
        "payload":{"name":"audio.set_volume","args":{"volume":40}}
    })";
    const std::string conflicting = R"({
        "v":1,"type":"command",
        "message_id":"619a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":20,
        "payload":{"name":"audio.set_volume","args":{"volume":41}}
    })";
    transport.dataCallback(first.data(), first.size(), false);
    transport.dataCallback(conflicting.data(), conflicting.size(), false);

    expect(commandCalls == 1, "conflicting request was executed");
    expect(
        transport.sentText.find(R"("code":"INVALID_MESSAGE")") != std::string::npos,
        "conflicting request ID was not rejected"
    );
    expect(!transport.closed, "first conflicting request closed the connection");
}

void testAudioOutputStreamOwnsBinaryUntilMatchingEnd()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";
    transport.dataCallback(start.data(), start.size(), false);
    expect(client.state() == DeviceState::Speaking, "audio start did not enter SPEAKING");

    const std::uint8_t packet[] = {1, 2, 3};
    transport.dataCallback(
        reinterpret_cast<const char*>(packet), sizeof(packet), true
    );
    const std::string end = R"({
        "v":1,"type":"audio.output.end",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb9",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":22,
        "payload":{"reason":"completed"}
    })";
    transport.dataCallback(end.data(), end.size(), false);

    expect(
        !client.deliverAudioOutputPacket(
            true,
            [](int, int, const std::vector<std::uint8_t>&) { return false; }
        ),
        "downstream backpressure was ignored"
    );
    expect(client.queuedAudioOutputPackets() == 1, "backpressure discarded session audio");
    std::vector<std::uint8_t> output;
    expect(
        client.deliverAudioOutputPacket(
            true,
            [&](int sampleRate, int frameMs, const std::vector<std::uint8_t>& packetBytes) {
                expect(sampleRate == 16'000, "playback lost sample rate");
                expect(frameMs == 60, "playback lost frame duration");
                output = packetBytes;
                return true;
            }
        ),
        "owned audio packet was not exposed to playback"
    );
    expect(output == std::vector<std::uint8_t>({1, 2, 3}), "audio packet bytes changed");
    expect(
        client.state() == DeviceState::Speaking,
        "downstream delivery ended SPEAKING before physical playback completion"
    );
    expect(
        client.beginAudioInput(
            "168b58ca-7c31-4744-b445-d2f20c9bdde0",
            "82e18a2c-f267-48d7-8465-aeb7e9b73533",
            AudioInputTrigger::Touch
        ) == AudioInputError::InvalidState,
        "input started while physical playback was still active"
    );
    expect(
        client.audioOutputDeliveryComplete(),
        "drained stream was not awaiting physical playback completion"
    );
    expect(
        client.acknowledgeAudioOutputPlayback() == ClientError::None,
        "physical playback completion was not acknowledged"
    );
    expect(client.state() == DeviceState::Idle, "playback acknowledgement did not return to IDLE");
}

void testSessionUsesConfiguredAudioOutputPreroll()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    expect(
        BridgeClientConfig{}.audioOutputPrerollMs == 500,
        "default playback preroll changed"
    );
    config.audioOutputPrerollMs = 120;
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";
    transport.dataCallback(start.data(), start.size(), false);

    const std::uint8_t packet[] = {1};
    std::vector<std::uint8_t> output;
    transport.dataCallback(reinterpret_cast<const char*>(packet), sizeof(packet), true);
    expect(!client.popAudioOutputPacket(output), "configured preroll became ready after 60 ms");
    transport.dataCallback(reinterpret_cast<const char*>(packet), sizeof(packet), true);
    expect(client.popAudioOutputPacket(output), "configured preroll was not used at 120 ms");

    const std::string end = R"({
        "v":1,"type":"audio.output.end",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb9",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":22,
        "payload":{"reason":"completed"}
    })";
    transport.dataCallback(end.data(), end.size(), false);
    expect(client.popAudioOutputPacket(output), "remaining configured-preroll packet was not read");
    expect(
        client.state() == DeviceState::Speaking,
        "pop path ended SPEAKING before physical playback completion"
    );
    expect(
        client.acknowledgeAudioOutputPlayback() == ClientError::None,
        "pop-path physical playback completion was not acknowledged"
    );
}

void testEndAfterDownstreamDeliveryWaitsForPhysicalPlayback()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.audioOutputPrerollMs = 0;
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":60}
    })";
    transport.dataCallback(start.data(), start.size(), false);
    const std::uint8_t packet[] = {1, 2, 3};
    transport.dataCallback(reinterpret_cast<const char*>(packet), sizeof(packet), true);
    expect(
        client.deliverAudioOutputPacket(true, [](int, int, const auto&) { return true; }),
        "audio packet was not delivered downstream"
    );

    const std::string end = R"({
        "v":1,"type":"audio.output.end",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb9",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":22,
        "payload":{"reason":"completed"}
    })";
    transport.dataCallback(end.data(), end.size(), false);

    expect(
        client.state() == DeviceState::Speaking,
        "stream end discarded SPEAKING before physical playback completion"
    );
    expect(
        client.audioOutputDeliveryComplete(),
        "ended stream was not awaiting physical playback completion"
    );
    expect(
        client.acknowledgeAudioOutputPlayback() == ClientError::None,
        "physical playback completion was not acknowledged"
    );
    expect(client.state() == DeviceState::Idle, "playback acknowledgement did not return to IDLE");
}

void testFailedAudioEndLeavesSpeakingImmediately()
{
    FakeWebSocketTransport transport;
    BridgeClient client(transport, validConfig());
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";
    const std::string end = R"({
        "v":1,"type":"audio.output.end",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb9",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":22,
        "payload":{"reason":"tts_error"}
    })";
    transport.dataCallback(start.data(), start.size(), false);
    transport.dataCallback(end.data(), end.size(), false);

    expect(client.state() == DeviceState::Idle, "failed audio end retained SPEAKING state");
}

void testDuplicateAudioControlMessageIsNotAppliedTwice()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 2000;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";
    transport.dataCallback(start.data(), start.size(), false);
    transport.dataCallback(start.data(), start.size(), false);

    expect(client.state() == DeviceState::Speaking, "duplicate start changed playback state");
    expect(
        transport.sentText.find(R"("type":"error")") == std::string::npos,
        "duplicate message ID was treated as a new start"
    );
    expect(!transport.closed, "duplicate message ID closed the connection");
}

void testBinaryBeforeAudioStartIsDroppedAndCounted()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 2001;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::uint8_t packet[] = {4};
    transport.dataCallback(
        reinterpret_cast<const char*>(packet), sizeof(packet), true
    );

    expect(
        client.droppedAudioOutputPackets() == 1,
        "binary outside an audio stream was not counted"
    );
    expect(
        transport.sentText.find(R"("type":"error")") != std::string::npos
            && transport.sentText.find(R"("code":"INVALID_STATE")")
                != std::string::npos,
        "binary outside an audio stream was not reported"
    );
    expect(!transport.closed, "first invalid audio state closed the connection");
    expect(client.state() == DeviceState::Idle, "stray binary changed device state");
}

void testThirdInvalidFrameWithinTenSecondsClosesConnection()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 2002;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
    client.update(100);

    const std::string malformed = R"({"type":"not-protocol-v1"})";
    transport.dataCallback(malformed.data(), malformed.size(), false);
    expect(!transport.closed, "first invalid message closed the connection");
    expect(
        transport.sentText.find(R"("code":"INVALID_MESSAGE")") != std::string::npos,
        "invalid message was not reported safely"
    );
    transport.dataCallback(malformed.data(), malformed.size(), false);
    expect(!transport.closed, "second invalid message closed the connection");
    transport.dataCallback(malformed.data(), malformed.size(), false);
    expect(transport.closed, "third invalid message in ten seconds kept connection open");
}

void testSpeechCancelDiscardsOnlyTheOwnedPlaybackQueue()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    int cancelCalls = 0;
    config.commandHandler = [&](const Command& command) {
        expect(command.name == CommandName::SpeechCancel, "wrong command was dispatched");
        ++cancelCalls;
        CommandExecutionResult result;
        result.ok = true;
        return result;
    };
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 2000;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";
    transport.dataCallback(start.data(), start.size(), false);
    const std::uint8_t packet[] = {5, 6};
    transport.dataCallback(reinterpret_cast<const char*>(packet), sizeof(packet), true);
    expect(client.queuedAudioOutputPackets() == 1, "playback packet was not queued");

    const std::string cancel = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb9",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7","sent_at_ms":24,
        "payload":{"name":"speech.cancel","args":{}}
    })";
    transport.dataCallback(cancel.data(), cancel.size(), false);

    expect(cancelCalls == 1, "owned speech cancellation did not reach the handler");
    expect(client.queuedAudioOutputPackets() == 0, "speech cancellation retained audio");
    expect(client.state() == DeviceState::Idle, "speech cancellation did not return to IDLE");
    expect(
        transport.sentText.find(R"("ok":true)") != std::string::npos,
        "speech cancellation result was not sent"
    );
}

void testCancelledOutputFlushesBeforeARepeatedSpeechCancel()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    int cancelCalls = 0;
    config.commandHandler = [&](const Command& command) {
        expect(command.name == CommandName::SpeechCancel, "wrong command was dispatched");
        ++cancelCalls;
        CommandExecutionResult result;
        result.ok = true;
        return result;
    };
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 2000;
        return envelope;
    };
    BridgeClient* clientPointer = nullptr;
    bool ownedQueueVisibleDuringFlush = false;
    config.playbackFlushHandler = [&]() {
        ownedQueueVisibleDuringFlush = clientPointer != nullptr
            && clientPointer->state() == DeviceState::Speaking
            && clientPointer->queuedAudioOutputPackets() == 1;
    };
    BridgeClient client(transport, std::move(config));
    clientPointer = &client;
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";
    transport.dataCallback(start.data(), start.size(), false);
    const std::uint8_t packet[] = {5, 6};
    transport.dataCallback(reinterpret_cast<const char*>(packet), sizeof(packet), true);

    const std::string end = R"({
        "v":1,"type":"audio.output.end",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cba",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":23,
        "payload":{"reason":"cancelled"}
    })";
    transport.dataCallback(end.data(), end.size(), false);

    expect(ownedQueueVisibleDuringFlush, "cancelled end cleared context before decoder flush");
    expect(client.queuedAudioOutputPackets() == 0, "cancelled end retained playback bytes");
    expect(client.state() == DeviceState::Idle, "cancelled end retained SPEAKING state");

    const std::string cancel = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cbb",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7","sent_at_ms":24,
        "payload":{"name":"speech.cancel","args":{}}
    })";
    transport.dataCallback(cancel.data(), cancel.size(), false);

    expect(cancelCalls == 1, "repeated owned cancellation did not reach the handler");
    expect(
        transport.sentText.find(R"("ok":true)") != std::string::npos,
        "repeated owned cancellation returned failure"
    );
}

void testLocalAudioInputBargesInAndDiscardsPlayback()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 3000;
        return envelope;
    };
    int playbackFlushCalls = 0;
    config.playbackFlushHandler = [&]() {
        ++playbackFlushCalls;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    const std::string playbackStart = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";
    const std::uint8_t packet[] = {0x11, 0x22};
    transport.dataCallback(playbackStart.data(), playbackStart.size(), false);
    transport.dataCallback(
        reinterpret_cast<const char*>(packet), sizeof(packet), true
    );
    expect(client.state() == DeviceState::Speaking, "playback did not enter SPEAKING");
    expect(client.queuedAudioOutputPackets() == 1, "playback packet was not queued");

    expect(
        client.beginAudioInput(
            "f19a16ce-3a07-4ab6-9767-f39bcc096cb8",
            "b9d1c15a-f728-4293-87fc-1d3cae5f1874",
            AudioInputTrigger::Touch
        ) == AudioInputError::None,
        "touch did not barge in during playback"
    );

    expect(client.state() == DeviceState::Listening, "barge-in did not enter LISTENING");
    expect(playbackFlushCalls == 1, "barge-in did not flush physical playback");
    expect(client.queuedAudioOutputPackets() == 0, "barge-in retained playback packets");
    expect(
        transport.sentText.find(R"("type":"audio.input.start")") != std::string::npos,
        "barge-in did not send audio.input.start"
    );

    const std::size_t sentBeforeEnd = transport.sentTexts.size();
    const std::string playbackEnd = R"({
        "v":1,"type":"audio.output.end",
        "message_id":"619a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":22,
        "payload":{"reason":"cancelled"}
    })";
    for (char suffix = '0'; suffix < '3'; ++suffix) {
        std::string lateEnd = playbackEnd;
        lateEnd[lateEnd.find("619a16ce")] = suffix;
        transport.dataCallback(lateEnd.data(), lateEnd.size(), false);
    }
    expect(!transport.closed, "late cancellation ends closed the connection");
    expect(transport.sentTexts.size() == sentBeforeEnd, "late cancellation end was rejected");
    expect(client.state() == DeviceState::Listening, "late end interrupted the new input");
    expect(playbackFlushCalls == 1, "late end flushed playback again");
    expect(
        client.sendAudioInputPacket(packet, sizeof(packet)) == AudioInputError::None,
        "late end closed the new input stream"
    );

    std::string nextStart = playbackStart;
    nextStart[nextStart.find("519a16ce")] = '7';
    nextStart[nextStart.find("c9ef993d")] = 'd';
    nextStart[nextStart.find("a9d1c15a")] = 'b';
    transport.dataCallback(nextStart.data(), nextStart.size(), false);
    transport.dataCallback(reinterpret_cast<const char*>(packet), sizeof(packet), true);
    const std::size_t sentBeforeLateEnd = transport.sentTexts.size();
    transport.dataCallback(playbackEnd.data(), playbackEnd.size(), false);
    expect(client.state() == DeviceState::Speaking, "old end stopped the new playback");
    expect(client.queuedAudioOutputPackets() == 1, "old end discarded the new playback");
    expect(transport.sentTexts.size() == sentBeforeLateEnd, "old end was rejected during playback");

    for (const std::string prefix : {"c9ef993d", "a9d1c15a"}) {
        std::string wrongEnd = playbackEnd;
        wrongEnd[wrongEnd.find("619a16ce")] = prefix.front();
        wrongEnd[wrongEnd.find(prefix)] = 'e';
        transport.dataCallback(wrongEnd.data(), wrongEnd.size(), false);
        expect(
            transport.sentText.find("INVALID_STATE") != std::string::npos,
            "unrelated end was accepted as a cancelled stream"
        );
    }
    expect(!transport.closed, "matching late ends counted toward the invalid-message limit");
    expect(client.queuedAudioOutputPackets() == 1, "unrelated end discarded new playback");
}

void testPlaybackStartEndsTheOpenAudioInput()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.audioOutputPrerollMs = 0;
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 3000;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    expect(
        client.beginAudioInput(
            "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
            "a9d1c15a-f728-4293-87fc-1d3cae5f1874",
            AudioInputTrigger::Touch
        ) == AudioInputError::None,
        "local audio input did not start"
    );
    const std::string playbackStart = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"b9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":0}
    })";
    transport.dataCallback(playbackStart.data(), playbackStart.size(), false);

    expect(client.state() == DeviceState::Speaking, "playback did not enter SPEAKING");
    expect(
        transport.sentText.find(R"("type":"audio.input.end")") != std::string::npos,
        "playback start did not end the open input"
    );
    expect(
        transport.sentText.find(R"("reason":"silence")") != std::string::npos,
        "playback start used the wrong input end reason"
    );

    const std::string playbackEnd = R"({
        "v":1,"type":"audio.output.end",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb9",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"b9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":22,
        "payload":{"reason":"completed"}
    })";
    transport.dataCallback(playbackEnd.data(), playbackEnd.size(), false);
    expect(
        client.acknowledgeAudioOutputPlayback() == ClientError::None,
        "empty playback was not acknowledged"
    );
    expect(
        client.beginAudioInput(
            "d9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
            "c9d1c15a-f728-4293-87fc-1d3cae5f1874",
            AudioInputTrigger::Touch
        ) == AudioInputError::None,
        "stale input ownership blocked the next recording"
    );
}

void testBridgeAudioDecodeErrorReleasesTheOpenAudioInput()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174100";
        envelope.sentAtMs = 3001;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    expect(
        client.beginAudioInput(
            "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
            "a9d1c15a-f728-4293-87fc-1d3cae5f1874",
            AudioInputTrigger::Touch
        ) == AudioInputError::None,
        "local audio input did not start"
    );
    const std::size_t sentMessageCount = transport.sentTexts.size();
    const std::string decodeError = R"({
        "v":1,"type":"error",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cba",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":23,
        "payload":{"code":"AUDIO_DECODE_ERROR",
            "message":"audio input stream ended after repeated decode failures"}
    })";
    transport.dataCallback(decodeError.data(), decodeError.size(), false);

    expect(client.state() == DeviceState::Idle, "decode error left the input open");
    expect(
        transport.sentTexts.size() == sentMessageCount,
        "valid peer error was echoed back as another protocol error"
    );
    expect(
        client.beginAudioInput(
            "d9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
            "b9d1c15a-f728-4293-87fc-1d3cae5f1874",
            AudioInputTrigger::Touch
        ) == AudioInputError::None,
        "decode error left stale input ownership"
    );
}

void testLocalAudioInputSendsOwnedBoundedBinaryStream()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 3000;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    expect(
        client.beginAudioInput(
            "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
            "a9d1c15a-f728-4293-87fc-1d3cae5f1874",
            AudioInputTrigger::Touch
        ) == AudioInputError::None,
        "local audio input did not start"
    );
    expect(client.state() == DeviceState::Listening, "audio input did not enter LISTENING");
    expect(
        transport.sentText.find(R"("type":"audio.input.start")") != std::string::npos,
        "audio input start was not sent"
    );

    const std::uint8_t packet[] = {15, 16, 17};
    expect(
        client.sendAudioInputPacket(packet, sizeof(packet)) == AudioInputError::None,
        "bounded microphone packet was not sent"
    );
    expect(
        transport.sentBinary == std::vector<std::uint8_t>({15, 16, 17}),
        "microphone packet bytes changed"
    );
    expect(
        client.sendAudioInputPacket(packet, stackchan::bridge_client::kMaxAudioPacketBytes + 1)
            == AudioInputError::PacketTooLarge,
        "oversized microphone packet was accepted"
    );
    expect(transport.binarySendCount == 1, "oversized microphone packet reached transport");

    expect(
        client.endAudioInput(AudioInputEndReason::Silence) == AudioInputError::None,
        "local audio input did not end"
    );
    expect(client.state() == DeviceState::Idle, "audio input end did not return to IDLE");
    expect(
        transport.sentText.find(R"("type":"audio.input.end")") != std::string::npos,
        "audio input end was not sent"
    );
}

void testAudioInputEndsAtTheConfiguredHardLimit()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    expect(
        BridgeClientConfig{}.audioInputMaxDurationMs == 15'000,
        "default audio input hard limit changed"
    );
    config.audioInputMaxDurationMs = 1'000;
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 3000;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
    expect(
        client.beginAudioInput(
            "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
            "a9d1c15a-f728-4293-87fc-1d3cae5f1874",
            AudioInputTrigger::Touch
        ) == AudioInputError::None,
        "local audio input did not start"
    );

    client.update(100);
    client.update(1'099);
    expect(client.state() == DeviceState::Listening, "audio input ended before hard limit");
    client.update(1'100);

    expect(client.state() == DeviceState::Idle, "audio input exceeded hard limit");
    expect(
        transport.sentText.find(R"("reason":"max_duration")") != std::string::npos,
        "hard limit did not send max_duration"
    );
}

void testAuthenticatedClientSendsTouchTapWithFreshEnvelope()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 3999;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    expect(
        client.sendTouchTap(160, 0) == ClientError::None,
        "touch tap event was not sent"
    );
    expect(
        transport.sentText.find(R"("name":"touch.tap")") != std::string::npos,
        "touch tap event name changed"
    );
    expect(
        transport.sentText.find(R"("device_id":"stackchan-001")") != std::string::npos,
        "touch tap lost device ownership"
    );
}

void testAuthenticatedClientSendsCameraCompletionWithFreshEnvelope()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 4000;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);

    expect(
        client.sendCameraCompleted(
            "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
            false,
            CameraCompletionError::CaptureFailed
        ) == ClientError::None,
        "camera completion was not sent"
    );
    expect(
        transport.sentText.find(R"("name":"camera.completed")") != std::string::npos,
        "camera completion event changed"
    );
    expect(
        transport.sentText.find(R"("message_id":"123e4567-e89b-12d3-a456-426614174099")")
            != std::string::npos,
        "camera completion did not use a fresh message ID"
    );
    expect(
        transport.sentText.find(R"("device_id":"stackchan-001")") != std::string::npos,
        "camera completion lost device ownership"
    );
    expect(
        transport.sentText.find(R"("error_code":"CAPTURE_FAILED")") != std::string::npos,
        "camera completion lost its failure"
    );
}

void testAudioOverflowSendsOwnedEventOnUpdate()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 5000;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";
    transport.dataCallback(start.data(), start.size(), false);
    const std::uint8_t packet[] = {1};
    for (std::size_t index = 0;
         index <= stackchan::bridge_client::kAudioOutputQueuePackets;
         ++index) {
        transport.dataCallback(reinterpret_cast<const char*>(packet), sizeof(packet), true);
    }

    client.update(100);

    expect(
        transport.sentText.find(R"("name":"audio.overflow")") != std::string::npos,
        "audio overflow event was not sent"
    );
    expect(
        transport.sentText.find(R"("stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874")")
            != std::string::npos,
        "audio overflow event lost stream ownership"
    );
}

void testAudioUnderrunWaitsForDownstreamPlaybackToDrain()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 5001;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";
    transport.dataCallback(start.data(), start.size(), false);
    const std::uint8_t packet[] = {2};
    for (int index = 0; index < 9; ++index) {
        transport.dataCallback(reinterpret_cast<const char*>(packet), sizeof(packet), true);
    }
    for (int index = 0; index < 9; ++index) {
        expect(
            client.deliverAudioOutputPacket(
                false,
                [](int, int, const auto&) { return true; }
            ),
            "audio packet was not delivered"
        );
    }
    expect(
        !client.deliverAudioOutputPacket(
            false,
            [](int, int, const auto&) { return true; }
        ),
        "empty playback delivered a packet"
    );

    client.update(100);
    expect(
        transport.sentText.find(R"("name":"audio.underrun")") == std::string::npos,
        "buffered downstream playback was reported as an underrun"
    );
    client.deliverAudioOutputPacket(true, [](int, int, const auto&) { return true; });
    client.update(101);
    const std::size_t eventCount = transport.sentTexts.size();
    expect(
        transport.sentText.find(R"("name":"audio.underrun")") != std::string::npos,
        "audio underrun event was not sent"
    );
    client.deliverAudioOutputPacket(true, [](int, int, const auto&) { return true; });
    client.update(102);
    expect(transport.sentTexts.size() == eventCount, "one underrun episode was sent repeatedly");
}

void testAudioDecodeFailureClearsPlaybackAndSendsSafeEvent()
{
    FakeWebSocketTransport transport;
    auto config = validConfig();
    config.envelopeFactory = []() {
        EnvelopeMetadata envelope;
        envelope.messageId = "123e4567-e89b-12d3-a456-426614174099";
        envelope.sentAtMs = 5002;
        return envelope;
    };
    BridgeClient client(transport, std::move(config));
    expect(client.initialize() == ClientError::None, "client initialization failed");
    expect(client.wifiConnected() == ClientError::None, "Wi-Fi connection handling failed");
    transport.connectedCallback();
    const std::string acknowledgement = validAcknowledgement();
    transport.dataCallback(acknowledgement.data(), acknowledgement.size(), false);
    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";
    transport.dataCallback(start.data(), start.size(), false);
    const std::uint8_t packet[] = {3};
    transport.dataCallback(reinterpret_cast<const char*>(packet), sizeof(packet), true);
    expect(client.state() == DeviceState::Speaking, "audio stream did not start");

    expect(
        client.reportAudioDecodeFailure() == ClientError::None,
        "audio decode failure was not reported"
    );

    expect(client.state() == DeviceState::Idle, "decode failure retained SPEAKING state");
    expect(client.queuedAudioOutputPackets() == 0, "decode failure retained playback bytes");
    expect(
        transport.sentText.find(R"("name":"device.error")") != std::string::npos,
        "decode failure did not send device.error"
    );
    expect(
        transport.sentText.find(R"("code":"AUDIO_DECODE_ERROR")") != std::string::npos,
        "decode failure sent the wrong stable code"
    );
}

}  // namespace

int main()
{
    testUpdatePollsTransportCallbacks();
    testWifiConnectedConfiguresAuthenticatedConnection();
    testWifiConnectedResolvesBridgeUrlAfterWifiIsReady();
    testDiscoveryMissIsRetriedAfterBackoff();
    testReconnectReevaluatesDiscoveryAfterAddressChange();
    testImmediateAsynchronousConnectFailureRemainsScheduledForRetry();
    testImmediateAsynchronousReconnectFailureRemainsScheduledForRetry();
    testUnsafeAudioInputHardLimitIsRejectedBeforeConnecting();
    testOversizedAudioOutputPrerollIsRejectedBeforeConnecting();
    testConnectedSocketSendsHello();
    testValidHelloAcknowledgementMakesClientIdle();
    testStateTransitionsArePublishedToLocalPresentation();
    testInvalidHelloAcknowledgementClosesSocket();
    testHelloSendFailureClosesSocket();
    testDisconnectAfterHandshakeStartsReconnectState();
    testTransportErrorClosesSocketWithoutLeavingReconnectState();
    testTransportErrorAfterHandshakeStartsReconnectState();
    testHeaderControlCharacterInTokenIsRejectedBeforeTransportUse();
    testDisconnectReconnectsOnlyAfterFirstBackoffDelay();
    testFailedReconnectUsesNextBackoffDelay();
    testStableConnectionResetsSessionBackoff();
    testMissingHelloAcknowledgementClosesAfterFiveSeconds();
    testNegotiatedHeartbeatPingsAtTheServerInterval();
    testUnansweredPingClosesAfter45SecondsAndCanReconnect();
    testIdleClientExecutesCommandAndSendsCorrelatedResult();
    testDuplicateCommandRequestReplaysWithoutExecution();
    testCommandResultsRemainReplayableUntilBoundedHistoryClosesTheConnection();
    testConflictingDuplicateRequestIsRejectedWithoutExecution();
    testAudioOutputStreamOwnsBinaryUntilMatchingEnd();
    testSessionUsesConfiguredAudioOutputPreroll();
    testEndAfterDownstreamDeliveryWaitsForPhysicalPlayback();
    testFailedAudioEndLeavesSpeakingImmediately();
    testDuplicateAudioControlMessageIsNotAppliedTwice();
    testBinaryBeforeAudioStartIsDroppedAndCounted();
    testThirdInvalidFrameWithinTenSecondsClosesConnection();
    testSpeechCancelDiscardsOnlyTheOwnedPlaybackQueue();
    testCancelledOutputFlushesBeforeARepeatedSpeechCancel();
    testLocalAudioInputBargesInAndDiscardsPlayback();
    testPlaybackStartEndsTheOpenAudioInput();
    testBridgeAudioDecodeErrorReleasesTheOpenAudioInput();
    testLocalAudioInputSendsOwnedBoundedBinaryStream();
    testAudioInputEndsAtTheConfiguredHardLimit();
    testAuthenticatedClientSendsTouchTapWithFreshEnvelope();
    testAuthenticatedClientSendsCameraCompletionWithFreshEnvelope();
    testAudioOverflowSendsOwnedEventOnUpdate();
    testAudioUnderrunWaitsForDownstreamPlaybackToDrain();
    testAudioDecodeFailureClearsPlaybackAndSendsSafeEvent();
    return 0;
}
