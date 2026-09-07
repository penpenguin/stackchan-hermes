#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

#include <stackchan_bridge_client/audio_output.h>
#include <stackchan_bridge_client/protocol.h>

namespace {

using stackchan::bridge_client::AudioOutputBuffer;
using stackchan::bridge_client::AudioOutputControl;
using stackchan::bridge_client::AudioOutputControlType;
using stackchan::bridge_client::AudioOutputEndReason;
using stackchan::bridge_client::AudioOutputError;
using stackchan::bridge_client::AudioOutputParseError;
using stackchan::bridge_client::AudioOutputStream;
using stackchan::bridge_client::AudioBufferEventBuildError;
using stackchan::bridge_client::AudioBufferEventType;
using stackchan::bridge_client::EnvelopeMetadata;
using stackchan::bridge_client::buildAudioBufferEventJson;
using stackchan::bridge_client::kAudioOutputQueuePackets;
using stackchan::bridge_client::kMaxAudioPacketBytes;
using stackchan::bridge_client::parseAudioOutputControlJson;

constexpr char kTurnId[] = "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7";
constexpr char kStreamId[] = "a9d1c15a-f728-4293-87fc-1d3cae5f1874";

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

AudioOutputStream validStream()
{
    AudioOutputStream stream;
    stream.turnId = kTurnId;
    stream.streamId = kStreamId;
    stream.codec = "opus";
    stream.sampleRate = 16'000;
    stream.channels = 1;
    stream.frameMs = 60;
    stream.expectedDurationMs = 2'000;
    return stream;
}

void testBinaryOutsideAnOpenStreamIsDropped()
{
    AudioOutputBuffer buffer;
    const std::uint8_t packet[] = {1, 2, 3};

    const auto error = buffer.push(packet, sizeof(packet));

    expect(error == AudioOutputError::InvalidState, "closed stream accepted binary");
    expect(buffer.queuedPackets() == 0, "closed stream queued binary");
    expect(buffer.droppedPackets() == 1, "closed-stream drop was not counted");
}

void testOpenStreamQueuesOnlyBoundedPackets()
{
    AudioOutputBuffer buffer;
    expect(buffer.start(validStream()) == AudioOutputError::None, "valid stream start failed");

    const std::uint8_t packet[] = {4, 5, 6};
    expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "valid packet failed");
    expect(buffer.queuedPackets() == 1, "valid packet was not queued");

    std::vector<std::uint8_t> oversized(kMaxAudioPacketBytes + 1, 7);
    expect(
        buffer.push(oversized.data(), oversized.size()) == AudioOutputError::PacketTooLarge,
        "oversized packet was accepted"
    );
    expect(buffer.queuedPackets() == 1, "oversized packet changed the queue");
    expect(buffer.droppedPackets() == 1, "oversized packet drop was not counted");
}

void testOutputOverflowRejectsTheNewPacket()
{
    AudioOutputBuffer buffer;
    expect(buffer.start(validStream()) == AudioOutputError::None, "valid stream start failed");
    const std::uint8_t packet[] = {8};
    for (std::size_t index = 0; index < kAudioOutputQueuePackets; ++index) {
        expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "queue filled early");
    }

    expect(
        buffer.push(packet, sizeof(packet)) == AudioOutputError::QueueOverflow,
        "queue overflow did not reject the new packet"
    );
    expect(
        buffer.queuedPackets() == kAudioOutputQueuePackets,
        "queue overflow changed retained packets"
    );
    expect(buffer.droppedPackets() == 1, "queue overflow was not counted");
}

void testSecondStartAndStaleEndKeepTheOriginalStream()
{
    AudioOutputBuffer buffer;
    expect(buffer.start(validStream()) == AudioOutputError::None, "valid stream start failed");

    auto second = validStream();
    second.streamId = "82e18a2c-f267-48d7-8465-aeb7e9b73533";
    expect(
        buffer.start(second) == AudioOutputError::InvalidState,
        "second stream start was accepted"
    );
    expect(buffer.streamId() == kStreamId, "second start replaced the original stream");
    expect(
        buffer.finish(
            kTurnId,
            "82e18a2c-f267-48d7-8465-aeb7e9b73533",
            AudioOutputEndReason::Completed
        ) == AudioOutputError::WrongStream,
        "stale end closed the current stream"
    );
    expect(buffer.isOpen(), "stale end changed stream state");
}

