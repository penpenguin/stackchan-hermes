#include <ArduinoJson.h>

#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>

#include <stackchan_bridge_client/protocol.h>

namespace {

using stackchan::bridge_client::AudioFormat;
using stackchan::bridge_client::Capabilities;
using stackchan::bridge_client::EnvelopeMetadata;
using stackchan::bridge_client::HelloPayload;
using stackchan::bridge_client::HelloAck;
using stackchan::bridge_client::ProtocolError;
using stackchan::bridge_client::buildHelloJson;
using stackchan::bridge_client::parseHelloAckJson;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

EnvelopeMetadata validEnvelope()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "11111111-1111-4111-8111-111111111111";
    envelope.sentAtMs  = 1234;
    return envelope;
}

HelloPayload validHello()
{
    Capabilities capabilities;
    capabilities.microphone = true;
    capabilities.speaker    = true;
    capabilities.camera     = true;
    capabilities.touch      = true;
    capabilities.head       = true;
    capabilities.display    = true;
    capabilities.avatar     = true;
    capabilities.ledCount   = 12;

    AudioFormat audio;
    audio.codec     = "opus";
    audio.sampleRate = 16000;
    audio.channels   = 1;
    audio.frameMs    = 60;

    HelloPayload hello;
    hello.deviceId        = "stackchan-001";
    hello.deviceName      = "StackChan";
    hello.firmwareVersion = "0.1.0";
    hello.hardwareModel   = "M5STACK-K151";
    hello.capabilities    = capabilities;
    hello.audio           = audio;
    return hello;
}

std::string validHelloAckJson()
{
    return R"({
        "v": 1,
        "type": "hello_ack",
        "message_id": "7d2598af-ae08-4025-94bb-53007808fb38",
        "sent_at_ms": 0,
        "payload": {
            "connection_id": "bdce4ce9-ec1d-4d06-bc26-45cb0474a8b6",
            "selected_protocol_version": 1,
            "heartbeat_interval_ms": 15000,
            "max_command_timeout_ms": 5000,
            "server_version": "0.1.0"
        }
    })";
}

void expectInvalidHello(
    const EnvelopeMetadata& envelope,
    const HelloPayload& hello,
    const char* label
)
{
    std::string json = "stale output";
    expect(buildHelloJson(envelope, hello, json) == ProtocolError::InvalidArgument, label);
    expect(json.empty(), "invalid hello retained output");
}

void testBuildsBoundedProtocolV1Hello()
{
    const EnvelopeMetadata envelope = validEnvelope();
    const HelloPayload hello         = validHello();

    std::string json;
    expect(buildHelloJson(envelope, hello, json) == ProtocolError::None, "hello build failed");
    expect(json.size() <= 16384, "hello exceeds Protocol v1 JSON limit");

    JsonDocument document;
    expect(!deserializeJson(document, json), "hello is not valid JSON");
    expect(document["v"] == 1, "protocol version mismatch");
    expect(document["type"] == "hello", "message type mismatch");
    expect(document["message_id"] == envelope.messageId, "message id mismatch");
    expect(document["sent_at_ms"] == 1234, "timestamp mismatch");
    expect(document["payload"]["device_id"] == "stackchan-001", "device id mismatch");
    expect(document["payload"]["protocol_versions"][0] == 1, "version list mismatch");
    expect(document["payload"]["capabilities"]["led_count"] == 12, "LED count mismatch");
    expect(document["payload"]["audio"]["codec"] == "opus", "audio codec mismatch");
    expect(document["payload"]["audio"]["sample_rate"] == 16000, "sample rate mismatch");
    expect(json.find("token") == std::string::npos, "hello leaked a token field");
}

