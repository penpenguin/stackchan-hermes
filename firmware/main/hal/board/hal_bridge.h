/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once
#include "stackchan_camera.h"
#include "device_config.h"
#include <hal/local_activity.h>
#include <cstdint>
#include <functional>
#include <lvgl.h>
#include <driver/i2c_master.h>
#include <string_view>

class AudioService;

namespace hal_bridge {

struct TouchPoint_t {
    int num = 0;
    int x   = -1;
    int y   = -1;
};

struct Data_t {
    TouchPoint_t touchPoint;
};

void lock();
void unlock();
Data_t& get_data();

void set_touch_point(int num, int x, int y);
TouchPoint_t get_touch_point();

void disply_lvgl_lock();
void disply_lvgl_unlock();
lv_disp_t* display_get_lvgl_display();

void board_init();
esp_err_t board_prepare_espnow(int channel);
void initialize_local_audio();
bool app_schedule(std::function<void()> callback);
void update_local_tasks();
AudioService& local_audio();
bool local_audio_busy();

i2c_master_bus_handle_t board_get_i2c_bus();
StackChanCamera* board_get_camera();
int board_get_battery_level();
bool board_is_battery_charging();
void board_set_backlight_brightness(uint8_t brightness, bool permanent = false);
uint8_t board_get_backlight_brightness();
void board_set_speaker_volume(uint8_t volume, bool permanent = false);
uint8_t board_get_speaker_volume();

void app_play_sound(const std::string_view& sound);

}  // namespace hal_bridge
