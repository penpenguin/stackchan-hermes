#pragma once
#include <stdint.h>
#include "linux/videodev2.h"
// Local extension of the locked Espressif video ioctl contract (ticks are finite).
struct stackchan_capture_buffer { struct v4l2_buffer buffer; uint32_t ticks; };
#define VIDIOC_CAPTURE_DQBUF _IOWR('V', BASE_VIDIOC_PRIVATE + 6, struct stackchan_capture_buffer)
