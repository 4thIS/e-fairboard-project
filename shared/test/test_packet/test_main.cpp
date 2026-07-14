#include <string.h>
#include <unity.h>

#include <efb/packet.h>

#include "../golden_vectors.h"

void setUp() {}
void tearDown() {}

namespace {

// 서버 encode() 가 내보낸 와이어 바이트와 정확히 일치하고, decode 하면 원래 필드로 돌아와야 한다.
void check_case(uint8_t src, uint8_t dst, uint8_t type, uint8_t seq,
                const uint8_t* payload, size_t payload_len,
                const uint8_t* wire, size_t wire_len) {
    efb::Packet p;
    p.src = src;
    p.dst = dst;
    p.type = type;
    p.seq = seq;
    p.len = static_cast<uint8_t>(payload_len);
    if (payload_len) memcpy(p.payload, payload, payload_len);

    uint8_t out[efb::MAX_PACKET];
    size_t n = efb::encode(p, out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(wire_len, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(wire, out, wire_len);

    efb::Packet back;
    TEST_ASSERT_EQUAL(efb::PacketErr::NONE, efb::decode(wire, wire_len, back));
    TEST_ASSERT_EQUAL_HEX8(src, back.src);
    TEST_ASSERT_EQUAL_HEX8(dst, back.dst);
    TEST_ASSERT_EQUAL_HEX8(type, back.type);
    TEST_ASSERT_EQUAL_HEX8(seq, back.seq);
    TEST_ASSERT_EQUAL_HEX8(efb::VER, back.ver);
    TEST_ASSERT_EQUAL_HEX8(efb::FRAG_SINGLE, back.frag);
    TEST_ASSERT_EQUAL_size_t(payload_len, back.len);
    if (payload_len) TEST_ASSERT_EQUAL_UINT8_ARRAY(payload, back.payload, payload_len);
}

}  // namespace

#define CHECK(i)                                                                       \
    check_case(golden::PKT_SRC_##i, golden::PKT_DST_##i, golden::PKT_TYPE_##i,         \
               golden::PKT_SEQ_##i, golden::PKT_PAYLOAD_##i, golden::PKT_PAYLOAD_##i##_LEN, \
               golden::PKT_WIRE_##i, golden::PKT_WIRE_##i##_LEN)

void test_matches_server_wire_format() {
    CHECK(0);  // PING (페이로드 없음)
    CHECK(1);  // SET_TEMPLATE
    CHECK(2);  // SET_FIELD 한글 UTF-8
    CHECK(3);  // SET_QR
    CHECK(4);  // COMMIT 브로드캐스트, SEQ=0xFF
    CHECK(5);  // ACK BUSY
    CHECK(6);  // PONG
    CHECK(7);  // STATUS_RES
    CHECK(8);  // 페이로드 200B 한계
}

// PROTOCOL.md §2 필드 표: 헤더 7B (VER SRC DST TYPE SEQ FRAG LEN) + CRC16 LE.
// 같은 문서 본문의 "8B 헤더"는 오기 — 필드 표와 서버 구현이 정본.
void test_wire_layout_is_7byte_header() {
    efb::Packet p;
    p.src = 0x00;
    p.dst = 0x02;
    p.type = efb::SET_TEMPLATE;
    p.seq = 3;
    p.payload[0] = 0x01;
    p.len = 1;

    uint8_t out[efb::MAX_PACKET];
    size_t n = efb::encode(p, out, sizeof(out));

    TEST_ASSERT_EQUAL_size_t(7 + 1 + 2, n);
    TEST_ASSERT_EQUAL_HEX8(efb::VER, out[0]);
    TEST_ASSERT_EQUAL_HEX8(0x00, out[1]);
    TEST_ASSERT_EQUAL_HEX8(0x02, out[2]);
    TEST_ASSERT_EQUAL_HEX8(0x10, out[3]);
    TEST_ASSERT_EQUAL_HEX8(3, out[4]);
    TEST_ASSERT_EQUAL_HEX8(0x80, out[5]);
    TEST_ASSERT_EQUAL_HEX8(1, out[6]);
    TEST_ASSERT_EQUAL_HEX8(0x01, out[7]);
}

void test_corrupted_crc_rejected() {
    uint8_t wire[efb::MAX_PACKET];
    memcpy(wire, golden::PKT_WIRE_0, golden::PKT_WIRE_0_LEN);
    wire[golden::PKT_WIRE_0_LEN - 1] ^= 0xFF;

    efb::Packet p;
    TEST_ASSERT_EQUAL(efb::PacketErr::CRC, efb::decode(wire, golden::PKT_WIRE_0_LEN, p));
}

void test_short_buffer_rejected() {
    const uint8_t buf[] = {0x01, 0x00, 0x01};
    efb::Packet p;
    TEST_ASSERT_EQUAL(efb::PacketErr::TOO_SHORT, efb::decode(buf, sizeof(buf), p));
}

void test_len_mismatch_rejected() {
    uint8_t wire[efb::MAX_PACKET];
    memcpy(wire, golden::PKT_WIRE_1, golden::PKT_WIRE_1_LEN);
    efb::Packet p;
    // LEN 필드는 1인데 버퍼는 그대로 → 길이 불일치
    TEST_ASSERT_EQUAL(efb::PacketErr::LEN_MISMATCH,
                      efb::decode(wire, golden::PKT_WIRE_1_LEN - 1, p));
}

void test_unknown_type_rejected() {
    efb::Packet p;
    p.src = 0;
    p.dst = 1;
    p.type = 0x77;  // 미정의 TYPE
    p.seq = 0;
    p.len = 0;
    uint8_t out[efb::MAX_PACKET];
    size_t n = efb::encode(p, out, sizeof(out));
    TEST_ASSERT_GREATER_THAN_size_t(0, n);

    efb::Packet back;
    TEST_ASSERT_EQUAL(efb::PacketErr::UNKNOWN_TYPE, efb::decode(out, n, back));
}

void test_payload_over_200_rejected() {
    efb::Packet p;
    p.len = 201;
    uint8_t out[efb::MAX_PACKET + 8];
    TEST_ASSERT_EQUAL_size_t(0, efb::encode(p, out, sizeof(out)));
}

// ---- 페이로드 빌더/파서 (PROTOCOL.md §3.1 — 전부 little-endian) ----

void test_build_set_field_utf8() {
    uint8_t out[efb::MAX_PAYLOAD];
    size_t n = efb::build_set_field(2, "\xEB\xB6\x80\xEC\x8A\xA4", 6, out, sizeof(out));  // "부스"
    TEST_ASSERT_EQUAL_size_t(golden::PAYLOAD_SET_FIELD_KO_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PAYLOAD_SET_FIELD_KO, out, n);
}

void test_build_set_qr() {
    uint8_t out[efb::MAX_PAYLOAD];
    const char* url = "https://x.io/a";
    size_t n = efb::build_set_qr(0, url, strlen(url), out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(golden::PAYLOAD_SET_QR_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PAYLOAD_SET_QR, out, n);
}

void test_build_ack() {
    uint8_t out[8];
    size_t n = efb::build_ack(9, efb::BUSY, out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(golden::PAYLOAD_ACK_BUSY_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PAYLOAD_ACK_BUSY, out, n);
}

void test_build_pong_little_endian() {
    uint8_t out[8];
    size_t n = efb::build_pong(3900, -60, 0, out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(golden::PAYLOAD_PONG_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PAYLOAD_PONG, out, n);  // 3C 0F C4 00
}

void test_build_status_res_little_endian() {
    uint8_t out[8];
    size_t n = efb::build_status_res(3700, 5, 600, 1, out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(golden::PAYLOAD_STATUS_RES_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PAYLOAD_STATUS_RES, out, n);
}

void test_parse_ack_roundtrip() {
    uint8_t seq = 0;
    uint8_t result = 0;
    TEST_ASSERT_TRUE(efb::parse_ack(golden::PAYLOAD_ACK_BUSY, golden::PAYLOAD_ACK_BUSY_LEN,
                                    seq, result));
    TEST_ASSERT_EQUAL_HEX8(9, seq);
    TEST_ASSERT_EQUAL_HEX8(efb::BUSY, result);
}

// 파이썬은 짧은 페이로드에서 IndexError지만 C++는 버퍼 오버런이다 — 길이 검사 필수.
void test_parse_ack_rejects_short_payload() {
    const uint8_t short_payload[] = {0x09};
    uint8_t seq = 0;
    uint8_t result = 0;
    TEST_ASSERT_FALSE(efb::parse_ack(short_payload, sizeof(short_payload), seq, result));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_matches_server_wire_format);
    RUN_TEST(test_wire_layout_is_7byte_header);
    RUN_TEST(test_corrupted_crc_rejected);
    RUN_TEST(test_short_buffer_rejected);
    RUN_TEST(test_len_mismatch_rejected);
    RUN_TEST(test_unknown_type_rejected);
    RUN_TEST(test_payload_over_200_rejected);
    RUN_TEST(test_build_set_field_utf8);
    RUN_TEST(test_build_set_qr);
    RUN_TEST(test_build_ack);
    RUN_TEST(test_build_pong_little_endian);
    RUN_TEST(test_build_status_res_little_endian);
    RUN_TEST(test_parse_ack_roundtrip);
    RUN_TEST(test_parse_ack_rejects_short_payload);
    return UNITY_END();
}