void testPrerollWaitsForFiveHundredMillisecondsOrEnd()
{
    AudioOutputBuffer buffer;
    expect(buffer.start(validStream()) == AudioOutputError::None, "valid stream start failed");
    const std::uint8_t packet[] = {9};
    for (int index = 0; index < 8; ++index) {
        expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "packet failed");
    }
    expect(!buffer.readyForPlayback(), "preroll became ready before 500 ms");
    expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "ninth packet failed");
    expect(buffer.readyForPlayback(), "preroll did not become ready after 540 ms");
    std::vector<std::uint8_t> output;
    expect(buffer.pop(output), "first preroll packet was not available");
    expect(buffer.pop(output), "playback stopped after dropping below the preroll threshold");

    AudioOutputBuffer shortBuffer;
    expect(shortBuffer.start(validStream()) == AudioOutputError::None, "short stream start failed");
    expect(shortBuffer.push(packet, sizeof(packet)) == AudioOutputError::None, "short packet failed");
    expect(
        shortBuffer.finish(kTurnId, kStreamId, AudioOutputEndReason::Completed)
            == AudioOutputError::None,
        "short stream end failed"
    );
    expect(shortBuffer.readyForPlayback(), "completed short stream never became playable");
}

void testPrerollMustFitThePacketQueue()
{
    for (const int frameMs : {20, 40, 60}) {
        auto stream = validStream();
        stream.frameMs = frameMs;
        const int capacityMs = static_cast<int>(kAudioOutputQueuePackets) * frameMs;
        for (const int invalidPreroll : {-1, capacityMs + 1, 5'000}) {
            AudioOutputBuffer invalid(invalidPreroll);
            expect(invalid.start(stream) == AudioOutputError::InvalidArgument,
                   "preroll outside the queue capacity was accepted");
            expect(!invalid.isOpen(), "invalid preroll opened a stream");
        }
        AudioOutputBuffer buffer(capacityMs);
        expect(buffer.start(stream) == AudioOutputError::None, "maximum fitting preroll failed");
        const std::uint8_t packet[] = {9};
        for (std::size_t index = 0; index < kAudioOutputQueuePackets; ++index) {
            expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None,
                   "fitting preroll overflowed before playback");
        }
        expect(buffer.readyForPlayback(), "full queue never satisfied fitting preroll");
        std::vector<std::uint8_t> output;
        expect(buffer.pop(output), "full preroll did not permit playback");
        expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None,
               "playback did not release a slot for the next packet");
        expect(buffer.droppedPackets() == 0, "fitting preroll dropped a packet");
    }
}

void testConfiguredPrerollControlsPlaybackReadiness()
{
    AudioOutputBuffer buffer(120);
    expect(buffer.start(validStream()) == AudioOutputError::None, "valid stream start failed");
    const std::uint8_t packet[] = {9};
    expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "first packet failed");
    expect(!buffer.readyForPlayback(), "configured preroll became ready after 60 ms");
    expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "second packet failed");
    expect(buffer.readyForPlayback(), "configured preroll was ignored at 120 ms");
}

void testCancellationDiscardsOwnedPlaybackOnly()
{
    AudioOutputBuffer buffer;
    expect(buffer.start(validStream()) == AudioOutputError::None, "valid stream start failed");
    const std::uint8_t packet[] = {10, 11};
    expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "packet failed");

    expect(
        buffer.cancelTurn("82e18a2c-f267-48d7-8465-aeb7e9b73533")
            == AudioOutputError::WrongStream,
        "stale turn cancelled playback"
    );
    expect(buffer.queuedPackets() == 1, "stale cancellation changed the queue");
    expect(buffer.cancelTurn(kTurnId) == AudioOutputError::None, "owned cancellation failed");
    expect(!buffer.isOpen(), "cancellation retained the open stream");
    expect(buffer.queuedPackets() == 0, "cancellation retained queued audio");
}

void testCompletedDeliveryRemainsCancelableUntilPlaybackIsAcknowledged()
{
    AudioOutputBuffer buffer;
    expect(buffer.start(validStream()) == AudioOutputError::None, "valid stream start failed");
    const std::uint8_t packet[] = {10, 11};
    expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "packet failed");
    expect(
        buffer.finish(kTurnId, kStreamId, AudioOutputEndReason::Completed)
            == AudioOutputError::None,
        "completed stream end failed"
    );
    expect(
        buffer.deliverNext([](const AudioOutputStream&, const auto&) { return true; }),
        "completed packet was not delivered downstream"
    );

    expect(
        buffer.cancelTurn(kTurnId) == AudioOutputError::None,
        "downstream delivery discarded cancellation ownership before physical playback ended"
    );
}

