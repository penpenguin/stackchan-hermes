#pragma once

#include <array>
#include <cstdint>
#include <string>

namespace stackchan::bridge_client {

std::string formatUuidV4(std::array<std::uint8_t, 16> bytes);

}  // namespace stackchan::bridge_client
