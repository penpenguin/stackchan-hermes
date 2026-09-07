#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

#include <stackchan_bridge_client/audio_safety.h>

namespace {

using stackchan::bridge_client::ConsecutiveFailureGate;
using stackchan::bridge_client::applyPcmGain;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testThreeConsecutiveFailuresTripOnceUntilReset()
{
    ConsecutiveFailureGate gate(3);
    expect(!gate.observeFailure(), "first decoder failure tripped the gate");
    expect(!gate.observeFailure(), "second decoder failure tripped the gate");
    expect(gate.observeFailure(), "third decoder failure did not trip the gate");
    expect(!gate.observeFailure(), "latched decoder failure tripped repeatedly");
    gate.reset();
    expect(!gate.observeFailure(), "reset decoder gate retained failures");
    gate.observeFailure();
    gate.observeSuccess();
    expect(!gate.observeFailure(), "decoder success did not clear consecutive failures");
}

void testPcmGainIsBoundedAndDoesNotWrap()
{
    std::vector<std::int16_t> samples = {10'000, -10'000, 32'767, -32'768};
    expect(applyPcmGain(samples, 65), "valid PCM gain was rejected");
    expect(samples[0] == 6'500 && samples[1] == -6'500, "PCM gain changed amplitude");
    expect(samples[2] == 21'298 && samples[3] == -21'299, "PCM gain wrapped extremes");

    const auto retained = samples;
    expect(!applyPcmGain(samples, 101), "out-of-range PCM gain was accepted");
    expect(samples == retained, "invalid PCM gain partially changed samples");
}

}  // namespace

int main()
{
    testThreeConsecutiveFailuresTripOnceUntilReset();
    testPcmGainIsBoundedAndDoesNotWrap();
    return 0;
}
