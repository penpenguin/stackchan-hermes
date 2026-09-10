#pragma once

#include <esp_err.h>

namespace stackchan::local {

// Called before app installation. Success and failure are retained until reboot.
esp_err_t startLocalConsole();

}  // namespace stackchan::local
