#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef int esp_err_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NO_MEM 0x101
#define ESP_ERR_INVALID_ARG 0x102
#define ESP_ERR_INVALID_STATE 0x103
#define ESP_ERR_NOT_SUPPORTED 0x106

void test_error_check(esp_err_t error, const char *expression);
#define ESP_ERROR_CHECK(expr) test_error_check((expr), #expr)
void test_log(const char *format, ...);
#define ESP_LOGI(tag, ...) test_log(__VA_ARGS__)
#define ESP_LOGE(tag, ...) test_log(__VA_ARGS__)

typedef void *TaskHandle_t;
typedef void *QueueHandle_t;
typedef unsigned TickType_t;
#define pdPASS 1
#define pdTRUE 1
#define pdFALSE 0
#define portTICK_PERIOD_MS 10
#define portMAX_DELAY UINT32_MAX
#define pdMS_TO_TICKS(ms) ((ms) / portTICK_PERIOD_MS)
#define eDeleted 1
int xTaskCreate(void (*task)(void *), const char *, unsigned, void *, unsigned, TaskHandle_t *);
void vTaskDelete(TaskHandle_t);
void vTaskDelay(TickType_t);
int eTaskGetState(TaskHandle_t);
QueueHandle_t xQueueCreate(unsigned, unsigned);
int xQueueReset(QueueHandle_t);
int xQueueSend(QueueHandle_t, const void *, TickType_t);
int xQueueReceive(QueueHandle_t, void *, TickType_t);
void vQueueDelete(QueueHandle_t);

typedef struct { int type; } uart_event_t;
#define UART_DATA 1
int uart_driver_install(int, int, int, int, QueueHandle_t *, int);
int uart_driver_delete(int);
int uart_read_bytes(int, void *, int, unsigned);
int uart_write_bytes(int, const void *, int);

typedef struct { size_t max_cmdline_args, max_cmdline_length; } esp_console_config_t;
typedef struct {
    const char *command;
    const char *help;
    int (*func)(int, char **);
} esp_console_cmd_t;
typedef struct { int unused; } esp_console_repl_t;
typedef struct {
    const char *prompt;
    size_t max_cmdline_length;
    const char *history_save_path;
    unsigned max_history_len;
} esp_console_repl_config_t;
#define ESP_CONSOLE_REPL_CONFIG_DEFAULT() {NULL, 256, NULL, 32}
typedef struct { int unused; } esp_console_dev_uart_config_t;
typedef struct { int unused; } esp_console_dev_usb_cdc_config_t;
typedef struct { int unused; } esp_console_dev_usb_serial_jtag_config_t;
#define ESP_CONSOLE_DEV_UART_CONFIG_DEFAULT() {0}
#define ESP_CONSOLE_DEV_CDC_CONFIG_DEFAULT() {0}
#define ESP_CONSOLE_DEV_USB_SERIAL_JTAG_CONFIG_DEFAULT() {0}
esp_err_t esp_console_init(const esp_console_config_t *);
esp_err_t esp_console_deinit(void);
esp_err_t esp_console_cmd_register(const esp_console_cmd_t *);
esp_err_t esp_console_new_repl_uart(const esp_console_dev_uart_config_t *, const esp_console_repl_config_t *, esp_console_repl_t **);
esp_err_t esp_console_new_repl_usb_cdc(const esp_console_dev_usb_cdc_config_t *, const esp_console_repl_config_t *, esp_console_repl_t **);
esp_err_t esp_console_new_repl_usb_serial_jtag(const esp_console_dev_usb_serial_jtag_config_t *, const esp_console_repl_config_t *, esp_console_repl_t **);
esp_err_t esp_console_start_repl(esp_console_repl_t *);
esp_err_t esp_console_run(const char *, int *);
void linenoiseHistoryFree(void);
struct os_mbuf;

#ifdef __cplusplus
}
#endif
