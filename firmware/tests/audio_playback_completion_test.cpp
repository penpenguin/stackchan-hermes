#include <cstdlib>
#include <iostream>

#include <stackchan_bridge_client/audio_playback_completion.h>

namespace {

using stackchan::bridge_client::AudioPlaybackCompletion;

void expect(bool condition, const char* message)
{
    if (!condition) {
        std::cerr << message << '\n';
        std::exit(1);
    }
}

void testInFlightOutputBlocksPhysicalPlaybackCompletion()
{
    AudioPlaybackCompletion completion;

    expect(completion.isIdle(true, true), "empty playback did not start idle");
    completion.beginOutput();
    expect(
        !completion.isIdle(true, true),
        "empty queues hid an in-flight physical output frame"
    );
    completion.finishOutput();
    expect(completion.isIdle(true, true), "finished physical output did not become idle");
}

void testQueuedWorkBlocksPhysicalPlaybackCompletion()
{
    AudioPlaybackCompletion completion;

    expect(!completion.isIdle(false, true), "decode queue was ignored");
    expect(!completion.isIdle(true, false), "playback queue was ignored");
}

void testInFlightDecodeBlocksPhysicalPlaybackCompletion()
{
    AudioPlaybackCompletion completion;

    const auto generation = completion.beginDecode();
    expect(
        !completion.isIdle(true, true),
        "empty queues hid an in-flight decode frame"
    );
    expect(completion.finishDecode(generation), "current decode frame was rejected");
    expect(completion.isIdle(true, true), "finished decode did not become idle");
}

void testInvalidatedDecodeCannotReturnStalePlayback()
{
    AudioPlaybackCompletion completion;

    const auto staleGeneration = completion.beginDecode();
    completion.invalidateDecode();
    expect(
        !completion.finishDecode(staleGeneration),
        "cancelled decode frame remained eligible for playback"
    );
    expect(completion.isIdle(true, true), "discarded stale decode did not become idle");

    const auto currentGeneration = completion.beginDecode();
    expect(
        currentGeneration != staleGeneration,
        "new playback reused a cancelled decode generation"
    );
    expect(completion.finishDecode(currentGeneration), "new decode frame was rejected");
}

}  // namespace

int main()
{
    testInFlightOutputBlocksPhysicalPlaybackCompletion();
    testQueuedWorkBlocksPhysicalPlaybackCompletion();
    testInFlightDecodeBlocksPhysicalPlaybackCompletion();
    testInvalidatedDecodeCannotReturnStalePlayback();
    return 0;
}