void testRejectsInvalidHelloIdentityAndCodec()
{
    EnvelopeMetadata envelope = validEnvelope();
    HelloPayload hello         = validHello();
    hello.deviceId = "../not-a-device";
    expectInvalidHello(envelope, hello, "unsafe device id was accepted");

    hello              = validHello();
    envelope.messageId = "not-a-uuid";
    expectInvalidHello(envelope, hello, "invalid message UUID was accepted");

    envelope         = validEnvelope();
    hello            = validHello();
    hello.audio.codec = "pcm";
    expectInvalidHello(envelope, hello, "unsupported audio codec was accepted");
}

void testRejectsProtocolTimestampsOutsideSignedJsonRange()
{
    EnvelopeMetadata envelope = validEnvelope();
    envelope.sentAtMs = static_cast<std::uint64_t>(
        std::numeric_limits<std::int64_t>::max()
    ) + 1;
    std::string output = "stale output";
    expect(
        buildHelloJson(envelope, validHello(), output) == ProtocolError::InvalidArgument,
        "out-of-range hello timestamp was accepted"
    );
    expect(output.empty(), "invalid hello timestamp retained output");

    const std::string acknowledgement = R"({
        "v": 1,
        "type": "hello_ack",
        "message_id": "7d2598af-ae08-4025-94bb-53007808fb38",
        "sent_at_ms": 9223372036854775808,
        "payload": {
            "connection_id": "bdce4ce9-ec1d-4d06-bc26-45cb0474a8b6",
            "selected_protocol_version": 1,
            "heartbeat_interval_ms": 15000,
            "max_command_timeout_ms": 5000,
            "server_version": "0.1.0"
        }
    })";
    HelloAck parsed;
    parsed.connectionId = "stale";
    expect(
        parseHelloAckJson(acknowledgement, parsed) == ProtocolError::InvalidArgument,
        "out-of-range hello_ack timestamp was accepted"
    );
    expect(parsed.connectionId.empty(), "invalid hello_ack retained parsed state");
}

void testRejectsAudioFormatsOutsideProtocolV1()
{
    const EnvelopeMetadata envelope = validEnvelope();
    HelloPayload hello               = validHello();
    hello.audio.sampleRate           = 48000;
    expectInvalidHello(envelope, hello, "unsupported sample rate was accepted");

    hello                = validHello();
    hello.audio.channels = 2;
    expectInvalidHello(envelope, hello, "stereo audio was accepted");

    hello               = validHello();
    hello.audio.frameMs = 10;
    expectInvalidHello(envelope, hello, "unsupported frame duration was accepted");
}

void testRejectsInvalidBoundedHelloText()
{
    const EnvelopeMetadata envelope = validEnvelope();
    HelloPayload hello               = validHello();
    hello.deviceName                 = std::string(65, 'x');
    expectInvalidHello(envelope, hello, "oversized device name was accepted");

    hello                 = validHello();
    hello.firmwareVersion = "";
    expectInvalidHello(envelope, hello, "empty firmware version was accepted");

    hello               = validHello();
    hello.hardwareModel = "M5STACK\nK151";
    expectInvalidHello(envelope, hello, "control character was accepted");
}

void testPreservesMaximumLedCapability()
{
    const EnvelopeMetadata envelope = validEnvelope();
    HelloPayload hello               = validHello();
    hello.deviceName                 = "スタックチャン";
    hello.capabilities.ledCount      = 256;

    std::string json;
    expect(buildHelloJson(envelope, hello, json) == ProtocolError::None, "max LED hello failed");

    JsonDocument document;
    expect(!deserializeJson(document, json), "max LED hello is not JSON");
    expect(document["payload"]["capabilities"]["led_count"] == 256, "LED count wrapped");

    hello.capabilities.ledCount = 257;
    expectInvalidHello(envelope, hello, "oversized LED count was accepted");
}

