#pragma once

#include <efb/packet.h>
#include <efb/ports.h>

namespace node {

// 템플릿은 최대 4필드(PROTOCOL.md §8)지만 프로토콜 자체는 field_id 1바이트를 허용한다.
// 스펙이 늘어나도 버퍼를 밟지 않도록 여유를 두고, 범위를 넘는 field_id는 BAD_TYPE으로 거절한다.
constexpr size_t MAX_FIELDS = 8;
constexpr size_t MAX_TEXT_LEN = efb::MAX_TEXT;  // 198B — SET_FIELD/SET_QR 본문 한도

struct DisplayState {
    int16_t template_id = -1;  // -1 = 아직 없음
    bool has_field[MAX_FIELDS] = {};
    char fields[MAX_FIELDS][MAX_TEXT_LEN + 1] = {};
    bool has_qr = false;
    char qr_url[MAX_TEXT_LEN + 1] = {};
};

// e-Paper 갱신은 블로킹이다 — 이 호출이 도는 1~3초 동안 노드는 무선을 못 듣는다.
struct IDisplay {
    virtual ~IDisplay() = default;
    virtual void render(const DisplayState& s, uint8_t refresh_mode) = 0;
};

struct IBattery {
    virtual ~IBattery() = default;
    virtual uint16_t read_mv() = 0;
};

// 노드 상태머신 (PROTOCOL.md §4·§5, 서버 레퍼런스 app/simulator/node.py).
//
// SET_* 는 스테이징 버퍼에만 쌓이고 COMMIT 에서 한 번에 화면으로 넘어간다 — 깜빡임 1회.
class StateMachine {
public:
    StateMachine(uint8_t node_id, efb::IRadioOut& radio, efb::IClock& clock, IDisplay& display,
                 IBattery& battery)
        : node_id_(node_id), radio_(radio), clock_(clock), display_(display), battery_(battery),
          boot_ms_(clock.millis()) {}

    // 무선에서 받은 논리 패킷 바이트. rssi 는 그 패킷의 실측 수신 세기.
    void on_radio_bytes(const uint8_t* buf, size_t len, int8_t rssi);

    const DisplayState& display() const { return committed_; }
    uint8_t last_seq() const { return last_seq_; }
    uint8_t err_cnt() const { return err_cnt_; }

private:
    uint8_t apply(const efb::Packet& p);  // AckResult
    void commit_staged();
    void send_ack(const efb::Packet& p, uint8_t result);
    void reply_query(const efb::Packet& p, int8_t rssi);
    void send(uint8_t dst, uint8_t type, uint8_t seq, const uint8_t* payload, size_t len);
    uint16_t uptime_s() const;

    uint8_t node_id_;
    efb::IRadioOut& radio_;
    efb::IClock& clock_;
    IDisplay& display_;
    IBattery& battery_;
    uint32_t boot_ms_;

    DisplayState staged_;
    DisplayState committed_;
    bool staged_template_ = false;
    bool staged_qr_ = false;

    bool has_last_handled_ = false;
    uint8_t last_type_ = 0;
    uint8_t last_handled_seq_ = 0;
    uint8_t last_seq_ = 0;
    uint8_t err_cnt_ = 0;
};

}  // namespace node
