#include "head_touch_fakes.h"
#include "drivers/Si12T/Si12T.h"

#include <cstdlib>
#include <initializer_list>
#include <iostream>
#include <utility>
#include <vector>

namespace {
enum class Sample { Idle, Low, Timeout };
struct EndOfSamples {};
std::vector<Sample> samples;
std::size_t reads = 0;
std::size_t pollsCompleted = 0;
using Event = std::pair<std::size_t, HeadPetGesture>;
std::vector<Event> events;

void require(bool ok, const char* message)
{
    if (!ok) {
        std::cerr << message << " (read " << reads << ")\n";
        std::exit(1);
    }
}

struct SampleRun {
    Sample sample;
    unsigned count;
    HeadPetGesture expectedOnLastRead = HeadPetGesture::None;
};

void expectEvents(const char* scenario, std::initializer_list<SampleRun> runs)
{
    samples.clear();
    events.clear();
    reads = 0;
    pollsCompleted = 0;
    std::vector<Event> expected;
    for (const auto& run : runs) {
        samples.insert(samples.end(), run.count, run.sample);
        if (run.expectedOnLastRead != HeadPetGesture::None) {
            expected.emplace_back(samples.size(), run.expectedOnLastRead);
        }
    }
    GetHAL().head_touch_init();
    require(pollsCompleted == samples.size(), "incomplete polling sequence");
    require(events == expected, scenario);
}
}  // namespace

esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t, const uint8_t* reg, size_t,
                                      uint8_t* result, size_t, int)
{
    if (*reg != SI12T_OUTPUT1_ADDR) {
        *result = 0;  // Configuration register readback during initialization.
        return ESP_OK;
    }
    require(reads == pollsCompleted && reads < samples.size(), "unexpected poll before delay");
    const Sample sample = samples[reads++];
    if (sample == Sample::Timeout) {
        return ESP_ERR_TIMEOUT;  // Leave the caller's output byte untouched.
    }
    *result = sample == Sample::Low ? SI12T_OUTPUT_LOW : SI12T_OUTPUT_NONE;
    return ESP_OK;
}

void GestureSignal::emit(HeadPetGesture gesture)
{
    events.emplace_back(reads, gesture);
}

void vTaskDelay(unsigned ticks)
{
    if (reads == 0 && ticks == pdMS_TO_TICKS(200)) {
        return;  // Startup delay.
    }
    require(ticks == pdMS_TO_TICKS(50), "unexpected poll delay");
    require(reads == pollsCompleted + 1, "expected one sensor read per poll");
    ++pollsCompleted;
    if (pollsCompleted == samples.size()) {
        throw EndOfSamples{};
    }
}

void xTaskCreatePinnedToCoreWithCaps(void (*task)(void*), const char*, unsigned, void* arg,
                                     unsigned, void*, int, unsigned)
{
    try {
        task(arg);
    } catch (EndOfSamples&) {
        si12t_delete(static_cast<si12t_handle_t>(arg));
    }
}

int main()
{
    expectEvents("timeouts after one LOW emitted a gesture", {
        {Sample::Idle, 3}, {Sample::Low, 1}, {Sample::Timeout, 5}
    });
    expectEvents("timeouts released or rearmed a held press", {
        {Sample::Idle, 3}, {Sample::Low, 6, HeadPetGesture::Press},
        {Sample::Idle, 1}, {Sample::Timeout, 5}, {Sample::Low, 6}
    });
    expectEvents("press qualification crossed a failed read or failed to recover", {
        {Sample::Idle, 3}, {Sample::Low, 5}, {Sample::Timeout, 1}, {Sample::Low, 6, HeadPetGesture::Press},
        {Sample::Idle, 3, HeadPetGesture::Release}, {Sample::Idle, 3}, {Sample::Low, 6, HeadPetGesture::Press}
    });
    expectEvents("release qualification crossed a failed read", {
        {Sample::Idle, 3}, {Sample::Low, 6, HeadPetGesture::Press},
        {Sample::Idle, 2}, {Sample::Timeout, 1}, {Sample::Idle, 3, HeadPetGesture::Release}
    });
    expectEvents("interrupted idle samples armed input at startup", {
        {Sample::Idle, 2}, {Sample::Timeout, 5}, {Sample::Idle, 1}, {Sample::Low, 6}
    });
    expectEvents("interrupted idle samples rearmed input after release", {
        {Sample::Idle, 3}, {Sample::Low, 6, HeadPetGesture::Press}, {Sample::Idle, 3, HeadPetGesture::Release},
        {Sample::Idle, 2}, {Sample::Timeout, 5}, {Sample::Idle, 1}, {Sample::Low, 6}
    });
}