void testParsesProtocolV1HelloAck()
{
    std::string json = R"({
        "v": 1,
        "type": "hello_ack",
        "message_id": "7d2598af-ae08-4025-94bb-53007808fb38",
        "sent_at_ms": 0,
        "payload": {
            "connection_id": "bdce4ce9-ec1d-4d06-bc26-45cb0474a8b6",
            "selected_protocol_version": 1,
            "heartbeat_interval_ms": 15000,
            "max_command_timeout_ms": 5000,
            "server_version": "0.1.0"
        }
    })";

    HelloAck acknowledgement;
    expect(parseHelloAckJson(json, acknowledgement) == ProtocolError::None, "ack parse failed");
    expect(
        acknowledgement.connectionId == "bdce4ce9-ec1d-4d06-bc26-45cb0474a8b6",
        "connection id mismatch"
    );
    expect(acknowledgement.heartbeatIntervalMs == 15000, "heartbeat mismatch");
    expect(acknowledgement.maxCommandTimeoutMs == 5000, "command timeout mismatch");
    expect(acknowledgement.serverVersion == "0.1.0", "server version mismatch");
}

void testRejectsHelloAckHeartbeatOutsideProtocolV1()
{
    const std::string json = R"({
        "v": 1,
        "type": "hello_ack",
        "message_id": "7d2598af-ae08-4025-94bb-53007808fb38",
        "sent_at_ms": 0,
        "payload": {
            "connection_id": "bdce4ce9-ec1d-4d06-bc26-45cb0474a8b6",
            "selected_protocol_version": 1,
            "heartbeat_interval_ms": 999,
            "max_command_timeout_ms": 5000,
            "server_version": "0.1.0"
        }
    })";

    HelloAck acknowledgement;
    expect(
        parseHelloAckJson(json, acknowledgement) == ProtocolError::InvalidArgument,
        "invalid heartbeat was accepted"
    );
    expect(acknowledgement.connectionId.empty(), "invalid ack retained connection state");
}

void testRejectsHelloAckProtocolVersionMismatch()
{
    const std::string json = R"({
        "v": 1,
        "type": "hello_ack",
        "message_id": "7d2598af-ae08-4025-94bb-53007808fb38",
        "sent_at_ms": 0,
        "payload": {
            "connection_id": "bdce4ce9-ec1d-4d06-bc26-45cb0474a8b6",
            "selected_protocol_version": 2,
            "heartbeat_interval_ms": 15000,
            "max_command_timeout_ms": 5000,
            "server_version": "0.1.0"
        }
    })";

    HelloAck acknowledgement;
    expect(
        parseHelloAckJson(json, acknowledgement) == ProtocolError::InvalidArgument,
        "unsupported protocol version was accepted"
    );
}

void testRejectsHelloAckCommandTimeoutOutsideProtocolV1()
{
    const std::string json = R"({
        "v": 1,
        "type": "hello_ack",
        "message_id": "7d2598af-ae08-4025-94bb-53007808fb38",
        "sent_at_ms": 0,
        "payload": {
            "connection_id": "bdce4ce9-ec1d-4d06-bc26-45cb0474a8b6",
            "selected_protocol_version": 1,
            "heartbeat_interval_ms": 15000,
            "max_command_timeout_ms": 99,
            "server_version": "0.1.0"
        }
    })";

    HelloAck acknowledgement;
    expect(
        parseHelloAckJson(json, acknowledgement) == ProtocolError::InvalidArgument,
        "invalid command timeout was accepted"
    );
}

void testRejectsHelloAckWithInvalidConnectionIdentity()
{
    const std::string json = R"({
        "v": 1,
        "type": "hello_ack",
        "message_id": "7d2598af-ae08-4025-94bb-53007808fb38",
        "sent_at_ms": 0,
        "payload": {
            "connection_id": "not-a-uuid",
            "selected_protocol_version": 1,
            "heartbeat_interval_ms": 15000,
            "max_command_timeout_ms": 5000,
            "server_version": "0.1.0"
        }
    })";

    HelloAck acknowledgement;
    expect(
        parseHelloAckJson(json, acknowledgement) == ProtocolError::InvalidArgument,
        "invalid connection UUID was accepted"
    );
}

