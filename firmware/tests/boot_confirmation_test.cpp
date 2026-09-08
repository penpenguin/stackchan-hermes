#include <hal/boot_confirmation.h>
#include <cassert>
#include <initializer_list>

namespace {
esp_partition_t partition;
esp_ota_img_states_t state = ESP_OTA_IMG_PENDING_VERIFY;
int confirmations = 0;
bool has_running_partition = true;
esp_err_t state_result = ESP_OK;
esp_err_t confirmation_result = ESP_OK;
}

const esp_partition_t* esp_ota_get_running_partition()
{
    return has_running_partition ? &partition : nullptr;
}
esp_err_t esp_ota_get_state_partition(const esp_partition_t* running, esp_ota_img_states_t* output)
{
    assert(running == &partition);
    *output = state;
    return state_result;
}
esp_err_t esp_ota_mark_app_valid_cancel_rollback()
{
    ++confirmations;
    if (confirmation_result == ESP_OK) { state = ESP_OTA_IMG_VALID; }
    return confirmation_result;
}

int main()
{
    assert(stackchan::local::confirm_running_image() == ESP_OK);
    assert(state == ESP_OTA_IMG_VALID);
    assert(confirmations == 1);
    assert(stackchan::local::confirm_running_image() == ESP_OK);
    assert(confirmations == 1); // A confirmed image does not need another flash write.

    for (auto other : {ESP_OTA_IMG_NEW, ESP_OTA_IMG_UNDEFINED, ESP_OTA_IMG_VALID,
                       ESP_OTA_IMG_INVALID, ESP_OTA_IMG_ABORTED}) {
        state = other;
        assert(stackchan::local::confirm_running_image() == ESP_OK);
        assert(state == other);
        assert(confirmations == 1);
    }

    // USB installation can leave no state record; factory partitions have no OTA state.
    state = ESP_OTA_IMG_PENDING_VERIFY;
    for (auto missing : {ESP_ERR_NOT_FOUND, ESP_ERR_NOT_SUPPORTED}) {
        state_result = missing;
        assert(stackchan::local::confirm_running_image() == ESP_OK);
        assert(confirmations == 1);
    }
    state_result = ESP_FAIL;
    assert(stackchan::local::confirm_running_image() == ESP_FAIL);
    assert(confirmations == 1);

    state_result = ESP_OK;
    has_running_partition = false;
    assert(stackchan::local::confirm_running_image() == ESP_ERR_NOT_FOUND);
    assert(confirmations == 1);

    has_running_partition = true;
    confirmation_result = ESP_FAIL;
    assert(stackchan::local::confirm_running_image() == ESP_FAIL);
    assert(confirmations == 2);
    assert(state == ESP_OTA_IMG_PENDING_VERIFY); // Keep rollback possible on a write failure.
}
