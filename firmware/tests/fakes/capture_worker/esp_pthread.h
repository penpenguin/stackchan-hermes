#pragma once
#include "platform.h"
struct esp_pthread_cfg_t { std::size_t stack_size=0; bool inherit_cfg=false; const char* thread_name=nullptr; };
constexpr int ESP_ERR_INVALID_ARG = 0x102;
namespace worker_fake { inline int configResult = ESP_OK; }
inline esp_pthread_cfg_t esp_pthread_get_default_config() { return {}; }
inline int esp_pthread_get_cfg(esp_pthread_cfg_t*) { return -1; }
inline int esp_pthread_set_cfg(const esp_pthread_cfg_t*) { return worker_fake::configResult; }
