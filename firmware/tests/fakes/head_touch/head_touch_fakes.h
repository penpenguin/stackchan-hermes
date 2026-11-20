#pragma once

#include <cstddef>
#include <cstdint>
#include <string_view>

using esp_err_t = int;
constexpr esp_err_t ESP_OK = 0;
constexpr esp_err_t ESP_ERR_NO_MEM = 0x101;
constexpr esp_err_t ESP_ERR_INVALID_ARG = 0x102;
constexpr esp_err_t ESP_ERR_TIMEOUT = 0x107;
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGD(...) ((void)0)
#define ESP_LOGE(...) ((void)0)

using i2c_master_bus_handle_t = void*;
using i2c_master_dev_handle_t = void*;
constexpr int I2C_ADDR_BIT_LEN_7 = 0;
struct i2c_device_config_t {
    int dev_addr_length;
    uint16_t device_address;
    uint32_t scl_speed_hz;
};
inline esp_err_t i2c_master_bus_add_device(i2c_master_bus_handle_t bus, const i2c_device_config_t*,
                                           i2c_master_dev_handle_t* dev) {
    *dev = bus;
    return ESP_OK;
}
inline esp_err_t i2c_master_bus_rm_device(i2c_master_dev_handle_t) { return ESP_OK; }
inline esp_err_t i2c_master_transmit(i2c_master_dev_handle_t, const uint8_t*, size_t, int) { return ESP_OK; }
esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t, const uint8_t*, size_t, uint8_t*, size_t, int);

namespace mclog {
inline void tagInfo(std::string_view, const char*) {}
}
enum class HeadPetGesture { None, Press, Release, SwipeForward, SwipeBackward };
struct GestureSignal {
    void emit(HeadPetGesture gesture);
};
struct Hal {
    GestureSignal onHeadPetGesture;
    void head_touch_init();
};
inline Hal& GetHAL() { static Hal hal; return hal; }
namespace hal_bridge {
inline i2c_master_bus_handle_t board_get_i2c_bus() { static int bus; return &bus; }
inline void note_activity() {}
}

constexpr unsigned MALLOC_CAP_SPIRAM = 1;
constexpr unsigned pdMS_TO_TICKS(unsigned ms) { return ms; }
inline uint32_t xTaskGetTickCount() { return 0; }
void vTaskDelay(unsigned ticks);
void xTaskCreatePinnedToCoreWithCaps(void (*task)(void*), const char*, unsigned, void*, unsigned, void*, int, unsigned);
