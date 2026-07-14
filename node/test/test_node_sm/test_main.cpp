#include <string.h>
#include <unity.h>

#include <efb/packet.h>
#include <node/state_machine.h>

void setUp() {}
void tearDown() {}

namespace {

constexpr uint8_t NODE_ID = 0x01;

struct FakeRadio : efb::IRadioOut {
    efb::Packet sent[8];
    int count = 0;

    bool send(const uint8_t* data, size_t len) override {
        if (count < 8) efb::decode(data, len, sent[count]);
        ++count;
        return true;
    }
    const efb::Packet& last() const { return sent[count - 1]; }
};

struct FakeClock : efb::IClock {
    uint32_t now = 0;
    uint32_t delayed_total = 0;

    uint32_t millis() override { return now; }
    void delay(uint32_t ms) override {
        delayed_total += ms;
        now += ms;
    }
};

struct FakeBattery : node::IBattery {
    uint16_t mv = 4100;
    uint16_t read_mv() override { return mv; }
};

// e-Paper 갱신은 블로킹이다. render() 안에서 무엇이 일어나는지가 이중 갱신 버그의 핵심이라
// 재진입 훅을 열어둔다.
struct FakeDisplay : node::IDisplay {
    int render_count = 0;
    node::DisplayState last;
    uint8_t last_mode = 0xFF;
    node::StateMachine* reenter_sm = nullptr;  // 렌더 도중 도착할 패킷을 흉내낸다
    const uint8_t* reenter_buf = nullptr;
    size_t reenter_len = 0;

    void render(const node::DisplayState& s, uint8_t refresh_mode) override {
        ++render_count;
        last = s;
        last_mode = refresh_mode;
        if (reenter_sm && reenter_buf) {
            const uint8_t* buf = reenter_buf;
            const size_t len = reenter_len;
            reenter_buf = nullptr;  // 한 번만
            reenter_sm->on_radio_bytes(buf, len, -60);
        }
    }
};

struct Rig {
    FakeRadio radio;
    FakeClock clock;
    FakeBattery battery;
    FakeDisplay display;
    node::StateMachine sm{NODE_ID, radio, clock, display, battery};

    // 게이트웨이가 보낸 패킷을 노드에 밀어넣는다.
    void deliver(uint8_t type, uint8_t seq, const uint8_t* payload, size_t len,
                 uint8_t dst = NODE_ID) {
        efb::Packet p;
        p.src = efb::GATEWAY_ID;
        p.dst = dst;
        p.type = type;
        p.seq = seq;
        p.len = static_cast<uint8_t>(len);
        if (len) memcpy(p.payload, payload, len);

        uint8_t wire[efb::MAX_PACKET];
        const size_t n = efb::encode(p, wire, sizeof(wire));
        sm.on_radio_bytes(wire, n, -60);
    }

    size_t wire_of(uint8_t type, uint8_t seq, const uint8_t* payload, size_t len, uint8_t* out) {
        efb::Packet p;
        p.src = efb::GATEWAY_ID;
        p.dst = NODE_ID;
        p.type = type;
        p.seq = seq;
        p.len = static_cast<uint8_t>(len);
        if (len) memcpy(p.payload, payload, len);
        return efb::encode(p, out, efb::MAX_PACKET);
    }

    void expect_ack(uint8_t seq, uint8_t result) {
        TEST_ASSERT_EQUAL_HEX8(efb::ACK, radio.last().type);
        uint8_t ack_seq = 0;
        uint8_t res = 0xFF;
        TEST_ASSERT_TRUE(efb::parse_ack(radio.last().payload, radio.last().len, ack_seq, res));
        TEST_ASSERT_EQUAL_HEX8(seq, ack_seq);
        TEST_ASSERT_EQUAL_HEX8(result, res);
    }
};

size_t set_field(uint8_t id, const char* text, uint8_t* out) {
    return efb::build_set_field(id, text, strlen(text), out, efb::MAX_PAYLOAD);
}

}  // namespace

// SET_* 는 스테이징 버퍼에만 들어간다 — COMMIT 전에는 화면이 바뀌지 않는다.
// 이게 깜빡임을 1회로 묶어주는 장치다 (PROTOCOL.md §4).
void test_set_field_stages_but_does_not_render() {
    Rig r;
    uint8_t payload[efb::MAX_PAYLOAD];
    const size_t n = set_field(0, "\xEC\xA0\x9C\xEB\xAA\xA9", payload);  // "제목"

    r.deliver(efb::SET_FIELD, 1, payload, n);

    r.expect_ack(1, efb::OK);
    TEST_ASSERT_EQUAL_INT(0, r.display.render_count);
    TEST_ASSERT_FALSE(r.sm.display().has_field[0]);
}

