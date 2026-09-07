#include "stackchan_bridge_provisioning.h"

#include <cstdio>

#include <esp_console.h>
#include <esp_err.h>
#include <linenoise/linenoise.h>
#include <settings.h>
#include <stackchan_bridge_client/provisioning.h>

#if CONFIG_STACKCHAN_HERMES_ATTENDED_WIFI_CYCLE
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <wifi_manager.h>
#endif

namespace stackchan::hermes {
namespace {

constexpr char kPrompt[] = "hermes-config>";
esp_console_repl_t* provisioningRepl = nullptr;
#if CONFIG_STACKCHAN_HERMES_ATTENDED_WIFI_CYCLE
bool wifiCycleUsed = false;
#endif

int handleProvisioningCommand(int argumentCount, char** arguments)
{
    linenoiseHistoryFree();
    const auto result = bridge_client::parseProvisioningArguments(
        argumentCount,
        const_cast<const char* const*>(arguments)
    );
    if (result.error == bridge_client::ProvisioningError::InvalidArguments) {
        std::fputs(
            "ERROR usage: stackchan-hermes <command> <value>\n",
            stderr
        );
        return 1;
    }
    if (result.error != bridge_client::ProvisioningError::None) {
        std::fputs("ERROR invalid value\n", stderr);
        return 1;
    }

    switch (result.action) {
        case bridge_client::ProvisioningAction::SetDeviceId: {
            Settings settings("device", true);
            settings.SetString("id", result.value);
            break;
        }
        case bridge_client::ProvisioningAction::SetDeviceName: {
            Settings settings("device", true);
            settings.SetString("name", result.value);
            break;
        }
        case bridge_client::ProvisioningAction::SetBridgeUrl: {
            Settings settings("bridge", true);
            settings.SetString("url", result.value);
            break;
        }
        case bridge_client::ProvisioningAction::SetBridgeFallbackUrl: {
            Settings settings("bridge", true);
            settings.SetString("fallback_url", result.value);
            break;
        }
        case bridge_client::ProvisioningAction::SetBridgeToken: {
            Settings settings("bridge", true);
            settings.SetString("token", result.value);
            break;
        }
        case bridge_client::ProvisioningAction::SetBridgeDiscoveryEnabled: {
            Settings settings("bridge", true);
            settings.SetBool("discovery", result.boolValue);
            break;
        }
        case bridge_client::ProvisioningAction::SetAudioVolume: {
            Settings settings("audio", true);
            settings.SetInt("volume", result.numericValue);
            break;
        }
        case bridge_client::ProvisioningAction::SetDisplayBrightness: {
            Settings settings("display", true);
            settings.SetInt("brightness", result.numericValue);
            break;
        }
        case bridge_client::ProvisioningAction::SetMotionIdleLevel: {
            Settings settings("motion", true);
            settings.SetInt("idle_level", result.numericValue);
            break;
        }
        case bridge_client::ProvisioningAction::SetTouchEnabled: {
            Settings settings("touch", true);
            settings.SetBool("enabled", result.boolValue);
            break;
        }
        case bridge_client::ProvisioningAction::CycleWifi: {
#if CONFIG_STACKCHAN_HERMES_ATTENDED_WIFI_CYCLE
            auto& wifi = WifiManager::GetInstance();
            const auto authorization = bridge_client::authorizeAttendedWifiCycle(
                wifi.IsConnected(),
                wifiCycleUsed
            );
            if (authorization == bridge_client::WifiCycleAuthorization::AlreadyUsed) {
                std::fputs("ERROR Wi-Fi cycle already used this boot\n", stderr);
                return 1;
            }
            if (authorization == bridge_client::WifiCycleAuthorization::NotConnected) {
                std::fputs("ERROR Wi-Fi station is not connected\n", stderr);
                return 1;
            }

            std::fputs("OK Wi-Fi cycle starting\n", stdout);
            wifi.StopStation();
            vTaskDelay(pdMS_TO_TICKS(result.numericValue * 1000));
            wifi.StartStation();
            std::fputs("OK Wi-Fi station restart requested\n", stdout);
            return 0;
#else
            std::fputs("ERROR Wi-Fi cycle diagnostic disabled\n", stderr);
            return 1;
#endif
        }
        case bridge_client::ProvisioningAction::None:
            std::fputs("ERROR unsupported action\n", stderr);
            return 1;
    }

    std::fputs("OK saved; reboot required\n", stdout);
    return 0;
}

}  // namespace

bool startStackchanHermesProvisioningConsole()
{
    if (provisioningRepl != nullptr) {
        return true;
    }

    esp_console_cmd_t command{};
    command.command = "stackchan-hermes";
    command.help = "Provision validated StackChan Hermes runtime settings in NVS";
    command.func = handleProvisioningCommand;
    if (esp_console_cmd_register(&command) != ESP_OK) {
        return false;
    }

    esp_console_repl_config_t replConfig = ESP_CONSOLE_REPL_CONFIG_DEFAULT();
    replConfig.prompt = kPrompt;
    replConfig.max_cmdline_length = 640;
    replConfig.history_save_path = nullptr;
    replConfig.max_history_len = 1;

#if defined(CONFIG_ESP_CONSOLE_UART_DEFAULT) || defined(CONFIG_ESP_CONSOLE_UART_CUSTOM)
    esp_console_dev_uart_config_t deviceConfig = ESP_CONSOLE_DEV_UART_CONFIG_DEFAULT();
    if (esp_console_new_repl_uart(&deviceConfig, &replConfig, &provisioningRepl) != ESP_OK) {
        return false;
    }
#elif defined(CONFIG_ESP_CONSOLE_USB_CDC)
    esp_console_dev_usb_cdc_config_t deviceConfig = ESP_CONSOLE_DEV_CDC_CONFIG_DEFAULT();
    if (esp_console_new_repl_usb_cdc(&deviceConfig, &replConfig, &provisioningRepl) != ESP_OK) {
        return false;
    }
#elif defined(CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG)
    esp_console_dev_usb_serial_jtag_config_t deviceConfig =
        ESP_CONSOLE_DEV_USB_SERIAL_JTAG_CONFIG_DEFAULT();
    if (esp_console_new_repl_usb_serial_jtag(&deviceConfig, &replConfig, &provisioningRepl)
        != ESP_OK) {
        return false;
    }
#else
    return false;
#endif

    return esp_console_start_repl(provisioningRepl) == ESP_OK;
}

}  // namespace stackchan::hermes
