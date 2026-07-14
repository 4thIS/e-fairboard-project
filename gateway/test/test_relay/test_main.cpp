#include <string.h>
#include <unity.h>

#include <efb/framing.h>
#include <efb/packet.h>
#include <gw/relay.h>

void setUp() {}
void tearDown() {}

namespace {

struct FakeRadio : efb::IRadioOut {
    uint8_t last[efb::MAX_PACKET] = {};
    size_t last_len = 0;
    int sends = 0;

    bool send(const uint8_t* data, size_t len) override {
        memcpy(last, data, len);
        last_len = len;
        ++sends;
        return true;
    }
};

struct FakeSerial : efb::ISerialOut {
    uint8_t last[efb::MAX_FRAME] = {};
    size_t last_len = 0;
    int writes = 0;

    void write(const uint8_t* data, size_t len) override {
        memcpy(last, data, len);
        last_len = len;
        ++writes;
    }
};

efb::Packet make(uint8_t src, uint8_t dst, uint8_t type, uint8_t seq) {
    efb::Packet p;
    p.src = src;
    p.dst = dst;
    p.type = type;
    p.seq = seq;
    return p;
}

}  // namespace

// 서버 -> LoRa: 시리얼 COBS 프레임을 논리 패킷으로 풀어 무선으로 그대로 내보낸다.
void test_serial_frame_goes_out_on_radio() {
    FakeRadio radio;
    FakeSerial serial;
    gw::Relay relay(serial, radio);

    const efb::Packet ping = make(efb::GATEWAY_ID, 0x01, efb::PING, 7);
    uint8_t wire[efb::MAX_PACKET];
    const size_t wire_len = efb::encode(ping, wire, sizeof(wire));
    uint8_t frame[efb::MAX_FRAME];
    const size_t frame_len = efb::encode_frame(wire, wire_len, frame, sizeof(frame));

    relay.on_serial_bytes(frame, frame_len);

    TEST_ASSERT_EQUAL_INT(1, radio.sends);
    TEST_ASSERT_EQUAL_size_t(wire_len, radio.last_len);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(wire, radio.last, wire_len);  // 무선에는 COBS 없음
}

// UART는 경계를 안 지켜준다 — 반씩 끊어 들어와도 재조립돼야 한다.
void test_serial_frame_split_across_reads() {
    FakeRadio radio;
    FakeSerial serial;
    gw::Relay relay(serial, radio);

    const efb::Packet p = make(efb::GATEWAY_ID, 0x02, efb::COMMIT, 3);
    uint8_t wire[efb::MAX_PACKET];
    const size_t wire_len = efb::encode(p, wire, sizeof(wire));
    uint8_t frame[efb::MAX_FRAME];
    const size_t frame_len = efb::encode_frame(wire, wire_len, frame, sizeof(frame));

    relay.on_serial_bytes(frame, 2);
    TEST_ASSERT_EQUAL_INT(0, radio.sends);

    relay.on_serial_bytes(frame + 2, frame_len - 2);
    TEST_ASSERT_EQUAL_INT(1, radio.sends);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(wire, radio.last, wire_len);
}

// LoRa -> 서버: DST=0x00 인 패킷만 COBS 프레임으로 감싸 시리얼로 올린다.
void test_radio_packet_for_gateway_goes_up_serial() {
    FakeRadio radio;
    FakeSerial serial;
    gw::Relay relay(serial, radio);

    const efb::Packet ack = make(0x01, efb::GATEWAY_ID, efb::ACK, 7);
    uint8_t wire[efb::MAX_PACKET];
    const size_t wire_len = efb::encode(ack, wire, sizeof(wire));

    relay.on_radio_bytes(wire, wire_len);

    TEST_ASSERT_EQUAL_INT(1, serial.writes);
    uint8_t want[efb::MAX_FRAME];
    const size_t want_len = efb::encode_frame(wire, wire_len, want, sizeof(want));
    TEST_ASSERT_EQUAL_size_t(want_len, serial.last_len);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(want, serial.last, want_len);
}

// 노드끼리의 트래픽이나 브로드캐스트는 서버로 올리지 않는다 (레퍼런스 gateway.py:42).
void test_radio_packet_for_other_node_is_ignored() {
    FakeRadio radio;
    FakeSerial serial;
    gw::Relay relay(serial, radio);

    const efb::Packet p = make(0x01, 0x02, efb::PING, 1);
    uint8_t wire[efb::MAX_PACKET];
    const size_t wire_len = efb::encode(p, wire, sizeof(wire));

    relay.on_radio_bytes(wire, wire_len);
    TEST_ASSERT_EQUAL_INT(0, serial.writes);
}

// 깨진 무선 패킷은 폐기 — 서버가 타임아웃으로 재전송한다.
void test_corrupt_radio_packet_dropped() {
    FakeRadio radio;
    FakeSerial serial;
    gw::Relay relay(serial, radio);

    const efb::Packet ack = make(0x01, efb::GATEWAY_ID, efb::ACK, 7);
    uint8_t wire[efb::MAX_PACKET];
    const size_t wire_len = efb::encode(ack, wire, sizeof(wire));
    wire[wire_len - 1] ^= 0xFF;  // CRC 깨뜨림

    relay.on_radio_bytes(wire, wire_len);
    TEST_ASSERT_EQUAL_INT(0, serial.writes);
    TEST_ASSERT_EQUAL_UINT32(1, relay.dropped());
}

// 깨진 시리얼 프레임도 폐기하고 스트림은 계속된다.
void test_corrupt_serial_frame_dropped_stream_continues() {
    FakeRadio radio;
    FakeSerial serial;
    gw::Relay relay(serial, radio);

    const uint8_t garbage[] = {0x05, 0x11, 0x22, 0x00};
    relay.on_serial_bytes(garbage, sizeof(garbage));
    TEST_ASSERT_EQUAL_INT(0, radio.sends);

    const efb::Packet ping = make(efb::GATEWAY_ID, 0x01, efb::PING, 9);
    uint8_t wire[efb::MAX_PACKET];
    const size_t wire_len = efb::encode(ping, wire, sizeof(wire));
    uint8_t frame[efb::MAX_FRAME];
    const size_t frame_len = efb::encode_frame(wire, wire_len, frame, sizeof(frame));

    relay.on_serial_bytes(frame, frame_len);
    TEST_ASSERT_EQUAL_INT(1, radio.sends);
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_serial_frame_goes_out_on_radio);
    RUN_TEST(test_serial_frame_split_across_reads);
    RUN_TEST(test_radio_packet_for_gateway_goes_up_serial);
    RUN_TEST(test_radio_packet_for_other_node_is_ignored);
    RUN_TEST(test_corrupt_radio_packet_dropped);
    RUN_TEST(test_corrupt_serial_frame_dropped_stream_continues);
    return UNITY_END();
}
