#pragma once

#include <cassert>
#include <cstdint>
#include <map>
#include <string>
#include <utility>

class Settings {
public:
    Settings(const std::string& ns, bool writable = false) : ns_(ns), writable_(writable) {}
    int32_t GetInt(const std::string& key, int32_t fallback = 0) {
        const auto found = values.find({ns_, key});
        return found == values.end() ? fallback : found->second;
    }
    bool GetBool(const std::string& key, bool fallback = false) { return GetInt(key, fallback); }
    void SetInt(const std::string& key, int32_t value) {
        assert(writable_);
        values[{ns_, key}] = value;
    }
    void SetBool(const std::string& key, bool value) { SetInt(key, value); }
    static inline std::map<std::pair<std::string, std::string>, int32_t> values;
private:
    std::string ns_;
    bool writable_;
};
