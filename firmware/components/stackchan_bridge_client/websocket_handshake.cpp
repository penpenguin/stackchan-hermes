#include <stackchan_bridge_client/websocket_handshake.h>

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace stackchan::bridge_client {
namespace {

constexpr std::string_view kWebSocketGuid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

std::uint32_t rotateLeft(std::uint32_t value, unsigned int bits)
{
    return (value << bits) | (value >> (32U - bits));
}

std::array<std::uint8_t, 20> sha1(std::string_view input)
{
    const std::uint64_t inputBits = static_cast<std::uint64_t>(input.size()) * 8U;
    std::vector<std::uint8_t> message(input.begin(), input.end());
    message.push_back(0x80U);
    while (message.size() % 64U != 56U) {
        message.push_back(0U);
    }
    for (int shift = 56; shift >= 0; shift -= 8) {
        message.push_back(static_cast<std::uint8_t>((inputBits >> shift) & 0xFFU));
    }

    std::uint32_t h0 = 0x67452301U;
    std::uint32_t h1 = 0xEFCDAB89U;
    std::uint32_t h2 = 0x98BADCFEU;
    std::uint32_t h3 = 0x10325476U;
    std::uint32_t h4 = 0xC3D2E1F0U;
    for (std::size_t chunk = 0; chunk < message.size(); chunk += 64U) {
        std::array<std::uint32_t, 80> words{};
        for (std::size_t index = 0; index < 16; ++index) {
            const std::size_t offset = chunk + index * 4U;
            words[index] = (static_cast<std::uint32_t>(message[offset]) << 24U)
                | (static_cast<std::uint32_t>(message[offset + 1U]) << 16U)
                | (static_cast<std::uint32_t>(message[offset + 2U]) << 8U)
                | static_cast<std::uint32_t>(message[offset + 3U]);
        }
        for (std::size_t index = 16; index < words.size(); ++index) {
            words[index] = rotateLeft(
                words[index - 3U] ^ words[index - 8U] ^ words[index - 14U]
                    ^ words[index - 16U],
                1U
            );
        }

        std::uint32_t a = h0;
        std::uint32_t b = h1;
        std::uint32_t c = h2;
        std::uint32_t d = h3;
        std::uint32_t e = h4;
        for (std::size_t index = 0; index < words.size(); ++index) {
            std::uint32_t function = 0;
            std::uint32_t constant = 0;
            if (index < 20U) {
                function = (b & c) | ((~b) & d);
                constant = 0x5A827999U;
            } else if (index < 40U) {
                function = b ^ c ^ d;
                constant = 0x6ED9EBA1U;
            } else if (index < 60U) {
                function = (b & c) | (b & d) | (c & d);
                constant = 0x8F1BBCDCU;
            } else {
                function = b ^ c ^ d;
                constant = 0xCA62C1D6U;
            }
            const std::uint32_t next = rotateLeft(a, 5U) + function + e + constant
                + words[index];
            e = d;
            d = c;
            c = rotateLeft(b, 30U);
            b = a;
            a = next;
        }
        h0 += a;
        h1 += b;
        h2 += c;
        h3 += d;
        h4 += e;
    }

    const std::array<std::uint32_t, 5> words{h0, h1, h2, h3, h4};
    std::array<std::uint8_t, 20> digest{};
    for (std::size_t index = 0; index < words.size(); ++index) {
        for (std::size_t byte = 0; byte < 4; ++byte) {
            digest[index * 4U + byte] = static_cast<std::uint8_t>(
                (words[index] >> (24U - static_cast<unsigned int>(byte * 8U)))
                & 0xFFU
            );
        }
    }
    return digest;
}

std::string base64Encode(const std::uint8_t* data, std::size_t size)
{
    constexpr char alphabet[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string output;
    output.reserve((size + 2U) / 3U * 4U);
    for (std::size_t offset = 0; offset < size; offset += 3U) {
        const std::uint32_t first = data[offset];
        const std::uint32_t second = offset + 1U < size ? data[offset + 1U] : 0U;
        const std::uint32_t third = offset + 2U < size ? data[offset + 2U] : 0U;
        const std::uint32_t group = (first << 16U) | (second << 8U) | third;
        output.push_back(alphabet[(group >> 18U) & 0x3FU]);
        output.push_back(alphabet[(group >> 12U) & 0x3FU]);
        output.push_back(offset + 1U < size ? alphabet[(group >> 6U) & 0x3FU] : '=');
        output.push_back(offset + 2U < size ? alphabet[group & 0x3FU] : '=');
    }
    return output;
}

char lowerAscii(char value)
{
    return value >= 'A' && value <= 'Z' ? static_cast<char>(value + ('a' - 'A')) : value;
}

bool equalsIgnoreCase(std::string_view left, std::string_view right)
{
    if (left.size() != right.size()) {
        return false;
    }
    for (std::size_t index = 0; index < left.size(); ++index) {
        if (lowerAscii(left[index]) != lowerAscii(right[index])) {
            return false;
        }
    }
    return true;
}

std::string_view trimHttpWhitespace(std::string_view value)
{
    while (!value.empty() && (value.front() == ' ' || value.front() == '\t')) {
        value.remove_prefix(1U);
    }
    while (!value.empty() && (value.back() == ' ' || value.back() == '\t')) {
        value.remove_suffix(1U);
    }
    return value;
}

bool containsHeaderToken(std::string_view value, std::string_view expected)
{
    while (true) {
        const std::size_t separator = value.find(',');
        const std::string_view token = trimHttpWhitespace(value.substr(0, separator));
        if (equalsIgnoreCase(token, expected)) {
            return true;
        }
        if (separator == std::string_view::npos) {
            return false;
        }
        value.remove_prefix(separator + 1U);
    }
}

std::string expectedAccept(std::string_view clientKey)
{
    std::string source(clientKey);
    source.append(kWebSocketGuid);
    const auto digest = sha1(source);
    return base64Encode(digest.data(), digest.size());
}

}  // namespace

bool validateWebSocketHandshakeResponse(
    std::string_view response,
    std::string_view clientKey
)
{
    if (clientKey.empty()) {
        return false;
    }
    const std::size_t headerEnd = response.find("\r\n\r\n");
    const std::size_t statusEnd = response.find("\r\n");
    if (headerEnd == std::string_view::npos || statusEnd == std::string_view::npos
        || statusEnd >= headerEnd) {
        return false;
    }
    const std::string_view status = response.substr(0, statusEnd);
    if (status.size() < 13U || status.substr(0, 9U) != "HTTP/1.1 "
        || status.substr(9U, 3U) != "101" || status[12U] != ' ') {
        return false;
    }

    bool upgrade = false;
    bool connectionUpgrade = false;
    bool acceptSeen = false;
    bool acceptMatches = false;
    const std::string accept = expectedAccept(clientKey);
    std::size_t offset = statusEnd + 2U;
    while (offset < headerEnd) {
        const std::size_t lineEnd = response.find("\r\n", offset);
        if (lineEnd == std::string_view::npos || lineEnd > headerEnd) {
            return false;
        }
        const std::string_view line = response.substr(offset, lineEnd - offset);
        if (line.empty() || line.front() == ' ' || line.front() == '\t') {
            return false;
        }
        const std::size_t colon = line.find(':');
        if (colon == std::string_view::npos || colon == 0U) {
            return false;
        }
        const std::string_view name = line.substr(0, colon);
        if (trimHttpWhitespace(name) != name) {
            return false;
        }
        const std::string_view value = trimHttpWhitespace(line.substr(colon + 1U));
        if (equalsIgnoreCase(name, "Upgrade")) {
            upgrade = upgrade || containsHeaderToken(value, "websocket");
        } else if (equalsIgnoreCase(name, "Connection")) {
            connectionUpgrade = connectionUpgrade || containsHeaderToken(value, "Upgrade");
        } else if (equalsIgnoreCase(name, "Sec-WebSocket-Accept")) {
            if (acceptSeen) {
                return false;
            }
            acceptSeen = true;
            acceptMatches = value == accept;
        }
        offset = lineEnd + 2U;
    }
    return upgrade && connectionUpgrade && acceptSeen && acceptMatches;
}

}  // namespace stackchan::bridge_client
