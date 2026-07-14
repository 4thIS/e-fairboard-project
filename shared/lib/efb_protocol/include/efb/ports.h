#pragma once

#include <stddef.h>
#include <stdint.h>

namespace efb {

// 코어 로직이 하드웨어를 보는 유일한 창. RadioLib·GxEPD2 헤더는 이 뒤에만 존재한다.
// 덕분에 코어는 맥에서 컴파일되고 테스트된다.

struct IRadioOut {
    virtual ~IRadioOut() = default;
    // 논리 패킷 바이트를 LoRa로 송신 (COBS 없음 — COBS는 시리얼 전용, PROTOCOL.md §7).
    virtual bool send(const uint8_t* data, size_t len) = 0;
};

struct ISerialOut {
    virtual ~ISerialOut() = default;
    virtual void write(const uint8_t* data, size_t len) = 0;
};

struct IClock {
    virtual ~IClock() = default;
    virtual uint32_t millis() = 0;
    virtual void delay(uint32_t ms) = 0;
};

}  // namespace efb
