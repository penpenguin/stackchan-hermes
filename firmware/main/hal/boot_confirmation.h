#pragma once

#include <esp_ota_ops.h>

namespace stackchan::local {

// Call once after local initialization succeeds, before apps can request a reboot.
inline esp_err_t confirm_running_image()
{
    const auto* partition = esp_ota_get_running_partition();
    if (partition == nullptr) { return ESP_ERR_NOT_FOUND; }
    esp_ota_img_states_t state = ESP_OTA_IMG_UNDEFINED;
    const auto result = esp_ota_get_state_partition(partition, &state);
    // A USB installation or factory partition may have no image state to confirm.
    if (result == ESP_ERR_NOT_FOUND || result == ESP_ERR_NOT_SUPPORTED) { return ESP_OK; }
    if (result != ESP_OK) { return result; }
    if (state != ESP_OTA_IMG_PENDING_VERIFY) { return ESP_OK; }
    return esp_ota_mark_app_valid_cancel_rollback();
}

}  // namespace stackchan::local
