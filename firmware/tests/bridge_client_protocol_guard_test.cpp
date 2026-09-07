#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>

#include <stackchan_bridge_client/protocol_guard.h>

namespace {

using stackchan::bridge_client::EnvelopeMetadata;
using stackchan::bridge_client::InvalidMessageWindow;
using stackchan::bridge_client::PeerErrorBuildError;
using stackchan::bridge_client::PeerErrorCode;
using stackchan::bridge_client::RemoteErrorCode;
using stackchan::bridge_client::RemoteErrorMessage;
using stackchan::bridge_client::RemoteErrorParseError;
using stackchan::bridge_client::buildPeerErrorJson;
using stackchan::bridge_client::parseRemoteErrorJson;

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
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 42;
    return envelope;
}

void testBuildsBoundedSafePeerErrors()
{
    std::string output;
    expect(
        buildPeerErrorJson(
            validEnvelope(),
            PeerErrorCode::InvalidState,
            "Audio output stream is not active",
            output
        ) == PeerErrorBuildError::None,
        "peer error was not built"
    );
    expect(output.find(R"("type":"error")") != std::string::npos, "wrong error type");
    expect(
        output.find(R"("code":"INVALID_STATE")") != std::string::npos,
        "stable error code changed"
    );
    expect(output.find("detail") == std::string::npos, "safe peer error leaked detail");
}

void testRejectsUnsafePeerErrorWithoutRetainingOutput()
{
    std::string output = "stale output";
    expect(
        buildPeerErrorJson(
            validEnvelope(), PeerErrorCode::InvalidMessage, "bad\nmessage", output
        ) == PeerErrorBuildError::InvalidArgument,
        "control text was accepted"
    );
    expect(output.empty(), "invalid peer error retained output");

    EnvelopeMetadata envelope = validEnvelope();
    envelope.sentAtMs = static_cast<std::uint64_t>(
        std::numeric_limits<std::int64_t>::max()
    ) + 1;
    output = "stale output";
    expect(
        buildPeerErrorJson(
            envelope, PeerErrorCode::InvalidArgument, "Invalid command arguments", output
        ) == PeerErrorBuildError::InvalidArgument,
        "out-of-range error timestamp was accepted"
    );
    expect(output.empty(), "invalid timestamp retained peer error output");
}

void testParsesEveryStableRemoteErrorCode()
{
    const char* codes[] = {
        "UNSUPPORTED_VERSION",
        "UNAUTHORIZED",
        "UNKNOWN_DEVICE",
        "INVALID_MESSAGE",
        "INVALID_ARGUMENT",
        "INVALID_STATE",
        "COMMAND_TIMEOUT",
        "DEVICE_BUSY",
        "AUDIO_DECODE_ERROR",
        "AUDIO_ENCODE_ERROR",
        "CAPTURE_FAILED",
        "INTERNAL_ERROR",
    };
    for (const char* code : codes) {
        const std::string input = std::string(R"({
            "v":1,"type":"error",
            "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
            "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
            "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874",
            "sent_at_ms":42,"payload":{"code":")")
            + code + R"(","message":"remote protocol failure"}})";
        RemoteErrorMessage output;
        expect(
            parseRemoteErrorJson(input, output) == RemoteErrorParseError::None,
            "stable remote error code was rejected"
        );
    }

    const std::string decodeError = R"({
        "v":1,"type":"error",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874",
        "sent_at_ms":42,"payload":{"code":"AUDIO_DECODE_ERROR",
            "message":"remote protocol failure"}})";
    RemoteErrorMessage output;
    expect(
        parseRemoteErrorJson(decodeError, output) == RemoteErrorParseError::None
            && output.code == RemoteErrorCode::AudioDecodeError
            && output.turnId == "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7"
            && output.streamId == "a9d1c15a-f728-4293-87fc-1d3cae5f1874",
        "routed audio decode error was not parsed"
    );
}

void testRejectsInvalidRemoteErrorFields()
{
    const std::string input = R"({
        "v":1,"type":"error",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":null,"sent_at_ms":42,
        "payload":{"code":"NOT_A_PROTOCOL_CODE","message":"remote failure"}})";
    RemoteErrorMessage output;
    expect(
        parseRemoteErrorJson(input, output) == RemoteErrorParseError::InvalidArgument,
        "invalid remote error fields were accepted"
    );
}

void testThirdInvalidMessageWithinTenSecondsClosesTheWindow()
{
    InvalidMessageWindow window;
    expect(!window.observe(1'000), "first invalid message closed connection");
    expect(!window.observe(5'000), "second invalid message closed connection");
    expect(window.observe(10'999), "third invalid message in window was not terminal");
}

void testInvalidMessageWindowExpiresAndHandlesClockWrap()
{
    InvalidMessageWindow window;
    expect(!window.observe(100), "first invalid message was terminal");
    expect(!window.observe(10'100), "expired invalid message was retained");
    expect(!window.observe(10'101), "second message in fresh window was terminal");
    expect(window.observe(10'102), "third message in fresh window was not terminal");

    window.reset();
    const std::uint32_t nearWrap = std::numeric_limits<std::uint32_t>::max() - 5;
    expect(!window.observe(nearWrap), "near-wrap first message was terminal");
    expect(!window.observe(3), "clock wrap expired an active window");
    expect(window.observe(4), "clock wrap lost the third message");
}

}  // namespace

int main()
{
    testBuildsBoundedSafePeerErrors();
    testRejectsUnsafePeerErrorWithoutRetainingOutput();
    testParsesEveryStableRemoteErrorCode();
    testRejectsInvalidRemoteErrorFields();
    testThirdInvalidMessageWithinTenSecondsClosesTheWindow();
    testInvalidMessageWindowExpiresAndHandlesClockWrap();
    return 0;
}
