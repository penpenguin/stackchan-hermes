#include <cstdlib>
#include <iostream>
#include <string>

#include <stackchan_bridge_client/websocket_handshake.h>

namespace {

using stackchan::bridge_client::validateWebSocketHandshakeResponse;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testRfcHandshakeBindsTheAcceptHeaderToTheClientKey()
{
    const std::string response =
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: keep-alive, Upgrade\r\n"
        "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"
        "\r\n";

    expect(
        validateWebSocketHandshakeResponse(
            response,
            "dGhlIHNhbXBsZSBub25jZQ=="
        ),
        "RFC WebSocket handshake was rejected"
    );
    expect(
        !validateWebSocketHandshakeResponse(response, "AAAAAAAAAAAAAAAAAAAAAA=="),
        "handshake accepted a response for a different client key"
    );
}

void testHandshakeRequiresARealStatusLineAndUpgradeHeaders()
{
    const std::string headers =
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"
        "\r\n";
    const std::string accept =
        "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n\r\n";
    expect(
        !validateWebSocketHandshakeResponse(
            "HTTP/1.1 101\r\n" + headers,
            "dGhlIHNhbXBsZSBub25jZQ=="
        ),
        "incomplete status line was accepted"
    );
    expect(
        !validateWebSocketHandshakeResponse(
            "HTTP/1.1 200 OK\r\nX-Fake: HTTP/1.1 101\r\n"
                "Upgrade: websocket\r\nConnection: Upgrade\r\n" + accept,
            "dGhlIHNhbXBsZSBub25jZQ=="
        ),
        "embedded 101 text was accepted as a status line"
    );
    expect(
        !validateWebSocketHandshakeResponse(
            "HTTP/1.1 101 Switching Protocols\r\n"
                "Connection: Upgrade\r\n" + accept,
            "dGhlIHNhbXBsZSBub25jZQ=="
        ),
        "handshake without Upgrade header was accepted"
    );
    expect(
        !validateWebSocketHandshakeResponse(
            "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n" + accept,
            "dGhlIHNhbXBsZSBub25jZQ=="
        ),
        "handshake without Connection upgrade token was accepted"
    );
}

}  // namespace

int main()
{
    testRfcHandshakeBindsTheAcceptHeaderToTheClientKey();
    testHandshakeRequiresARealStatusLineAndUpgradeHeaders();
    return 0;
}
