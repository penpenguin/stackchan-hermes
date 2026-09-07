#pragma once

#include <string_view>

namespace stackchan::bridge_client {

bool validateWebSocketHandshakeResponse(
    std::string_view response,
    std::string_view clientKey
);

}  // namespace stackchan::bridge_client
