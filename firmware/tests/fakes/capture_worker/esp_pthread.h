#pragma once

#include "platform.h"

struct esp_pthread_cfg_t {
    std::size_t stack_size = 0;
    bool inherit_cfg = false;
    const char* thread_name = nullptr;
};
constexpr int ESP_ERR_INVALID_ARG = 0x102;
constexpr int ESP_ERR_NOT_FOUND = 0x105;

namespace worker_fake {
inline int readConfigResult = ESP_ERR_NOT_FOUND;
inline int configResult = ESP_OK;
inline int restoreResult = ESP_OK;
inline esp_pthread_cfg_t currentConfig{};
}

inline esp_pthread_cfg_t esp_pthread_get_default_config() { return {}; }

inline int esp_pthread_get_cfg(esp_pthread_cfg_t* config)
{
    *config = worker_fake::currentConfig;
    return worker_fake::readConfigResult;
}

inline int esp_pthread_set_cfg(const esp_pthread_cfg_t* config)
{
    const int result = config->stack_size == 12288 ? worker_fake::configResult : worker_fake::restoreResult;
    if (result == ESP_OK) { worker_fake::currentConfig = *config; }
    return result;
}
