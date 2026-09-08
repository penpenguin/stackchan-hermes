/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include <smooth_ui_toolkit.hpp>
#include <uitk/short_namespace.hpp>
#include <mooncake_log.h>
#include <mooncake.h>
#include <apps/apps.h>
#include <apps/common/toast/toast.h>
#include <hal/hal.h>
#include <hal/stackchan_bridge_provisioning.h>
#include <hal/stackchan_bridge_service.h>
#include <hal/board/hal_bridge.h>
#include <apps/common/common.h>
#include <assets/assets.h>

using namespace mooncake;
using namespace smooth_ui_toolkit;

extern "C" void app_main(void)
{
    // Setup logger
    mclog::set_level(mclog::level_info);
    mclog::set_time_format(mclog::time_format_unix_milliseconds);

    // HAL init
    GetHAL().init();

    // Setup ui hal
    ui_hal::on_delay([](uint32_t ms) { GetHAL().delay(ms); });
    ui_hal::on_get_tick([]() { return GetHAL().millis(); });

#if CONFIG_STACKCHAN_HERMES_USB_PROVISIONING
    if (!stackchan::hermes::startStackchanHermesProvisioningConsole()) {
        mclog::error("StackChan Hermes provisioning console did not start");
    }
#endif

    GetMooncake().installApp(std::make_unique<AppLauncher>());
    GetMooncake().installApp(std::make_unique<AppAvatar>());
    GetMooncake().installApp(std::make_unique<AppEspnowControl>());
    GetMooncake().installApp(std::make_unique<AppDance>());
    GetMooncake().installApp(std::make_unique<AppSetup>());

    if (!view::initialize_toast_manager()) {
        mclog::error("Toast manager did not start");
    }
    tools::on_reminder_triggered().connect([](int, std::string_view message) {
        view::pop_a_toast(std::string(message), view::ToastType::Info);
        hal_bridge::app_play_sound(OGG_NEW_NOTIFICATION);
    });
#if CONFIG_STACKCHAN_HERMES_BRIDGE_CLIENT
    if (!stackchan::hermes::startStackchanHermesBridgeClient()) {
        mclog::error("StackChan Hermes Bridge client did not start");
    }
#endif
    while (true) {
        GetHAL().feedTheDog();
        GetHAL().updateHeapStatusLog();
        hal_bridge::update_local_tasks();
        tools::update_reminders();
        GetMooncake().update();
    }
}
