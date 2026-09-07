#include <cstdlib>
#include <iostream>
#include <limits>

#include <stackchan_bridge_client/command.h>

namespace {

using stackchan::bridge_client::Command;
using stackchan::bridge_client::CommandErrorCode;
using stackchan::bridge_client::CommandExecutionResult;
using stackchan::bridge_client::CommandName;
using stackchan::bridge_client::CommandParseError;
using stackchan::bridge_client::CommandResultBuildError;
using stackchan::bridge_client::CommandResultField;
using stackchan::bridge_client::EnvelopeMetadata;
using stackchan::bridge_client::buildCommandResultJson;
using stackchan::bridge_client::parseCommandJson;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testGetStatusCommandIsParsed()
{
    const std::string input = R"({
        "v": 1,
        "type": "command",
        "message_id": "519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id": "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        "sent_at_ms": 1,
        "payload": {"name": "device.get_status", "args": {}}
    })";
    Command command;

    const auto error = parseCommandJson(input, command);

    expect(error == CommandParseError::None, "get-status command was rejected");
    expect(command.name == CommandName::DeviceGetStatus, "wrong command name");
    expect(
        command.requestId == "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        "request ID was not retained"
    );
}

void testCommandEnvelopeRejectsOutOfRangeAndMalformedOptionalFields()
{
    const char* invalidMessages[] = {
        R"([])",
        R"({
            "v":1,"type":"command",
            "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
            "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
            "sent_at_ms":9223372036854775808,
            "payload":{"name":"device.get_status","args":{}}
        })",
        R"({
            "v":1,"type":"command",
            "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
            "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
            "turn_id":7,"sent_at_ms":1,
            "payload":{"name":"device.get_status","args":{}}
        })",
        R"({
            "v":1,"type":"command",
            "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
            "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
            "stream_id":"not-a-uuid","sent_at_ms":1,
            "payload":{"name":"device.get_status","args":{}}
        })",
        R"({
            "v":1,"type":"command",
            "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
            "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
            "device_id":"bad id","sent_at_ms":1,
            "payload":{"name":"device.get_status","args":{}}
        })",
    };
    for (const char* input : invalidMessages) {
        Command command;
        command.requestId = "stale";
        expect(
            parseCommandJson(input, command) == CommandParseError::InvalidMessage,
            "malformed command envelope was accepted"
        );
        expect(command.requestId.empty(), "failed envelope parse retained stale output");
    }
}

void testCommandRetainsValidOptionalEnvelopeOwnership()
{
    const std::string input = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874",
        "device_id":"stackchan-001","sent_at_ms":9223372036854775807,
        "payload":{"name":"device.get_status","args":{}}
    })";
    Command command;

    expect(
        parseCommandJson(input, command) == CommandParseError::None,
        "valid optional envelope ownership was rejected"
    );
    expect(
        command.streamId == "a9d1c15a-f728-4293-87fc-1d3cae5f1874",
        "stream ownership was not retained"
    );
    expect(command.deviceId == "stackchan-001", "device ownership was not retained");
}

void testSetVolumeCommandRetainsTheValidatedInteger()
{
    const std::string input = R"({
        "v": 1,
        "type": "command",
        "message_id": "519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id": "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        "sent_at_ms": 2,
        "payload": {"name": "audio.set_volume", "args": {"volume": 75}}
    })";
    Command command;

    const auto error = parseCommandJson(input, command);

    expect(error == CommandParseError::None, "set-volume command was rejected");
    expect(command.name == CommandName::AudioSetVolume, "wrong set-volume command name");
    expect(command.arguments.volume == 75, "volume was not retained");
}

