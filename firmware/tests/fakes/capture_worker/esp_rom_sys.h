#pragma once

#include <cstdarg>
#include <cstdio>

namespace worker_fake {
inline char diagnostic[384] = {};
}

inline int esp_rom_printf(const char* format, ...) __attribute__((format(printf, 1, 2)));
inline int esp_rom_printf(const char* format, ...)
{
    va_list args;
    va_start(args, format);
    const int count = std::vsnprintf(worker_fake::diagnostic, sizeof(worker_fake::diagnostic), format, args);
    va_end(args);
    return count;
}
