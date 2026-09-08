#pragma once
#include <algorithm>
#include <cstdint>
namespace stackchan::bridge_client {
template<class Clock, class Cancelled, class Receive>
bool waitCameraFrame(std::uint64_t deadline, Clock clock, Cancelled cancelled, Receive receive)
{
    while (!cancelled()) {
        const auto now = clock();
        if (now >= deadline) { return false; }
        if (receive(static_cast<unsigned>(std::min<std::uint64_t>(20, deadline - now)))) { return true; }
    }
    return false;
}
}
