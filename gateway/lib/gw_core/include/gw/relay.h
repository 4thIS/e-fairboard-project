#pragma once

#include <efb/framing.h>
#include <efb/packet.h>
#include <efb/ports.h>

namespace gw {

// 서버(USB 시리얼, COBS 프레임) <-> LoRa 무선의 무상태 중계기.
//
// 재전송·ACK 대기·SEQ 발급은 전부 서버 LinkManager 소관이다. 게이트웨이는 아무것도 기억하지
// 않고 방향만 바꾼다. PROTOCOL.md §5의 "GW는 전송 후 ACK 대기" 문구는 서버 레퍼런스 구현
// (app/simulator/gateway.py)과 어긋나는데, 구현을 정본으로 따른다.
//
// 무선에는 COBS를 쓰지 않는다 — COBS는 시리얼 스트림 경계용이다 (PROTOCOL.md §7).
class Relay {
public:
    Relay(efb::ISerialOut& serial, efb::IRadioOut& radio) : serial_(serial), radio_(radio) {}

    // 서버 -> LoRa. UART가 경계를 안 지켜주므로 청크가 잘려도 재조립한다.
    void on_serial_bytes(const uint8_t* chunk, size_t len);

    // LoRa -> 서버. DST=0x00 인 패킷만 올린다. 나머지(노드간 트래픽·브로드캐스트)는 무시.
    void on_radio_bytes(const uint8_t* buf, size_t len);

    uint32_t dropped() const { return dropped_; }

private:
    efb::ISerialOut& serial_;
    efb::IRadioOut& radio_;
    efb::FrameAccumulator acc_;
    uint32_t dropped_ = 0;
};

}  // namespace gw
