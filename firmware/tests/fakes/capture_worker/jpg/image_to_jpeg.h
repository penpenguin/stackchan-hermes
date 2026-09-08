#pragma once
#include <cstdint>
#include <cstddef>
#include <esp_heap_caps.h>
using v4l2_pix_fmt_t=std::uint32_t;
using jpg_out_cb=std::size_t(*)(void*,std::size_t,const void*,std::size_t);
inline bool image_to_jpeg_cb(std::uint8_t*,std::size_t,std::uint16_t,std::uint16_t,v4l2_pix_fmt_t,std::uint8_t,jpg_out_cb callback,void* argument) {
    ++worker_fake::encodes;
    if(worker_fake::failEncoding) return false;
    const std::uint8_t jpeg[]={0xff,0xd8,0xff,0,0xff,0xd9};
    if(callback(argument,0,jpeg,sizeof(jpeg))!=sizeof(jpeg)) return false;
    callback(argument,sizeof(jpeg),nullptr,0); return true;
}
