#include <gw/relay.h>

namespace gw {

void Relay::on_serial_bytes(const uint8_t* chunk, size_t len) {
    acc_.feed(chunk, len);

    uint8_t wire[efb::MAX_PACKET];
    for (;;) {
        const size_t n = acc_.next(wire, sizeof(wire));
        if (n == 0) break;

        efb::Packet p;
        if (efb::decode(wire, n, p) != efb::PacketErr::NONE) {
            ++dropped_;  // 서버가 타임아웃으로 재전송한다
            continue;
        }
        radio_.send(wire, n);  // 논리 패킷 그대로 — 무선에 COBS 없음
    }
}

void Relay::on_radio_bytes(const uint8_t* buf, size_t len) {
    efb::Packet p;
    if (efb::decode(buf, len, p) != efb::PacketErr::NONE) {
        ++dropped_;
        return;
    }
    if (p.dst != efb::GATEWAY_ID) return;  // 우리 앞으로 온 게 아니다

    uint8_t frame[efb::MAX_FRAME];
    const size_t n = efb::encode_frame(buf, len, frame, sizeof(frame));
    if (n == 0) {
        ++dropped_;
        return;
    }
    serial_.write(frame, n);
}

}  // namespace gw
