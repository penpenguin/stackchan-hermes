#include "local_console.h"

#include <esp_console.h>
#include <sdkconfig.h>

#include "stackchan_bridge_provisioning.h"
#include "utils/bleprph/nimble_peripheral_utils/esp_peripheral.h"

namespace stackchan::local {
namespace {

// The console, its command handlers and their queues live until the next reboot.
esp_console_repl_t* consoleRepl = nullptr;

esp_err_t initializeConsole()
{
    esp_console_repl_config_t replConfig = ESP_CONSOLE_REPL_CONFIG_DEFAULT();
#if CONFIG_STACKCHAN_HERMES_USB_PROVISIONING
    replConfig.prompt = "hermes-config>";
#else
    replConfig.prompt = "stackchan>";
#endif
    replConfig.max_cmdline_length = 640;
    replConfig.history_save_path = nullptr;
    replConfig.max_history_len = 1;

    esp_err_t result = ESP_ERR_NOT_SUPPORTED;
#if defined(CONFIG_ESP_CONSOLE_UART_DEFAULT) || defined(CONFIG_ESP_CONSOLE_UART_CUSTOM)
    esp_console_dev_uart_config_t deviceConfig = ESP_CONSOLE_DEV_UART_CONFIG_DEFAULT();
    result = esp_console_new_repl_uart(&deviceConfig, &replConfig, &consoleRepl);
#elif defined(CONFIG_ESP_CONSOLE_USB_CDC)
    esp_console_dev_usb_cdc_config_t deviceConfig = ESP_CONSOLE_DEV_CDC_CONFIG_DEFAULT();
    result = esp_console_new_repl_usb_cdc(&deviceConfig, &replConfig, &consoleRepl);
#elif defined(CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG)
    esp_console_dev_usb_serial_jtag_config_t deviceConfig =
        ESP_CONSOLE_DEV_USB_SERIAL_JTAG_CONFIG_DEFAULT();
    result = esp_console_new_repl_usb_serial_jtag(&deviceConfig, &replConfig, &consoleRepl);
#endif
    if (result != ESP_OK) {
        return result;
    }

    result = scli_init();
    if (result != ESP_OK) {
        return result;
    }
#if CONFIG_STACKCHAN_HERMES_USB_PROVISIONING
    result = hermes::registerStackchanHermesProvisioningCommands();
    if (result != ESP_OK) {
        return result;
    }
#endif

    // Publish all handlers before the REPL can execute any command.
    return esp_console_start_repl(consoleRepl);
}

}  // namespace

esp_err_t startLocalConsole()
{
    // Never allocate another REPL or restart a partially initialized console.
    static const esp_err_t result = initializeConsole();
    return result;
}

}  // namespace stackchan::local
