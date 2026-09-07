#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>

#include <stackchan_bridge_client/audio_input.h>

namespace {

using stackchan::bridge_client::AudioInputBuildError;
using stackchan::bridge_client::AudioInputEndReason;
using stackchan::bridge_client::AudioInputTrigger;
using stackchan::bridge_client::EnvelopeMetadata;
using stackchan::bridge_client::buildAudioInputEndJson;
using stackchan::bridge_client::buildAudioInputStartJson;

constexpr char kTurnId[] = "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7";
constexpr char kStreamId[] = "a9d1c15a-f728-4293-87fc-1d3cae5f1874";

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

EnvelopeMetadata envelope()
{
    EnvelopeMetadata value;
    value.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    value.sentAtMs = 25;
    return value;
}

void testAudioInputStartBuildsTheNegotiatedOwnedFormat()
{
    std::string output;

    const auto error = buildAudioInputStartJson(
        envelope(), kTurnId, kStreamId, AudioInputTrigger::Touch, 60, output
    );

    expect(error == AudioInputBuildError::None, "audio input start was not built");
    expect(output.find(R"("type":"audio.input.start")") != std::string::npos, "wrong type");
    expect(output.find(R"("turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7")")
               != std::string::npos,
           "turn ownership was lost");
    expect(output.find(R"("stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874")")
               != std::string::npos,
           "stream ownership was lost");
    expect(output.find(R"("codec":"opus")") != std::string::npos, "codec changed");
    expect(output.find(R"("sample_rate":16000)") != std::string::npos, "sample rate changed");
    expect(output.find(R"("frame_ms":60)") != std::string::npos, "frame duration changed");
    expect(output.find(R"("trigger":"touch")") != std::string::npos, "trigger changed");
}

void testAudioInputEndBuildsEveryStableReason()
{
    const struct {
        AudioInputEndReason reason;
        const char* text;
    } cases[] = {
        {AudioInputEndReason::Silence, "silence"},
        {AudioInputEndReason::MaxDuration, "max_duration"},
        {AudioInputEndReason::UserCancel, "user_cancel"},
        {AudioInputEndReason::DeviceError, "device_error"},
        {AudioInputEndReason::Disconnect, "disconnect"},
    };
    for (const auto& value : cases) {
        std::string output;
        const auto error = buildAudioInputEndJson(
            envelope(), kTurnId, kStreamId, value.reason, output
        );
        expect(error == AudioInputBuildError::None, "audio input end was not built");
        expect(output.find(R"("type":"audio.input.end")") != std::string::npos, "wrong type");
        expect(output.find(std::string(R"("reason":")") + value.text + R"(")")
                   != std::string::npos,
               "end reason changed");
    }
}

void testInvalidAudioInputIdentityAndFrameAreRejectedAtomically()
{
    std::string output = "unchanged";
    expect(
        buildAudioInputStartJson(
            envelope(), "not-a-uuid", kStreamId, AudioInputTrigger::Touch, 60, output
        ) == AudioInputBuildError::InvalidArgument,
        "invalid turn ID was accepted"
    );
    expect(output.empty(), "failed identity build retained partial JSON");
    output = "unchanged";
    expect(
        buildAudioInputStartJson(
            envelope(), kTurnId, kStreamId, AudioInputTrigger::Touch, 30, output
        ) == AudioInputBuildError::InvalidArgument,
        "invalid frame duration was accepted"
    );
    expect(output.empty(), "failed frame build retained partial JSON");
}

void testAudioInputRejectsTimestampOutsideSignedJsonRange()
{
    EnvelopeMetadata invalidEnvelope = envelope();
    invalidEnvelope.sentAtMs = static_cast<std::uint64_t>(
        std::numeric_limits<std::int64_t>::max()
    ) + 1;

    std::string output = "stale output";
    expect(
        buildAudioInputStartJson(
            invalidEnvelope, kTurnId, kStreamId, AudioInputTrigger::Touch, 60, output
        ) == AudioInputBuildError::InvalidArgument,
        "out-of-range audio timestamp was accepted"
    );
    expect(output.empty(), "invalid audio timestamp retained output");
}

}  // namespace

int main()
{
    testAudioInputStartBuildsTheNegotiatedOwnedFormat();
    testAudioInputEndBuildsEveryStableReason();
    testInvalidAudioInputIdentityAndFrameAreRejectedAtomically();
    testAudioInputRejectsTimestampOutsideSignedJsonRange();
    return 0;
}
