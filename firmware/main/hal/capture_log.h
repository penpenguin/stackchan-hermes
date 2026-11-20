#pragma once

#include <algorithm>
#include <cstdint>

namespace stackchan::hermes {

// newlib nano accepts a 32-bit unsigned argument for %u.
inline unsigned captureLogElapsedMs(std::uint64_t nowMs, std::uint64_t startedMs)
{
    return static_cast<unsigned>(std::min<std::uint64_t>(nowMs - startedMs, UINT32_MAX));
}

} // namespace stackchan::hermes
