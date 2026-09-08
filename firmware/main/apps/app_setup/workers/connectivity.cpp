/* SPDX-License-Identifier: MIT */
#include "workers.h"
#include <hal/hal.h>
#include <board.h>
#include <wifi_board.h>
#include <wifi_manager.h>

using namespace smooth_ui_toolkit::lvgl_cpp;
using namespace setup_workers;

WifiSetupWorker::WifiSetupWorker()
{
    GetHAL().startNetwork(nullptr);
    static_cast<WifiBoard&>(Board::GetInstance()).EnterWifiConfigMode();
    _panel = std::make_unique<Container>(lv_screen_active());
    _panel->setSize(320, 240);
    _panel->align(LV_ALIGN_CENTER, 0, 0);
    _panel->setBgColor(lv_color_hex(0xEDF4FF));
    _info = std::make_unique<Label>(_panel->get());
    _info->setWidth(296);
    _info->setTextFont(&lv_font_montserrat_16);
    _info->setTextColor(lv_color_hex(0x26206A));
    _info->setTextAlign(LV_TEXT_ALIGN_CENTER);
    _info->align(LV_ALIGN_TOP_MID, 0, 12);
    _done = std::make_unique<Button>(_panel->get());
    apply_button_common_style(*_done);
    _done->align(LV_ALIGN_BOTTOM_MID, 0, -12);
    _done->label().setText("Done");
    _done->onClick().connect([this]() { _done_clicked = true; });
}

WifiSetupWorker::~WifiSetupWorker() = default;

void WifiSetupWorker::update()
{
    auto& wifi = WifiManager::GetInstance();
    if (wifi.IsConnected()) {
        _info->setText("Wi-Fi connected.\nConfigure your Bridge over USB.");
    } else {
        _info->setText("Wi-Fi Setup\nConnect to hotspot:\n" + wifi.GetApSsid()
                       + "\nOpen in a browser:\n" + wifi.GetApWebUrl()
                       + "\nBridge setup is available over USB.");
    }
    if (_done_clicked) { _is_done = true; }
}