void testPhysicalPlaybackAcknowledgementReleasesCompletedContext()
{
    AudioOutputBuffer buffer;
    expect(buffer.start(validStream()) == AudioOutputError::None, "valid stream start failed");
    const std::uint8_t packet[] = {10, 11};
    expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "packet failed");
    expect(
        buffer.finish(kTurnId, kStreamId, AudioOutputEndReason::Completed)
            == AudioOutputError::None,
        "completed stream end failed"
    );
    expect(
        buffer.deliverNext([](const AudioOutputStream&, const auto&) { return true; }),
        "completed packet was not delivered downstream"
    );
    expect(buffer.deliveryComplete(), "completed delivery was not awaiting physical playback");

    auto next = validStream();
    next.turnId = "168b58ca-7c31-4744-b445-d2f20c9bdde0";
    next.streamId = "82e18a2c-f267-48d7-8465-aeb7e9b73533";
    expect(
        buffer.start(next) == AudioOutputError::InvalidState,
        "new stream replaced playback awaiting physical completion"
    );
    expect(
        buffer.acknowledgePlayback(kTurnId, next.streamId) == AudioOutputError::WrongStream,
        "stale playback acknowledgement cleared the owned context"
    );
    expect(
        buffer.acknowledgePlayback(kTurnId, kStreamId) == AudioOutputError::None,
        "owned physical playback acknowledgement failed"
    );
    expect(buffer.start(next) == AudioOutputError::None, "new stream was not released after playback");
}

void testPlaybackUnderflowIsDetectedWithoutConsumingNoise()
{
    AudioOutputBuffer buffer;
    expect(buffer.start(validStream()) == AudioOutputError::None, "valid stream start failed");
    const std::uint8_t packet[] = {12};
    for (int index = 0; index < 9; ++index) {
        expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "packet failed");
    }
    std::vector<std::uint8_t> output;
    for (int index = 0; index < 9; ++index) {
        expect(buffer.pop(output), "queued packet was not playable");
    }

    expect(!buffer.pop(output), "empty playback produced a packet");
    expect(output.empty(), "underflow returned stale packet bytes");
    expect(buffer.underflowCount() == 1, "playback underflow was not counted");
    expect(!buffer.pop(output), "repeated empty playback produced a packet");
    expect(buffer.underflowCount() == 1, "one underflow was counted repeatedly");
}

void testStrictAudioOutputControlsRetainStreamOwnership()
{
    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";
    AudioOutputControl control;
    expect(
        parseAudioOutputControlJson(start, control) == AudioOutputParseError::None,
        "valid audio output start was rejected"
    );
    expect(control.type == AudioOutputControlType::Start, "wrong start control type");
    expect(control.stream.turnId == kTurnId, "start lost turn ownership");
    expect(control.stream.streamId == kStreamId, "start lost stream ownership");
    expect(control.stream.frameMs == 60, "start lost frame duration");

    const std::string end = R"({
        "v":1,"type":"audio.output.end",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":22,
        "payload":{"reason":"completed"}
    })";
    expect(
        parseAudioOutputControlJson(end, control) == AudioOutputParseError::None,
        "valid audio output end was rejected"
    );
    expect(control.type == AudioOutputControlType::End, "wrong end control type");
    expect(control.reason == AudioOutputEndReason::Completed, "end reason was changed");
}

void testAudioOutputControlIgnoresUnknownCompatibilityFields()
{
    const std::string start = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":21,
        "future_envelope":true,
        "payload":{"codec":"opus","sample_rate":16000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000,"future_payload":"ignored"}
    })";
    AudioOutputControl control;

    expect(
        parseAudioOutputControlJson(start, control) == AudioOutputParseError::None,
        "unknown compatibility fields were rejected"
    );
    expect(control.stream.streamId == kStreamId, "compatibility fields changed ownership");
}

void testInvalidAudioOutputControlIsRejectedAtomically()
{
    AudioOutputControl control;
    control.type = AudioOutputControlType::End;
    const std::string invalid = R"({
        "v":1,"type":"audio.output.start",
        "message_id":"519a16ce-3a07-4ab6-9767-f39bcc096cb8",
        "turn_id":"c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
        "stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874","sent_at_ms":23,
        "payload":{"codec":"opus","sample_rate":48000,"channels":1,
            "frame_ms":60,"expected_duration_ms":2000}
    })";

    expect(
        parseAudioOutputControlJson(invalid, control)
            == AudioOutputParseError::InvalidArgument,
        "invalid audio format was accepted"
    );
    expect(control.type == AudioOutputControlType::End, "failed parse partially changed output");
}

