#pragma once

#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace capture_log {
inline std::vector<std::string> lines;

inline bool contains(const std::string& line)
{
    return std::find(lines.begin(), lines.end(), line) != lines.end();
}

// Only the conversions used by Capture and supported by the ESP32-S3 nano formatter.
__attribute__((format(printf, 2, 3)))
inline void info(const char* tag, const char* format, ...)
{
    if (std::strcmp(tag, "Capture") != 0) { return; }
    std::string line;
    va_list args;
    va_start(args, format);
    for (const char* p = format; *p; ++p) {
        if (*p != '%') {
            line += *p;
            continue;
        }
        switch (*++p) {
        case 's': line += va_arg(args, const char*); break;
        case 'd': line += std::to_string(va_arg(args, int)); break;
        case 'u': line += std::to_string(va_arg(args, unsigned int)); break;
        default:
            std::fprintf(stderr, "Unsupported capture log conversion in %s\n", format);
            std::abort();
        }
    }
    va_end(args);
    lines.push_back(line);
}
} // namespace capture_log

#define ESP_LOGI(...) capture_log::info(__VA_ARGS__)
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGD(...) ((void)0)