void testInvalidVolumesAreRejectedAtomically()
{
    const char* invalidArguments[] = {
        R"({"volume":-1})",
        R"({"volume":101})",
        R"({"volume":75.5})",
        R"({"volume":true})",
        R"({"volume":75,"extra":0})",
    };

    for (const char* arguments : invalidArguments) {
        const std::string input = std::string(R"({
            "v":1,
            "type":"command",
            "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
            "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
            "sent_at_ms":3,
            "payload":{"name":"audio.set_volume","args":)")
            + arguments + "}}";
        Command command;
        command.name = CommandName::DeviceGetStatus;
        command.requestId = "stale";

        const auto error = parseCommandJson(input, command);

        expect(error == CommandParseError::InvalidArgument, "invalid volume was accepted");
        expect(command.name == CommandName::Unknown, "invalid volume retained a command");
        expect(command.requestId.empty(), "invalid volume retained a request ID");
    }
}

void testSetBrightnessCommandRetainsTheValidatedInteger()
{
    const std::string input = R"({
        "v":1,
        "type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        "sent_at_ms":4,
        "payload":{"name":"display.set_brightness","args":{"brightness":80}}
    })";
    Command command;

    const auto error = parseCommandJson(input, command);

    expect(error == CommandParseError::None, "set-brightness command was rejected");
    expect(command.name == CommandName::DisplaySetBrightness, "wrong brightness command name");
    expect(command.arguments.brightness == 80, "brightness was not retained");
}

void testShowTextCommandRetainsBoundedUtf8AndPresentationValues()
{
    const std::string input = R"({
        "v":1,
        "type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        "sent_at_ms":5,
        "payload":{"name":"display.show_text","args":{
            "text":"こんにちは","duration_ms":3000,"priority":4
        }}
    })";
    Command command;

    const auto error = parseCommandJson(input, command);

    expect(error == CommandParseError::None, "show-text command was rejected");
    expect(command.name == CommandName::DisplayShowText, "wrong show-text command name");
    expect(command.arguments.text == "こんにちは", "display text was not retained");
    expect(command.arguments.durationMs == 3000, "display duration was not retained");
    expect(command.arguments.priority == 4, "display priority was not retained");
}

void testExpressionCommandAcceptsOnlyTheProtocolEnum()
{
    const std::string valid = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":6,
        "payload":{"name":"avatar.set_expression","args":{"expression":"thinking"}}
    })";
    Command command;

    const auto error = parseCommandJson(valid, command);

    expect(error == CommandParseError::None, "valid expression was rejected");
    expect(command.name == CommandName::AvatarSetExpression, "wrong expression command name");
    expect(command.arguments.expression == "thinking", "expression was not retained");
}

void testBlinkCommandRetainsAStrictBoolean()
{
    const std::string valid = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":7,
        "payload":{"name":"avatar.set_blink","args":{"enabled":true}}
    })";
    Command command;

    const auto error = parseCommandJson(valid, command);

    expect(error == CommandParseError::None, "valid blink command was rejected");
    expect(command.name == CommandName::AvatarSetBlink, "wrong blink command name");
    expect(command.arguments.enabled, "blink value was not retained");
}

void testHeadAnglesCommandRetainsProtocolDomainValues()
{
    const std::string input = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":8,
        "payload":{"name":"head.set_angles","args":{
            "yaw":15.5,"pitch":-40,"speed":30
        }}
    })";
    Command command;

    const auto error = parseCommandJson(input, command);

    expect(error == CommandParseError::None, "valid head angles were rejected");
    expect(command.name == CommandName::HeadSetAngles, "wrong head command name");
    expect(command.arguments.yaw == 15.5, "yaw was not retained");
    expect(command.arguments.pitch == -40.0, "pitch was not retained");
    expect(command.arguments.hasSpeed, "optional speed presence was lost");
    expect(command.arguments.speed == 30, "head speed was not retained");
}

void testReadOnlyAndClearCommandsRequireEmptyArguments()
{
    struct Example {
        const char* name;
        CommandName expected;
    };
    const Example examples[] = {
        {"device.get_info", CommandName::DeviceGetInfo},
        {"head.get_angles", CommandName::HeadGetAngles},
        {"led.clear", CommandName::LedClear},
    };

    for (const auto& example : examples) {
        const std::string input = std::string(R"({
            "v":1,"type":"command",
            "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
            "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":9,
            "payload":{"name":")") + example.name + R"(","args":{}}
        })";
        Command command;

        const auto error = parseCommandJson(input, command);

        expect(error == CommandParseError::None, "empty-argument command was rejected");
        expect(command.name == example.expected, "empty-argument command name changed");
    }
}

