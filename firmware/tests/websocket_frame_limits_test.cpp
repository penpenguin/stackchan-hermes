#include <cstdlib>
#include <cstdint>
#include <iostream>

#include <stackchan_bridge_client/websocket_frame_limits.h>

namespace {

using stackchan::bridge_client::WebSocketFrameHeaderStatus;
using stackchan::bridge_client::inspectWebSocketFrameHeader;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testOversizedFrameIsRejectedFromItsHeader()
{
    const std::uint8_t header[] = {
        0x82,
        0x7E,
        0x40,
        0x01,
    };

    const auto result = inspectWebSocketFrameHeader(header, sizeof(header), 16'384);

    expect(
        result.status == WebSocketFrameHeaderStatus::MessageTooLarge,
        "oversized frame header was accepted"
    );
    expect(result.payloadBytes == 16'385, "payload length was not decoded safely");
}

void testExactLimitAndFragmentRemainderAreEnforced()
{
    const std::uint8_t exactLimit[] = {0x82, 0x7E, 0x40, 0x00};
    const auto accepted = inspectWebSocketFrameHeader(
        exactLimit,
        sizeof(exactLimit),
        16'384
    );
    expect(
        accepted.status == WebSocketFrameHeaderStatus::Complete,
        "frame at the exact limit was rejected"
    );
    expect(accepted.headerBytes == 4, "extended frame header length was wrong");

    const std::uint8_t continuation[] = {0x80, 0x7E, 0x20, 0x01};
    const auto tooLarge = inspectWebSocketFrameHeader(
        continuation,
        sizeof(continuation),
        8'192
    );
    expect(
        tooLarge.status == WebSocketFrameHeaderStatus::MessageTooLarge,
        "fragment exceeding the remaining message budget was accepted"
    );

    const std::uint8_t emptyFinalContinuation[] = {0x80, 0x00};
    const auto completedAtLimit = inspectWebSocketFrameHeader(
        emptyFinalContinuation,
        sizeof(emptyFinalContinuation),
        0
    );
    expect(
        completedAtLimit.status == WebSocketFrameHeaderStatus::Complete,
        "empty final continuation at the exact message limit was rejected"
    );
}

}  // namespace

int main()
{
    testOversizedFrameIsRejectedFromItsHeader();
    testExactLimitAndFragmentRemainderAreEnforced();
    return 0;
}
