#include <stackchan_bridge_client/reconnect.h>

namespace stackchan::bridge_client {

std::uint32_t ReconnectBackoff::nextDelaySeconds()
{
    const std::uint32_t delay = nextDelaySeconds_;
    nextDelaySeconds_ = nextDelaySeconds_ >= 16 ? 30 : nextDelaySeconds_ * 2;
    return delay;
}

void ReconnectBackoff::observeStableConnection(std::uint32_t durationSeconds)
{
    if (durationSeconds >= 30) {
        nextDelaySeconds_ = 1;
    }
}

}  // namespace stackchan::bridge_client
