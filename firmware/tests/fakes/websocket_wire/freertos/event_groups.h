#pragma once

#include <cstdint>

using EventBits_t = std::uint32_t;
using EventGroupHandle_t = EventBits_t*;

namespace websocket_test {
inline EventBits_t lastWaitBits = 0;
}

inline EventGroupHandle_t xEventGroupCreate() { return new EventBits_t(0); }
inline void vEventGroupDelete(EventGroupHandle_t group) { delete group; }
inline EventBits_t xEventGroupSetBits(EventGroupHandle_t group, EventBits_t bits)
{
    return *group |= bits;
}
inline EventBits_t xEventGroupClearBits(EventGroupHandle_t group, EventBits_t bits)
{
    const EventBits_t previous = *group;
    *group &= ~bits;
    return previous;
}
inline EventBits_t xEventGroupWaitBits(
    EventGroupHandle_t group, EventBits_t, bool, bool, std::uint32_t
)
{
    websocket_test::lastWaitBits = *group;
    return *group;
}
