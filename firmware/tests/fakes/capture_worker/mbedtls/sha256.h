#pragma once
#include <cstring>
inline int mbedtls_sha256(const unsigned char*,std::size_t,unsigned char* out,int) { std::memset(out,0,32); return 0; }
