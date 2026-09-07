#include <array>
#include <cstdlib>
#include <iostream>
#include <string>

#include <stackchan_bridge_client/message_id.h>

namespace {

using stackchan::bridge_client::formatUuidV4;

void expect(bool condition, const char* label)
{
    if (!condition) {
        std::cerr << label << '\n';
        std::exit(1);
    }
}

void testRandomBytesAreFormattedAsAnRfc4122VersionFourUuid()
{
    std::array<std::uint8_t, 16> bytes = {
        0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef,
        0xff, 0xee, 0xdd, 0xcc, 0xbb, 0xaa, 0x99, 0x88,
    };

    const std::string value = formatUuidV4(bytes);

    expect(value == "01234567-89ab-4def-bfee-ddccbbaa9988", "UUID v4 formatting changed");
    expect(value.size() == 36, "UUID length changed");
}

void testVersionAndVariantBitsDoNotDependOnRandomInput()
{
    std::array<std::uint8_t, 16> bytes{};
    expect(
        formatUuidV4(bytes) == "00000000-0000-4000-8000-000000000000",
        "UUID version or variant bits were not forced"
    );
}

}  // namespace

int main()
{
    testRandomBytesAreFormattedAsAnRfc4122VersionFourUuid();
    testVersionAndVariantBitsDoNotDependOnRandomInput();
    return 0;
}
