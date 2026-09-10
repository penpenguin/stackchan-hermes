#include "console_fakes.h"
#include <hal/local_console.h>
#include <hal/utils/bleprph/nimble_peripheral_utils/esp_peripheral.h>
#include <settings.h>

#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

namespace {
bool initialized = false;
bool running = false;
bool registeredAfterStart = false;
bool registeredKeyWithoutQueue = false;
unsigned initCalls = 0;
unsigned replCreates = 0;
unsigned replStarts = 0;
unsigned legacyTasks = 0;
unsigned uartInstalls = 0;
unsigned queueCreates = 0;
unsigned queueDeletes = 0;
unsigned commandRegisters = 0;
unsigned historyClears = 0;
TickType_t receiveTimeout = 0;
std::optional<int> queuedKey;
std::map<std::string, esp_console_cmd_t> commands;
esp_console_repl_t repl{};
esp_console_repl_config_t replConfig{};
std::string transport;
std::string failure;
std::string logOutput;
}

extern "C" {
void test_error_check(esp_err_t error, const char *expression) {
    if (error != ESP_OK) {
        std::fprintf(stderr, "ESP_ERROR_CHECK(%s) failed: 0x%x\n", expression, error);
        std::exit(1);
    }
}
void test_log(const char *format, ...) {
    va_list args;
    va_start(args, format);
    char buffer[256];
    std::vsnprintf(buffer, sizeof(buffer), format, args);
    logOutput += buffer;
    va_end(args);
}
esp_err_t esp_console_init(const esp_console_config_t *) {
    ++initCalls;
    if (initialized) return ESP_ERR_INVALID_STATE;
    initialized = true;
    return ESP_OK;
}
esp_err_t esp_console_deinit(void) { initialized = false; return ESP_OK; }
esp_err_t esp_console_cmd_register(const esp_console_cmd_t *command) {
    ++commandRegisters;
    registeredAfterStart |= running;
    registeredKeyWithoutQueue |= std::string(command->command) == "key" && queueCreates == 0;
    if (failure == command->command) return ESP_FAIL;
    commands[command->command] = *command;
    return ESP_OK;
}
static esp_err_t create_repl(const char *backend, const esp_console_repl_config_t *config, esp_console_repl_t **out) {
    ++replCreates;
    if (failure == "create") return ESP_ERR_NO_MEM;
    const auto error = esp_console_init(nullptr);
    if (error != ESP_OK) return error;
    transport = backend;
    replConfig = *config;
    *out = &repl;
    return ESP_OK;
}
esp_err_t esp_console_new_repl_uart(const esp_console_dev_uart_config_t *, const esp_console_repl_config_t *config, esp_console_repl_t **out) {
    return create_repl("uart", config, out);
}
esp_err_t esp_console_new_repl_usb_cdc(const esp_console_dev_usb_cdc_config_t *, const esp_console_repl_config_t *config, esp_console_repl_t **out) {
    return create_repl("cdc", config, out);
}
esp_err_t esp_console_new_repl_usb_serial_jtag(const esp_console_dev_usb_serial_jtag_config_t *, const esp_console_repl_config_t *config, esp_console_repl_t **out) {
    return create_repl("jtag", config, out);
}
esp_err_t esp_console_start_repl(esp_console_repl_t *handle) {
    ++replStarts;
    assert(handle == &repl);
    if (failure == "start") return ESP_FAIL;
    if (running) return ESP_ERR_INVALID_STATE;
    running = true;
    return ESP_OK;
}
esp_err_t esp_console_run(const char *line, int *result) {
    assert(running);
    std::istringstream stream(line);
    std::vector<std::string> words;
    for (std::string word; stream >> word;) words.push_back(word);
    assert(!words.empty() && commands.count(words[0]) == 1);
    std::vector<char *> args;
    for (auto& word : words) args.push_back(word.data());
    *result = commands.at(words[0]).func(static_cast<int>(args.size()), args.data());
    return ESP_OK;
}
void linenoiseHistoryFree(void) { ++historyClears; }
int xTaskCreate(void (*task)(void *), const char *, unsigned, void *arg, unsigned, TaskHandle_t *handle) {
    ++legacyTasks;
    *handle = reinterpret_cast<void *>(1);
    // A newly created higher-priority task may run immediately on the device.
    task(arg);
    return pdPASS;
}
void vTaskDelete(TaskHandle_t) {}
void vTaskDelay(TickType_t) {}
int eTaskGetState(TaskHandle_t) { return eDeleted; }
QueueHandle_t xQueueCreate(unsigned count, unsigned size) {
    assert(count == 1 && size == sizeof(int));
    ++queueCreates;
    if (failure == "queue") return nullptr;
    return &queuedKey;
}
int xQueueSend(QueueHandle_t handle, const void *value, TickType_t timeout) {
    assert(handle == &queuedKey && timeout == 0);
    if (queuedKey) return pdFALSE;
    queuedKey = *static_cast<const int *>(value);
    return pdPASS;
}
int xQueueReceive(QueueHandle_t handle, void *value, TickType_t timeout) {
    assert(handle == &queuedKey && value != nullptr);
    receiveTimeout = timeout;
    if (!queuedKey) return pdFALSE;
    *static_cast<int *>(value) = *queuedKey;
    queuedKey.reset();
    return pdPASS;
}
void vQueueDelete(QueueHandle_t handle) {
    assert(handle == &queuedKey);
    ++queueDeletes;
    queuedKey.reset();
}
int uart_driver_install(int, int, int, int, QueueHandle_t *queue, int) {
    ++uartInstalls;
    *queue = reinterpret_cast<void *>(2);
    return ESP_OK;
}
int uart_driver_delete(int) { return ESP_OK; }
int uart_read_bytes(int, void *, int, unsigned) { std::abort(); }
int uart_write_bytes(int, const void *, int) { std::abort(); }
}

