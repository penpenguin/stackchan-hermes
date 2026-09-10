/*
 * SPDX-FileCopyrightText: 2021-2025 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Unlicense OR CC0-1.0
 */

#include <stdio.h>
#include <ctype.h>
#include <string.h>
#include <strings.h>
#include <esp_console.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <linenoise/linenoise.h>
#include "esp_peripheral.h"

#define BLE_RX_TIMEOUT pdMS_TO_TICKS(30000)

static QueueHandle_t cli_handle;

static int enter_passkey_handler(int argc, char *argv[])
{
    int key;
    char pkey[8];
    int num;

    linenoiseHistoryFree();
    if (argc != 2 || cli_handle == NULL) {
        return -1;
    }

    sscanf(argv[1], "%7s", pkey);
    num = pkey[0];

    if (isalpha(num)) {
        if ((strcasecmp(pkey, "Y") == 0) || (strcasecmp(pkey, "Yes") == 0)) {
            key = 1;
        } else {
            key = 0;
        }
    } else {
        if (sscanf(pkey, "%d", &key) != 1) {
            key = 0;
        }
    }

    return xQueueSend(cli_handle, &key, 0) == pdPASS ? 0 : -1;
}

int scli_receive_key(int *console_key)
{
    if (cli_handle == NULL || console_key == NULL) {
        return pdFALSE;
    }
    return xQueueReceive(cli_handle, console_key, BLE_RX_TIMEOUT);
}

static esp_console_cmd_t cmds[] = {
    {
        .command = "key",
        .help    = "",
        .func    = enter_passkey_handler,
    },
};

int scli_init(void)
{
    if (cli_handle != NULL) {
        return ESP_OK;
    }

    /* The shared console owns the input task; this module only receives keys. */
    cli_handle = xQueueCreate(1, sizeof(int));
    if (cli_handle == NULL) {
        return ESP_ERR_NO_MEM;
    }

    const esp_err_t result = esp_console_cmd_register(&cmds[0]);
    if (result != ESP_OK) {
        vQueueDelete(cli_handle);
        cli_handle = NULL;
    }
    return result;
}
