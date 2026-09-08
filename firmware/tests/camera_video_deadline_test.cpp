#include <cassert>
#include <stackchan_bridge_client/camera_video_wait.h>
int main()
{
    unsigned long long now = 0;
    int attempts = 0;
    bool cancelled = false;
    auto frame = [&](unsigned wait) { assert(wait <= 20); ++attempts; now += wait; return false; };
    assert(!stackchan::bridge_client::waitCameraFrame(55, [&] { return now; }, [&] { return cancelled; }, frame));
    assert(now == 55 && attempts == 3);
    now = 0; cancelled = true; attempts = 0;
    assert(!stackchan::bridge_client::waitCameraFrame(55, [&] { return now; }, [&] { return cancelled; }, frame));
    assert(attempts == 0);
    cancelled = false;
    assert(stackchan::bridge_client::waitCameraFrame(55, [&] { return now; }, [&] { return cancelled; }, [&](unsigned) { return true; }));
}