void test_commit_applies_staged_state_and_renders_once() {
    Rig r;
    uint8_t payload[efb::MAX_PAYLOAD];

    const uint8_t tpl = 2;
    r.deliver(efb::SET_TEMPLATE, 1, &tpl, 1);
    size_t n = set_field(0, "\xEB\xAA\xA8\xEC\xA7\x91", payload);  // "모집"
    r.deliver(efb::SET_FIELD, 2, payload, n);
    n = efb::build_set_qr(0, "https://x.io", 12, payload, sizeof(payload));
    r.deliver(efb::SET_QR, 3, payload, n);

    TEST_ASSERT_EQUAL_INT(0, r.display.render_count);

    const uint8_t mode = 0;  // 부분 갱신
    r.deliver(efb::COMMIT, 4, &mode, 1);

    r.expect_ack(4, efb::OK);
    TEST_ASSERT_EQUAL_INT(1, r.display.render_count);
    TEST_ASSERT_EQUAL_UINT8(0, r.display.last_mode);

    const node::DisplayState& s = r.sm.display();
    TEST_ASSERT_EQUAL_INT(2, s.template_id);
    TEST_ASSERT_TRUE(s.has_field[0]);
    TEST_ASSERT_EQUAL_STRING("\xEB\xAA\xA8\xEC\xA7\x91", s.fields[0]);
    TEST_ASSERT_TRUE(s.has_qr);
    TEST_ASSERT_EQUAL_STRING("https://x.io", s.qr_url);
}

// 재전송(동일 TYPE,SEQ)은 재적용 없이 ACK만 — 멱등 (PROTOCOL.md §5).
void test_duplicate_seq_is_idempotent() {
    Rig r;
    uint8_t payload[efb::MAX_PAYLOAD];
    const size_t n = set_field(0, "A", payload);

    r.deliver(efb::SET_FIELD, 9, payload, n);
    r.deliver(efb::SET_FIELD, 9, payload, n);  // 재전송

    TEST_ASSERT_EQUAL_INT(2, r.radio.count);  // ACK는 두 번
    r.expect_ack(9, efb::OK);

    const uint8_t mode = 0;
    r.deliver(efb::COMMIT, 10, &mode, 1);
    TEST_ASSERT_EQUAL_STRING("A", r.sm.display().fields[0]);
}

// ★ 이중 갱신 방지 — 이 프로젝트에서 실제로 터진 버그다.
//
// 서버 T_ack=1500ms 인데 COMMIT 왕복은 전체갱신 기준 3.7초라 재전송이 반드시 온다.
// 서버 레퍼런스(simulator/node.py:65-69)는 멱등 키를 렌더가 "끝난 뒤" 기록해서, 렌더 도중
// 도착한 재전송이 필터를 통과하고 e-Paper를 두 번 갱신시켰다(실측 확인).
// 펌웨어는 키를 렌더 "전에" 기록한다 — 서버도 문서도 건드리지 않고 여기서 끝낸다.
void test_retransmit_during_render_does_not_render_twice() {
    Rig r;
    const uint8_t mode = 1;  // 전체 갱신 — 가장 오래 걸려 재전송을 확실히 부른다

    uint8_t retransmit[efb::MAX_PACKET];
    const size_t len = r.wire_of(efb::COMMIT, 7, &mode, 1, retransmit);

    // 렌더가 도는 도중에 동일 COMMIT 이 다시 도착하는 상황
    r.display.reenter_sm = &r.sm;
    r.display.reenter_buf = retransmit;
    r.display.reenter_len = len;

    r.deliver(efb::COMMIT, 7, &mode, 1);

    TEST_ASSERT_EQUAL_INT(1, r.display.render_count);  // e-Paper는 한 번만 갱신
    TEST_ASSERT_EQUAL_INT(2, r.radio.count);           // ACK는 두 번 (원본 + 재전송)
    r.expect_ack(7, efb::OK);
}

void test_ping_replies_pong_with_battery_and_rssi() {
    Rig r;
    r.battery.mv = 3900;

    r.deliver(efb::PING, 5, nullptr, 0);

    TEST_ASSERT_EQUAL_HEX8(efb::PONG, r.radio.last().type);
    uint16_t batt = 0;
    int8_t rssi = 0;
    uint8_t status = 0xFF;
    TEST_ASSERT_TRUE(efb::parse_pong(r.radio.last().payload, r.radio.last().len, batt, rssi,
                                     status));
    TEST_ASSERT_EQUAL_UINT16(3900, batt);
    TEST_ASSERT_EQUAL_INT8(-60, rssi);  // 수신 패킷의 실제 RSSI
    TEST_ASSERT_EQUAL_UINT8(0, status);
}