void testHeadHomeAcceptsAnOptionalBoundedSpeed()
{
    const std::string input = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":10,
        "payload":{"name":"head.home","args":{"speed":10}}
    })";
    Command command;

    const auto error = parseCommandJson(input, command);

    expect(error == CommandParseError::None, "head-home command was rejected");
    expect(command.name == CommandName::HeadHome, "wrong home command name");
    expect(command.arguments.hasSpeed, "home speed presence was lost");
    expect(command.arguments.speed == 10, "home speed was not retained");
}

void testLedCommandsRetainBoundedRgbAndOptionalIndex()
{
    const std::string setOne = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":11,
        "payload":{"name":"led.set","args":{"index":3,"r":255,"g":64,"b":0}}
    })";
    Command command;

    auto error = parseCommandJson(setOne, command);

    expect(error == CommandParseError::None, "single-LED command was rejected");
    expect(command.name == CommandName::LedSet, "wrong single-LED command name");
    expect(command.arguments.index == 3, "LED index was not retained");
    expect(command.arguments.red == 255, "red channel was not retained");
    expect(command.arguments.green == 64, "green channel was not retained");
    expect(command.arguments.blue == 0, "blue channel was not retained");

    const std::string setAll = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":12,
        "payload":{"name":"led.set_all","args":{"r":1,"g":2,"b":3}}
    })";

    error = parseCommandJson(setAll, command);

    expect(error == CommandParseError::None, "all-LED command was rejected");
    expect(command.name == CommandName::LedSetAll, "wrong all-LED command name");
    expect(command.arguments.red == 1, "all-LED red channel changed");
    expect(command.arguments.green == 2, "all-LED green channel changed");
    expect(command.arguments.blue == 3, "all-LED blue channel changed");
}

void testCameraCaptureRetainsUuidAndBoundedQuality()
{
    const std::string input = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc","sent_at_ms":13,
        "payload":{"name":"camera.capture","args":{
            "capture_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7","quality":80
        }}
    })";
    Command command;

    const auto error = parseCommandJson(input, command);

    expect(error == CommandParseError::None, "camera capture was rejected");
    expect(command.name == CommandName::CameraCapture, "wrong camera command name");
    expect(
        command.arguments.captureId == "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "capture ID was not retained"
    );
    expect(command.arguments.quality == 80, "capture quality was not retained");
}

void testSpeechCancelRequiresAndRetainsTurnId()
{
    const std::string input = R"({
        "v":1,"type":"command",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7","sent_at_ms":14,
        "payload":{"name":"speech.cancel","args":{}}
    })";
    Command command;

    const auto error = parseCommandJson(input, command);

    expect(error == CommandParseError::None, "speech cancel was rejected");
    expect(command.name == CommandName::SpeechCancel, "wrong cancel command name");
    expect(
        command.turnId == "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "cancel turn ID was not retained"
    );
}

void testMotionRejectionBuildsACorrelatedSafeErrorResult()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 15;
    CommandExecutionResult result;
    result.errorCode = CommandErrorCode::InvalidState;
    result.errorMessage = "motion unavailable";
    std::string output;

    const auto error = buildCommandResultJson(
        envelope,
        "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        result,
        output
    );

    expect(error == CommandResultBuildError::None, "motion rejection result was not built");
    expect(output.find(R"("type":"command_result")") != std::string::npos, "wrong result type");
    expect(
        output.find(R"("request_id":"79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")")
            != std::string::npos,
        "request ID was not correlated"
    );
    expect(output.find(R"("ok":false)") != std::string::npos, "error result was marked successful");
    expect(output.find(R"("code":"INVALID_STATE")") != std::string::npos, "wrong error code");
    expect(output.find("motion unavailable") != std::string::npos, "safe error message was lost");
}

