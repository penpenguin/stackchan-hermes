#pragma once

#include <esp_heap_caps.h>
#include <esp_rom_sys.h>

namespace stackchan::hermes {

inline void logCaptureFailure(const char* stage, const char* reason, int code, unsigned stackBytes) noexcept
{
    multi_heap_info_t internal{}, psram{};
    heap_caps_get_info(&internal, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    heap_caps_get_info(&psram, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    esp_rom_printf("Capture: stage=%s reason=%s code=%d internal_free=%u internal_largest=%u "
                   "psram_free=%u psram_largest=%u stack_bytes=%u\n",
        stage, reason, code, static_cast<unsigned>(internal.total_free_bytes),
        static_cast<unsigned>(internal.largest_free_block), static_cast<unsigned>(psram.total_free_bytes),
        static_cast<unsigned>(psram.largest_free_block), stackBytes);
}

}  // namespace stackchan::hermes