int runCommand(const std::string& line) {
    int result = -1;
    assert(esp_console_run(line.c_str(), &result) == ESP_OK);
    return result;
}

int main(int argc, char **argv) {
    const std::string scenario = argc > 1 ? argv[1] : "startup";
    if (scenario == "uninitialized") {
        int value = 99;
        assert(scli_receive_key(&value) == pdFALSE);
        assert(scli_receive_key(nullptr) == pdFALSE);
        assert(value == 99);
        return 0;
    }
    if (scenario == "failure") {
        assert(argc == 3);
        failure = argv[2];
        const auto result = stackchan::local::startLocalConsole();
        const auto expected = failure == "queue" || failure == "create" ? ESP_ERR_NO_MEM : ESP_FAIL;
        assert(result == expected && !running);
        const auto registrations = commandRegisters;
        const auto queues = queueCreates;
        assert(stackchan::local::startLocalConsole() == result);
        assert(replCreates == 1 && queueCreates == queues && commandRegisters == registrations);
        assert(replStarts == (failure == "start" ? 1u : 0u));
        assert(queueDeletes == (failure == "key" ? 1u : 0u));
        assert(commands.count(failure) == 0);
        return 0;
    }
    if (scenario == "unsupported") {
        assert(stackchan::local::startLocalConsole() == ESP_ERR_NOT_SUPPORTED);
        assert(stackchan::local::startLocalConsole() == ESP_ERR_NOT_SUPPORTED);
        assert(replCreates == 0 && queueCreates == 0 && commandRegisters == 0);
        return 0;
    }

    assert(stackchan::local::startLocalConsole() == ESP_OK);
    // Repeated BLE registration must never start another console or input task.
    assert(scli_init() == ESP_OK);
    assert(stackchan::local::startLocalConsole() == ESP_OK);
    assert(initCalls == 1);
    assert(replCreates == 1 && replStarts == 1);
    assert(legacyTasks == 0 && uartInstalls == 0);
    assert(queueCreates == 1 && queueDeletes == 0);
    assert(!registeredAfterStart && !registeredKeyWithoutQueue);
    assert(replConfig.max_cmdline_length == 640);
    assert(replConfig.max_history_len == 1 && replConfig.history_save_path == nullptr);
#if CONFIG_STACKCHAN_HERMES_USB_PROVISIONING
    assert(commands.size() == 2 && commands.count("stackchan-hermes") == 1);
    assert(std::string(replConfig.prompt) == "hermes-config>");
#else
    assert(commands.size() == 1 && commands.count("stackchan-hermes") == 0);
    assert(std::string(replConfig.prompt) == "stackchan>");
#endif
#if defined(CONFIG_ESP_CONSOLE_UART_DEFAULT) || defined(CONFIG_ESP_CONSOLE_UART_CUSTOM)
    assert(transport == "uart");
#elif defined(CONFIG_ESP_CONSOLE_USB_CDC)
    assert(transport == "cdc");
#else
    assert(transport == "jtag");
#endif

    if (scenario == "keys") {
        for (const auto& [input, expected] : std::vector<std::pair<std::string, int>>{
                {"Y", 1}, {"Yes", 1}, {"N", 0}, {"No", 0}, {"y", 1}, {"no", 0}, {"123456", 123456}}) {
            assert(runCommand("key " + input) == 0);
            int value = -1;
            assert(scli_receive_key(&value) == pdPASS && value == expected);
        }
        int value = -1;
        assert(scli_receive_key(&value) == pdFALSE);
        assert(value == -1 && receiveTimeout == pdMS_TO_TICKS(30000));
        assert(historyClears == 7);
        assert(logOutput.empty());
    } else if (scenario == "full") {
        assert(runCommand("key Y") == 0);
        assert(runCommand("key N") != 0);
        int value = -1;
        assert(scli_receive_key(&value) == pdPASS && value == 1);
        assert(runCommand("key N") == 0);
        assert(scli_receive_key(&value) == pdPASS && value == 0);
    } else if (scenario == "null") {
        assert(scli_receive_key(nullptr) == pdFALSE);
    } else if (scenario == "provisioning") {
        assert(runCommand("stackchan-hermes set-brightness 42") == 0);
        assert((Settings::integers.at({"display", "brightness"}) == 42));
        assert(runCommand("stackchan-hermes set-token " + std::string(512, 'x')) == 0);
        assert((Settings::strings.at({"bridge", "token"}) == std::string(512, 'x')));
        assert(runCommand("stackchan-hermes set-brightness 101") != 0);
        assert((Settings::integers.at({"display", "brightness"}) == 42));
        assert(historyClears == 3 && logOutput.empty());
        assert(runCommand("key Y") == 0);
        int value = -1;
        assert(scli_receive_key(&value) == pdPASS && value == 1);
    } else {
        assert(scenario == "startup");
    }
}
