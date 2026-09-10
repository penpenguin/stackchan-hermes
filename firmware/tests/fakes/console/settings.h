#pragma once

#include <cassert>
#include <map>
#include <string>

class Settings {
public:
    Settings(const std::string& ns, bool writable = false) : ns_(ns) { assert(writable); }
    void SetString(const std::string& key, const std::string& value) { strings[{ns_, key}] = value; }
    void SetInt(const std::string& key, int value) { integers[{ns_, key}] = value; }
    void SetBool(const std::string& key, bool value) { SetInt(key, value); }
    static inline std::map<std::pair<std::string, std::string>, std::string> strings;
    static inline std::map<std::pair<std::string, std::string>, int> integers;
private:
    std::string ns_;
};
