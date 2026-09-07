#include <cstdlib>
#include <iostream>

#include <stackchan_bridge_client/reconnect.h>

namespace {

using stackchan::bridge_client::ReconnectBackoff;

void expectEqual(unsigned int actual, unsigned int expected, const char* label)
{
    if (actual != expected) {
        std::cerr << label << ": expected " << expected << ", got " << actual << '\n';
        std::exit(1);
    }
}

void testFirstRetryWaitsOneSecond()
{
    ReconnectBackoff backoff;
    expectEqual(backoff.nextDelaySeconds(), 1, "first retry");
    expectEqual(backoff.nextDelaySeconds(), 2, "second retry");
    expectEqual(backoff.nextDelaySeconds(), 4, "third retry");
    expectEqual(backoff.nextDelaySeconds(), 8, "fourth retry");
    expectEqual(backoff.nextDelaySeconds(), 16, "fifth retry");
    expectEqual(backoff.nextDelaySeconds(), 30, "sixth retry");
    expectEqual(backoff.nextDelaySeconds(), 30, "capped retry");
}

void testStableConnectionResetsBackoffAfterThirtySeconds()
{
    ReconnectBackoff backoff;
    expectEqual(backoff.nextDelaySeconds(), 1, "initial retry");
    expectEqual(backoff.nextDelaySeconds(), 2, "advanced retry");

    backoff.observeStableConnection(29);
    expectEqual(backoff.nextDelaySeconds(), 4, "premature stable reset");

    backoff.observeStableConnection(30);
    expectEqual(backoff.nextDelaySeconds(), 1, "stable reset");
}

}  // namespace

int main()
{
    testFirstRetryWaitsOneSecond();
    testStableConnectionResetsBackoffAfterThirtySeconds();
    return 0;
}
