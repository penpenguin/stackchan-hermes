#include <stackchan_bridge_client/message_id.h>

#include <cstdio>

namespace stackchan::bridge_client {

std::string formatUuidV4(std::array<std::uint8_t, 16> bytes)
{
    bytes[6] = static_cast<std::uint8_t>((bytes[6] & 0x0F) | 0x40);
    bytes[8] = static_cast<std::uint8_t>((bytes[8] & 0x3F) | 0x80);

    char output[37] = {};
    std::snprintf(
        output,
        sizeof(output),
        "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
        bytes[0],
        bytes[1],
        bytes[2],
        bytes[3],
        bytes[4],
        bytes[5],
        bytes[6],
        bytes[7],
        bytes[8],
        bytes[9],
        bytes[10],
        bytes[11],
        bytes[12],
        bytes[13],
        bytes[14],
        bytes[15]
    );
    return output;
}

}  // namespace stackchan::bridge_client
