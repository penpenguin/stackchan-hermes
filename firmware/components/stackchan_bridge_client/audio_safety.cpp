#include <stackchan_bridge_client/audio_safety.h>

#include <cstdint>

namespace stackchan::bridge_client {

ConsecutiveFailureGate::ConsecutiveFailureGate(std::size_t threshold)
    : threshold_(threshold == 0 ? 1 : threshold)
{
}

bool ConsecutiveFailureGate::observeFailure()
{
    if (latched_) {
        return false;
    }
    ++failures_;
    if (failures_ < threshold_) {
        return false;
    }
    latched_ = true;
    return true;
}

void ConsecutiveFailureGate::observeSuccess()
{
    reset();
}

void ConsecutiveFailureGate::reset()
{
    failures_ = 0;
    latched_ = false;
}

bool applyPcmGain(std::vector<std::int16_t>& samples, int gainPercent)
{
    if (gainPercent < 0 || gainPercent > 100) {
        return false;
    }
    for (std::int16_t& sample : samples) {
        sample = static_cast<std::int16_t>(
            static_cast<std::int32_t>(sample) * gainPercent / 100
        );
    }
    return true;
}

}  // namespace stackchan::bridge_client
