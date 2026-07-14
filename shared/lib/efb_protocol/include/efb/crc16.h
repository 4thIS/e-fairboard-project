#pragma once

#include <stddef.h>
#include <stdint.h>

namespace efb {

// CRC-16/CCITT-FALSE — PROTOCOL.md §2: poly=0x1021, init=0xFFFF, no reflect, xorout=0.
uint16_t crc16_ccitt(const uint8_t* data, size_t len);

}  // namespace efb