void test_status_req_reports_last_seq_and_uptime() {
    Rig r;
    r.battery.mv = 3700;
    const uint8_t tpl = 0;
    r.deliver(efb::SET_TEMPLATE, 11, &tpl, 1);
    r.clock.now = 600 * 1000;  // 10분

    r.deliver(efb::STATUS_REQ, 12, nullptr, 0);

    TEST_ASSERT_EQUAL_HEX8(efb::STATUS_RES, r.radio.last().type);
    uint16_t batt = 0;
    uint16_t uptime = 0;
    uint8_t last_seq = 0;
    uint8_t err = 0xFF;
    TEST_ASSERT_TRUE(efb::parse_status_res(r.radio.last().payload, r.radio.last().len, batt,
                                           last_seq, uptime, err));
    TEST_ASSERT_EQUAL_UINT16(3700, batt);
    TEST_ASSERT_EQUAL_UINT8(11, last_seq);
    TEST_ASSERT_EQUAL_UINT16(600, uptime);
    TEST_ASSERT_EQUAL_UINT8(0, err);
}

// PING/STATUS_REQ 는 멱등 검사 대상이 아니다 — 같은 SEQ로 다시 물어도 매번 최신값을 답한다.
void test_query_is_not_deduplicated() {
    Rig r;
    r.deliver(efb::PING, 5, nullptr, 0);
    r.battery.mv = 3500;
    r.deliver(efb::PING, 5, nullptr, 0);

    TEST_ASSERT_EQUAL_INT(2, r.radio.count);
    uint16_t batt = 0;
    int8_t rssi = 0;
    uint8_t status = 0;
    efb::parse_pong(r.radio.last().payload, r.radio.last().len, batt, rssi, status);
    TEST_ASSERT_EQUAL_UINT16(3500, batt);
}

void test_unsupported_type_acks_bad_type() {
    Rig r;
    const uint8_t junk = 0;
    r.deliver(efb::IMG_FRAG, 7, &junk, 1);  // 스트레치, MVP 미구현

    r.expect_ack(7, efb::BAD_TYPE);
    TEST_ASSERT_EQUAL_INT(0, r.display.render_count);
}

// 레퍼런스는 payload[0] 을 길이 검사 없이 읽는다 — 파이썬은 IndexError, C++는 버퍼 오버런.
void test_truncated_payload_acks_bad_type() {
    Rig r;
    r.deliver(efb::COMMIT, 3, nullptr, 0);  // refresh_mode 없는 COMMIT

    r.expect_ack(3, efb::BAD_TYPE);
    TEST_ASSERT_EQUAL_INT(0, r.display.render_count);
}

// 브로드캐스트 ACK는 NodeID×200ms 슬롯에 흘려 충돌을 피한다 (PROTOCOL.md §5).
void test_broadcast_ack_uses_node_slot() {
    Rig r;
    const uint8_t tpl = 1;
    r.deliver(efb::SET_TEMPLATE, 1, &tpl, 1, efb::BROADCAST);

    r.expect_ack(1, efb::OK);
    TEST_ASSERT_EQUAL_UINT32(NODE_ID * 200, r.clock.delayed_total);
}

void test_unicast_ack_has_no_slot_delay() {
    Rig r;
    const uint8_t tpl = 1;
    r.deliver(efb::SET_TEMPLATE, 1, &tpl, 1);

    TEST_ASSERT_EQUAL_UINT32(0, r.clock.delayed_total);
}

void test_packet_for_other_node_is_ignored() {
    Rig r;
    const uint8_t tpl = 1;
    r.deliver(efb::SET_TEMPLATE, 1, &tpl, 1, 0x02);  // 노드2 앞으로

    TEST_ASSERT_EQUAL_INT(0, r.radio.count);
}

// CRC가 깨진 패킷은 SEQ조차 믿을 수 없다 — ACK를 못 보낸다. 서버가 타임아웃으로 재전송한다.
void test_corrupt_packet_is_silent_but_counted() {
    Rig r;
    uint8_t wire[efb::MAX_PACKET];
    const uint8_t tpl = 1;
    const size_t n = r.wire_of(efb::SET_TEMPLATE, 1, &tpl, 1, wire);
    wire[n - 1] ^= 0xFF;

    r.sm.on_radio_bytes(wire, n, -60);

    TEST_ASSERT_EQUAL_INT(0, r.radio.count);
    TEST_ASSERT_EQUAL_UINT8(1, r.sm.err_cnt());
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_set_field_stages_but_does_not_render);
    RUN_TEST(test_commit_applies_staged_state_and_renders_once);
    RUN_TEST(test_duplicate_seq_is_idempotent);
    RUN_TEST(test_retransmit_during_render_does_not_render_twice);
    RUN_TEST(test_ping_replies_pong_with_battery_and_rssi);
    RUN_TEST(test_status_req_reports_last_seq_and_uptime);
    RUN_TEST(test_query_is_not_deduplicated);
    RUN_TEST(test_unsupported_type_acks_bad_type);
    RUN_TEST(test_truncated_payload_acks_bad_type);
    RUN_TEST(test_broadcast_ack_uses_node_slot);
    RUN_TEST(test_unicast_ack_has_no_slot_delay);
    RUN_TEST(test_packet_for_other_node_is_ignored);
    RUN_TEST(test_corrupt_packet_is_silent_but_counted);
    return UNITY_END();
}