void testInvalidArgumentBuildsAStableErrorCode()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 16;
    CommandExecutionResult result;
    result.errorCode = CommandErrorCode::InvalidArgument;
    result.errorMessage = "value outside supported range";
    std::string output;

    const auto error = buildCommandResultJson(
        envelope,
        "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        result,
        output
    );

    expect(error == CommandResultBuildError::None, "invalid argument result was not built");
    expect(
        output.find(R"("code":"INVALID_ARGUMENT")") != std::string::npos,
        "invalid argument code was not retained"
    );
}

void testDeviceBusyBuildsAStableErrorCode()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 17;
    CommandExecutionResult result;
    result.errorCode = CommandErrorCode::DeviceBusy;
    result.errorMessage = "camera is busy";
    std::string output;

    const auto error = buildCommandResultJson(
        envelope,
        "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        result,
        output
    );

    expect(error == CommandResultBuildError::None, "device busy result was not built");
    expect(
        output.find(R"("code":"DEVICE_BUSY")") != std::string::npos,
        "device busy code was not retained"
    );
}

void testSuccessfulSetterBuildsAnEmptyResultObject()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 16;
    CommandExecutionResult result;
    result.ok = true;
    std::string output;

    const auto error = buildCommandResultJson(
        envelope,
        "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        result,
        output
    );

    expect(error == CommandResultBuildError::None, "successful result was not built");
    expect(output.find(R"("ok":true)") != std::string::npos, "success result was marked failed");
    expect(output.find(R"("result":{})") != std::string::npos, "empty result object was missing");
}

void testSuccessfulStatusBuildsBoundedScalarFields()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 17;
    CommandExecutionResult result;
    result.ok = true;
    result.fields = {
        CommandResultField{"state", std::string("IDLE")},
        CommandResultField{"volume", std::int64_t{75}},
        CommandResultField{"connected", true},
    };
    std::string output;

    const auto error = buildCommandResultJson(
        envelope,
        "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
        result,
        output
    );

    expect(error == CommandResultBuildError::None, "status result was not built");
    expect(output.find(R"("state":"IDLE")") != std::string::npos, "state field was lost");
    expect(output.find(R"("volume":75)") != std::string::npos, "integer field was lost");
    expect(output.find(R"("connected":true)") != std::string::npos, "boolean field was lost");
}

void testCommandResultRejectsTimestampOutsideSignedJsonRange()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = static_cast<std::uint64_t>(
        std::numeric_limits<std::int64_t>::max()
    ) + 1;
    CommandExecutionResult result;
    result.ok = true;
    std::string output = "stale output";

    expect(
        buildCommandResultJson(
            envelope,
            "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
            result,
            output
        ) == CommandResultBuildError::InvalidArgument,
        "out-of-range command result timestamp was accepted"
    );
    expect(output.empty(), "invalid command result timestamp retained output");
}

}  // namespace


int main()
{
    testGetStatusCommandIsParsed();
    testCommandEnvelopeRejectsOutOfRangeAndMalformedOptionalFields();
    testCommandRetainsValidOptionalEnvelopeOwnership();
    testSetVolumeCommandRetainsTheValidatedInteger();
    testInvalidVolumesAreRejectedAtomically();
    testSetBrightnessCommandRetainsTheValidatedInteger();
    testShowTextCommandRetainsBoundedUtf8AndPresentationValues();
    testExpressionCommandAcceptsOnlyTheProtocolEnum();
    testBlinkCommandRetainsAStrictBoolean();
    testHeadAnglesCommandRetainsProtocolDomainValues();
    testReadOnlyAndClearCommandsRequireEmptyArguments();
    testHeadHomeAcceptsAnOptionalBoundedSpeed();
    testLedCommandsRetainBoundedRgbAndOptionalIndex();
    testCameraCaptureRetainsUuidAndBoundedQuality();
    testSpeechCancelRequiresAndRetainsTurnId();
    testMotionRejectionBuildsACorrelatedSafeErrorResult();
    testInvalidArgumentBuildsAStableErrorCode();
    testDeviceBusyBuildsAStableErrorCode();
    testSuccessfulSetterBuildsAnEmptyResultObject();
    testSuccessfulStatusBuildsBoundedScalarFields();
    testCommandResultRejectsTimestampOutsideSignedJsonRange();
    return 0;
}
