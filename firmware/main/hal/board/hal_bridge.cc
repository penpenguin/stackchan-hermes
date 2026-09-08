/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "hal_bridge.h"
#include "stackchan_display.h"
#include <esp_log.h>
#include <esp_err.h>
#include <nvs.h>
#include <nvs_flash.h>
#include <driver/gpio.h>
#include <esp_event.h>
#include <audio/audio_service.h>
#include <esp_timer.h>
#include <atomic>
#include <board.h>
#include <display.h>
#include <mutex>
#include <utility>
#include <assets.h>
#include <hal/local_tasks.h>

static const char* _tag = "HAL_BRIDGE";

namespace hal_bridge {

/* -------------------------------------------------------------------------- */
/*                            State and touch point                           */
/* -------------------------------------------------------------------------- */

static std::mutex _mutex;
static Data_t _data;
static stackchan::local::LocalTasks local_tasks;

bool app_schedule(std::function<void()> callback)
{
    return local_tasks.schedule(std::move(callback));
}

void update_local_tasks()
{
    local_tasks.runOne();
}

void lock()
{
    _mutex.lock();
}

void unlock()
{
    _mutex.unlock();
}

Data_t& get_data()
{
    return _data;
}

void set_touch_point(int num, int x, int y)
{
    std::lock_guard<std::mutex> lock(_mutex);
    _data.touchPoint.num = num;
    _data.touchPoint.x   = x;
    _data.touchPoint.y   = y;
}

TouchPoint_t get_touch_point()
{
    std::lock_guard<std::mutex> lock(_mutex);
    return _data.touchPoint;
}

/* -------------------------------------------------------------------------- */
/*                                   Display                                  */
/* -------------------------------------------------------------------------- */
#define DISPLAY_TYPE StackChanAvatarDisplay

lv_disp_t* display_get_lvgl_display()
{
    auto display = static_cast<DISPLAY_TYPE*>(Board::GetInstance().GetDisplay());
    return display->GetLvglDisplay();
}

void disply_lvgl_lock()
{
    auto display = static_cast<DISPLAY_TYPE*>(Board::GetInstance().GetDisplay());
    display->LvglLock();
}

void disply_lvgl_unlock()
{
    auto display = static_cast<DISPLAY_TYPE*>(Board::GetInstance().GetDisplay());
    display->LvglUnlock();
}

/* -------------------------------------------------------------------------- */
/*                                 Application                                */
/* -------------------------------------------------------------------------- */

void board_init()
{
    // Init board
    auto& board = Board::GetInstance();
}

void app_play_sound(const std::string_view& sound)
{
    note_activity();
    local_audio().PlaySound(sound);
}

namespace {
std::atomic<bool> audio_ready{false};
std::atomic<uint32_t> last_activity_ms{0};
}

AudioService& local_audio()
{
    static AudioService service;
    return service;
}

void initialize_local_audio()
{
    auto* codec = Board::GetInstance().GetAudioCodec();
    if (codec == nullptr) { return; }
    auto& service = local_audio();
    service.Initialize(codec);
    Assets::GetInstance().Apply();
    service.Start();
    audio_ready.store(true);
    note_activity();
}

bool local_audio_busy()
{
    if (!audio_ready.load()) { return false; }
    auto& service = local_audio();
    return !service.IsIdle() || service.IsAudioProcessorRunning();
}

void note_activity()
{
    last_activity_ms.store(static_cast<uint32_t>(esp_timer_get_time() / 1000));
}

uint32_t idle_milliseconds()
{
    return static_cast<uint32_t>(esp_timer_get_time() / 1000) - last_activity_ms.load();
}

}  // namespace hal_bridge