void testRejectsHelloAckWithWrongEnvelope()
{
    std::string json = R"({
        "v": 2,
        "type": "hello_ack",
        "message_id": "7d2598af-ae08-4025-94bb-53007808fb38",
        "sent_at_ms": 0,
        "payload": {
            "connection_id": "bdce4ce9-ec1d-4d06-bc26-45cb0474a8b6",
            "selected_protocol_version": 1,
            "heartbeat_interval_ms": 15000,
            "max_command_timeout_ms": 5000,
            "server_version": "0.1.0"
        }
    })";

    HelloAck acknowledgement;
    expect(
        parseHelloAckJson(json, acknowledgement) == ProtocolError::InvalidArgument,
        "wrong envelope version was accepted"
    );

    json.replace(json.find("\"v\": 2"), 6, "\"v\": 1");
    json.replace(json.find("hello_ack"), 9, "command");
    expect(
        parseHelloAckJson(json, acknowledgement) == ProtocolError::InvalidArgument,
        "wrong message type was accepted"
    );

    json.replace(json.find("command"), 7, "hello_ack");
    json.replace(json.find("7d2598af-ae08-4025-94bb-53007808fb38"), 36, "bad-uuid");
    expect(
        parseHelloAckJson(json, acknowledgement) == ProtocolError::InvalidArgument,
        "invalid envelope message UUID was accepted"
    );

    json.replace(json.find("bad-uuid"), 8, "7d2598af-ae08-4025-94bb-53007808fb38");
    json.replace(json.find("0.1.0"), 5, "");
    expect(
        parseHelloAckJson(json, acknowledgement) == ProtocolError::InvalidArgument,
        "empty server version was accepted"
    );
}

void testRejectsHelloAckWithCoercedNumericType()
{
    std::string json = validHelloAckJson();
    json.replace(json.find("15000"), 5, "\"15000\"");

    HelloAck acknowledgement;
    expect(
        parseHelloAckJson(json, acknowledgement) == ProtocolError::InvalidArgument,
        "string heartbeat was coerced to an integer"
    );
}

void testRejectsMalformedMissingDeepAndOversizedHelloAck()
{
    HelloAck acknowledgement;
    expect(
        parseHelloAckJson("{", acknowledgement) == ProtocolError::InvalidArgument,
        "malformed JSON was accepted"
    );
    expect(
        parseHelloAckJson(R"({"v":1,"type":"hello_ack"})", acknowledgement)
            == ProtocolError::InvalidArgument,
        "missing payload was accepted"
    );
    expect(
        parseHelloAckJson(R"({"a":{"b":{"c":{"d":{"e":{"f":{"g":{"h":{"i":1}}}}}}}}})", acknowledgement)
            == ProtocolError::InvalidArgument,
        "over-deep JSON was accepted"
    );
    expect(
        parseHelloAckJson(std::string(16385, ' '), acknowledgement)
            == ProtocolError::MessageTooLarge,
        "oversized JSON was not classified"
    );
}

}  // namespace

int main()
{
    testBuildsBoundedProtocolV1Hello();
    testRejectsInvalidHelloIdentityAndCodec();
    testRejectsProtocolTimestampsOutsideSignedJsonRange();
    testRejectsAudioFormatsOutsideProtocolV1();
    testRejectsInvalidBoundedHelloText();
    testPreservesMaximumLedCapability();
    testParsesProtocolV1HelloAck();
    testRejectsHelloAckHeartbeatOutsideProtocolV1();
    testRejectsHelloAckProtocolVersionMismatch();
    testRejectsHelloAckCommandTimeoutOutsideProtocolV1();
    testRejectsHelloAckWithInvalidConnectionIdentity();
    testRejectsHelloAckWithWrongEnvelope();
    testRejectsHelloAckWithCoercedNumericType();
    testRejectsMalformedMissingDeepAndOversizedHelloAck();
    return 0;
}