void testDownstreamBackpressureRetainsTheFrontPacket()
{
    AudioOutputBuffer buffer;
    expect(buffer.start(validStream()) == AudioOutputError::None, "valid stream start failed");
    const std::uint8_t packet[] = {13, 14};
    for (int index = 0; index < 9; ++index) {
        expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "packet failed");
    }

    expect(
        !buffer.deliverNext([](const AudioOutputStream&, const std::vector<std::uint8_t>&) {
            return false;
        }),
        "downstream rejection was reported as delivery"
    );
    expect(buffer.queuedPackets() == 9, "backpressure discarded the front packet");

    std::vector<std::uint8_t> delivered;
    expect(
        buffer.deliverNext([&](const AudioOutputStream& stream, const auto& bytes) {
            expect(stream.frameMs == 60, "delivery lost frame duration");
            delivered = bytes;
            return true;
        }),
        "available downstream did not receive a packet"
    );
    expect(delivered == std::vector<std::uint8_t>({13, 14}), "delivered bytes changed");
    expect(buffer.queuedPackets() == 8, "successful delivery retained the front packet");
}

void testDeliveryPathDetectsOneUnderflowEpisode()
{
    AudioOutputBuffer buffer;
    expect(buffer.start(validStream()) == AudioOutputError::None, "valid stream start failed");
    const std::uint8_t packet[] = {15};
    for (int index = 0; index < 9; ++index) {
        expect(buffer.push(packet, sizeof(packet)) == AudioOutputError::None, "packet failed");
    }
    for (int index = 0; index < 9; ++index) {
        expect(
            buffer.deliverNext([](const AudioOutputStream&, const auto&) { return true; }),
            "delivery path lost a packet"
        );
    }
    expect(
        !buffer.deliverNext([](const AudioOutputStream&, const auto&) { return true; }),
        "empty delivery path produced a packet"
    );
    expect(buffer.underflowCount() == 1, "delivery path did not count underflow");
    expect(
        !buffer.deliverNext([](const AudioOutputStream&, const auto&) { return true; }),
        "repeated empty delivery produced a packet"
    );
    expect(buffer.underflowCount() == 1, "one delivery underflow was counted repeatedly");
}

void testAudioBufferEventsAreOwnedAndBounded()
{
    EnvelopeMetadata envelope;
    envelope.messageId = "519a16ce-3a07-4ab6-9767-f39bcc096cb8";
    envelope.sentAtMs = 30;
    std::string output;

    expect(
        buildAudioBufferEventJson(
            envelope,
            "stackchan-001",
            kStreamId,
            AudioBufferEventType::Underrun,
            1,
            output
        ) == AudioBufferEventBuildError::None,
        "audio underrun event was not built"
    );
    expect(output.find(R"("name":"audio.underrun")") != std::string::npos,
           "wrong underrun event name");
    expect(output.find(R"("stream_id":"a9d1c15a-f728-4293-87fc-1d3cae5f1874")")
               != std::string::npos,
           "underrun lost stream ownership");
    expect(output.find(R"("dropped_packets":1)") != std::string::npos,
           "underrun lost its count");

    expect(
        buildAudioBufferEventJson(
            envelope,
            "stackchan-001",
            kStreamId,
            AudioBufferEventType::Overflow,
            65'535,
            output
        ) == AudioBufferEventBuildError::None,
        "audio overflow event was not built"
    );
    expect(output.find(R"("name":"audio.overflow")") != std::string::npos,
           "wrong overflow event name");
    expect(
        buildAudioBufferEventJson(
            envelope,
            "stackchan-001",
            kStreamId,
            AudioBufferEventType::Overflow,
            0,
            output
        ) == AudioBufferEventBuildError::InvalidArgument,
        "zero-drop audio event was accepted"
    );
    expect(output.empty(), "failed audio event build retained stale JSON");
}

}  // namespace

int main()
{
    testBinaryOutsideAnOpenStreamIsDropped();
    testOpenStreamQueuesOnlyBoundedPackets();
    testOutputOverflowRejectsTheNewPacket();
    testSecondStartAndStaleEndKeepTheOriginalStream();
    testPrerollWaitsForFiveHundredMillisecondsOrEnd();
    testPrerollMustFitThePacketQueue();
    testConfiguredPrerollControlsPlaybackReadiness();
    testCancellationDiscardsOwnedPlaybackOnly();
    testCompletedDeliveryRemainsCancelableUntilPlaybackIsAcknowledged();
    testPhysicalPlaybackAcknowledgementReleasesCompletedContext();
    testPlaybackUnderflowIsDetectedWithoutConsumingNoise();
    testStrictAudioOutputControlsRetainStreamOwnership();
    testAudioOutputControlIgnoresUnknownCompatibilityFields();
    testInvalidAudioOutputControlIsRejectedAtomically();
    testDownstreamBackpressureRetainsTheFrontPacket();
    testDeliveryPathDetectsOneUnderflowEpisode();
    testAudioBufferEventsAreOwnedAndBounded();
    return 0;
}
