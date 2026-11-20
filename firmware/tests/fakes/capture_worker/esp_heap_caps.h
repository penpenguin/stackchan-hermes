#pragma once
#include <cstdlib>
#include <atomic>
constexpr int MALLOC_CAP_SPIRAM=1, MALLOC_CAP_8BIT=2;
namespace worker_fake { inline std::atomic<int> allocations{0}, encodes{0}, captures{0}; inline bool failEncoding=false, failAllocation=false; }
inline void* heap_caps_malloc(std::size_t size,int) { if(worker_fake::failAllocation) return nullptr; auto* value=std::malloc(size); if(value) ++worker_fake::allocations; return value; }
inline void heap_caps_free(void* value) { if(value) --worker_fake::allocations; std::free(value); }

constexpr int MALLOC_CAP_INTERNAL = 4;
struct multi_heap_info_t { std::size_t total_free_bytes, largest_free_block; };
inline void heap_caps_get_info(multi_heap_info_t* info, int caps)
{
    if (caps == (MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)) { *info = {20000, 10000}; }
    else if (caps == (MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)) { *info = {90000, 70000}; }
    else { std::abort(); }
}
