#pragma once
#include <cstdlib>
#include <atomic>
constexpr int MALLOC_CAP_SPIRAM=1, MALLOC_CAP_8BIT=2;
namespace worker_fake { inline std::atomic<int> allocations{0}, encodes{0}, captures{0}; inline bool failEncoding=false, failAllocation=false; }
inline void* heap_caps_malloc(std::size_t size,int) { if(worker_fake::failAllocation) return nullptr; auto* value=std::malloc(size); if(value) ++worker_fake::allocations; return value; }
inline void heap_caps_free(void* value) { if(value) --worker_fake::allocations; std::free(value); }
