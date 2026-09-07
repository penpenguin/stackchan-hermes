#include <cstdlib>
#include <iostream>
#include <string>

#include <stackchan_bridge_client/event.h>

namespace {

using stackchan::bridge_client::DeviceFaultCode;
using stackchan::bridge_client::DeviceFaultEventType;
using stackchan::bridge_client::EnvelopeMetadata;
using stackchan::bridge_client::EventBuildError;
using stackchan::bridge_client::buildDeviceFaultEventJson;
using stackchan::bridge_client::buildTouchTapEventJson;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testAudioDecodeFailureBuildsADeviceErrorEvent()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 40;
    std::string output;

    expect(
        buildDeviceFaultEventJson(
            envelope,
            "stackchan-001",
            DeviceFaultEventType::DeviceError,
            DeviceFaultCode::AudioDecodeError,
            "Audio playback could not be decoded",
            output
        ) == EventBuildError::None,
        "audio decode failure event was not built"
    );
    expect(output.find(R"("name":"device.error")") != std::string::npos,
           "wrong device event name");
    expect(output.find(R"("code":"AUDIO_DECODE_ERROR")") != std::string::npos,
           "wrong device error code");
    expect(output.find("Audio playback could not be decoded") != std::string::npos,
           "safe device error message was lost");
}

void testDeviceFaultRejectsControlTextAtomically()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 41;
    std::string output = "stale";

    expect(
        buildDeviceFaultEventJson(
            envelope,
            "stackchan-001",
            DeviceFaultEventType::DeviceError,
            DeviceFaultCode::InternalError,
            "unsafe\nmessage",
            output
        ) == EventBuildError::InvalidArgument,
        "device fault accepted control text"
    );
    expect(output.empty(), "failed device fault build retained stale output");
}

void testTouchTapBuildsAnOwnedBoundedEvent()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 42;
    std::string output;

    expect(
        buildTouchTapEventJson(envelope, "stackchan-001", 160, 0, output)
            == EventBuildError::None,
        "touch tap event was not built"
    );
    expect(output.find(R"("name":"touch.tap")") != std::string::npos,
           "wrong touch event name");
    expect(output.find(R"("device_id":"stackchan-001")") != std::string::npos,
           "touch event lost device ownership");
    expect(output.find(R"("x":160)") != std::string::npos, "touch x coordinate changed");
    expect(output.find(R"("y":0)") != std::string::npos, "touch y coordinate changed");
}

void testTouchTapRejectsAnOutOfBoundsCoordinateAtomically()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 43;
    std::string output = "stale";

    expect(
        buildTouchTapEventJson(envelope, "stackchan-001", 320, 0, output)
            == EventBuildError::InvalidArgument,
        "touch tap accepted an out-of-bounds coordinate"
    );
    expect(output.empty(), "failed touch event build retained stale output");
}

}  // namespace

int main()
{
    testAudioDecodeFailureBuildsADeviceErrorEvent();
    testDeviceFaultRejectsControlTextAtomically();
    testTouchTapBuildsAnOwnedBoundedEvent();
    testTouchTapRejectsAnOutOfBoundsCoordinateAtomically();
    return 0;
}
