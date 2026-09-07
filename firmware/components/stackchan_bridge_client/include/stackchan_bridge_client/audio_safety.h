#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace stackchan::bridge_client {

class ConsecutiveFailureGate {
public:
    explicit ConsecutiveFailureGate(std::size_t threshold);

    bool observeFailure();
    void observeSuccess();
    void reset();

private:
    std::size_t threshold_ = 1;
    std::size_t failures_ = 0;
    bool latched_ = false;
};

bool applyPcmGain(std::vector<std::int16_t>& samples, int gainPercent);

}  // namespace stackchan::bridge_client
