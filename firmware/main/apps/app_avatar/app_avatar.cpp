/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "app_avatar.h"
#include <hal/hal.h>
#include <mooncake.h>
#include <mooncake_log.h>
#include <assets/assets.h>
#include <smooth_lvgl.hpp>
#include <stackchan/stackchan.h>
#include <apps/common/common.h>
#include <string_view>
#include <cstdint>
#include <memory>

using namespace mooncake;
using namespace smooth_ui_toolkit::lvgl_cpp;
using namespace stackchan;

AppAvatar::AppAvatar()
{
    // 配置 App 名
    setAppInfo().name = "AVATAR";
    // 配置 App 图标
    static auto icon  = assets::get_image("icon_sentinel.bin");
    setAppInfo().icon = (void*)&icon;
    // 配置 App 主题颜色
    static uint32_t theme_color = 0xFF6699;
    setAppInfo().userData       = (void*)&theme_color;
}

// App 被安装时会被调用
void AppAvatar::onCreate()
{
    mclog::tagInfo(getAppInfo().name, "on create");
}

void AppAvatar::onOpen()
{
    mclog::tagInfo(getAppInfo().name, "on open");

    GetHAL().startBleServer();
    LvglLockGuard lock;

    // Create default avatar
    auto avatar = std::make_unique<avatar::DefaultAvatar>();
    avatar->init(lv_screen_active());
    avatar->getPanel()->onClick().connect([&]() { _screen_clicked_flag = true; });
    GetStackChan().attachAvatar(std::move(avatar));

    /* ------------------------------- BLE events ------------------------------- */
    GetHAL().onBleAvatarData.connect([&](const char* data) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_ble_avatar_data.update_flag) {
            return;
        }
        _ble_avatar_data.update_flag = true;
        _ble_avatar_data.data_ptr    = (char*)data;
    });

    GetHAL().onBleMotionData.connect([&](const char* data) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_ble_motion_data.update_flag) {
            return;
        }
        _ble_motion_data.update_flag = true;
        _ble_motion_data.data_ptr    = (char*)data;
    });

    /* ----------------------------- Common widgets ----------------------------- */
    view::create_home_indicator([&]() { close(); }, 0xFF9ABC, 0x431525);
    view::create_status_bar(0xFF9ABC, 0x431525);
}

void AppAvatar::onRunning()
{
    std::lock_guard<std::mutex> lock(_mutex);

    LvglLockGuard lvgl_lock;

    if (_ble_avatar_data.update_flag) {
        GetStackChan().updateAvatarFromJson(_ble_avatar_data.data_ptr);
        _ble_avatar_data.update_flag = false;
        _ble_avatar_data.data_ptr    = nullptr;
    }

    if (_ble_motion_data.update_flag) {
        check_auto_angle_sync_mode();
        GetStackChan().updateMotionFromJson(_ble_motion_data.data_ptr);
        _ble_motion_data.update_flag = false;
        _ble_motion_data.data_ptr    = nullptr;
    }

    if (_screen_clicked_flag) {
        _screen_clicked_flag = false;
        if (_dance_modifier_id >= 0) {
            GetStackChan().removeModifier(_dance_modifier_id);
            _dance_modifier_id = -1;
            mclog::tagInfo(getAppInfo().name, "dance modifier removed");
        }
    }

    GetStackChan().update();

    view::update_home_indicator();
    view::update_status_bar();
}

void AppAvatar::onClose()
{
    mclog::tagInfo(getAppInfo().name, "on close");

    {
        LvglLockGuard lock;

        GetStackChan().resetAvatar();

        GetHAL().onBleAvatarData.clear();
        GetHAL().onBleMotionData.clear();

        view::destroy_home_indicator();
        view::destroy_status_bar();
    }

    GetHAL().requestWarmReboot("AVATAR");
}

void AppAvatar::check_auto_angle_sync_mode()
{
    auto& motion = GetStackChan().motion();

    // If far from last command, enable auto angle sync
    if (GetHAL().millis() - _last_motion_cmd_tick > 2000) {
        motion.setAutoAngleSyncEnabled(true);
    } else {
        motion.setAutoAngleSyncEnabled(false);
    }

    _last_motion_cmd_tick = GetHAL().millis();
}
