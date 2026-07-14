#include <string.h>
#include <unity.h>

#include <efb/cobs.h>

#include "../golden_vectors.h"

void setUp() {}
void tearDown() {}

namespace {

// 서버 cobs_encode 가 내보낸 바이트와 정확히 일치하고, 되돌리면 원본이어야 한다.
void check_case(const uint8_t* raw, size_t raw_len, const uint8_t* enc, size_t enc_len) {
    uint8_t out[efb::COBS_MAX_ENCODED];
    size_t n = efb::cobs_encode(raw, raw_len, out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(enc_len, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(enc, out, enc_len);

    uint8_t back[efb::COBS_MAX_ENCODED];
    size_t m = efb::cobs_decode(out, n, back, sizeof(back));
    TEST_ASSERT_NOT_EQUAL(efb::COBS_ERROR, m);
    TEST_ASSERT_EQUAL_size_t(raw_len, m);
    if (raw_len) TEST_ASSERT_EQUAL_UINT8_ARRAY(raw, back, raw_len);
}

}  // namespace

void test_matches_server_vectors() {
    check_case(golden::COBS_RAW_0, golden::COBS_RAW_0_LEN, golden::COBS_ENC_0,
               golden::COBS_ENC_0_LEN);
    check_case(golden::COBS_RAW_1, golden::COBS_RAW_1_LEN, golden::COBS_ENC_1,
               golden::COBS_ENC_1_LEN);
    check_case(golden::COBS_RAW_2, golden::COBS_RAW_2_LEN, golden::COBS_ENC_2,
               golden::COBS_ENC_2_LEN);
    check_case(golden::COBS_RAW_3, golden::COBS_RAW_3_LEN, golden::COBS_ENC_3,
               golden::COBS_ENC_3_LEN);
    check_case(golden::COBS_RAW_4, golden::COBS_RAW_4_LEN, golden::COBS_ENC_4,
               golden::COBS_ENC_4_LEN);
    check_case(golden::COBS_RAW_5, golden::COBS_RAW_5_LEN, golden::COBS_ENC_5,
               golden::COBS_ENC_5_LEN);  // 254 논제로 — 0xFF 블록 경계
    check_case(golden::COBS_RAW_6, golden::COBS_RAW_6_LEN, golden::COBS_ENC_6,
               golden::COBS_ENC_6_LEN);
}

// 인코딩 결과에는 0x00 이 없어야 한다 — 그래야 0x00 을 프레임 구분자로 쓸 수 있다.
void test_encoded_never_contains_zero() {
    uint8_t out[efb::COBS_MAX_ENCODED];
    size_t n = efb::cobs_encode(golden::COBS_RAW_6, golden::COBS_RAW_6_LEN, out, sizeof(out));
    TEST_ASSERT_GREATER_THAN_size_t(0, n);
    for (size_t i = 0; i < n; ++i) TEST_ASSERT_NOT_EQUAL_UINT8(0x00, out[i]);
}

void test_known_vector() {
    const uint8_t raw[] = {0x11, 0x22, 0x00, 0x33};
    const uint8_t want[] = {0x03, 0x11, 0x22, 0x02, 0x33};
    uint8_t out[16];
    size_t n = efb::cobs_encode(raw, sizeof(raw), out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(sizeof(want), n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(want, out, sizeof(want));
}

void test_decode_rejects_embedded_zero() {
    const uint8_t bad[] = {0x03, 0x11, 0x00};
    uint8_t out[16];
    TEST_ASSERT_EQUAL_size_t(efb::COBS_ERROR,
                             efb::cobs_decode(bad, sizeof(bad), out, sizeof(out)));
}

void test_decode_rejects_truncated_block() {
    const uint8_t bad[] = {0x05, 0x11, 0x22};
    uint8_t out[16];
    TEST_ASSERT_EQUAL_size_t(efb::COBS_ERROR,
                             efb::cobs_decode(bad, sizeof(bad), out, sizeof(out)));
}

// C++ 는 오버런하면 메모리를 밟는다 — 파이썬 레퍼런스에 없는 방어.
void test_encode_rejects_undersized_output() {
    const uint8_t raw[] = {0x11, 0x22, 0x33};
    uint8_t out[2];
    TEST_ASSERT_EQUAL_size_t(0, efb::cobs_encode(raw, sizeof(raw), out, sizeof(out)));
}

void test_decode_rejects_undersized_output() {
    const uint8_t enc[] = {0x04, 0x11, 0x22, 0x33};
    uint8_t out[2];
    TEST_ASSERT_EQUAL_size_t(efb::COBS_ERROR,
                             efb::cobs_decode(enc, sizeof(enc), out, sizeof(out)));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_matches_server_vectors);
    RUN_TEST(test_encoded_never_contains_zero);
    RUN_TEST(test_known_vector);
    RUN_TEST(test_decode_rejects_embedded_zero);
    RUN_TEST(test_decode_rejects_truncated_block);
    RUN_TEST(test_encode_rejects_undersized_output);
    RUN_TEST(test_decode_rejects_undersized_output);
    return UNITY_END();
}
