#pragma once

#include <cstdint>

namespace stackchan::bridge_client {

class ReconnectBackoff {
public:
    std::uint32_t nextDelaySeconds();
    void observeStableConnection(std::uint32_t durationSeconds);

private:
    std::uint32_t nextDelaySeconds_ = 1;
};

}  // namespace stackchan::bridge_client
