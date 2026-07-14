#include <unity.h>

#include <efb/crc16.h>

#include "../golden_vectors.h"

void setUp() {}
void tearDown() {}

// 서버 crc16_ccitt 가 실제로 내보낸 값과 바이트 단위로 일치해야 한다.
void test_matches_server_vectors() {
    TEST_ASSERT_EQUAL_HEX16(golden::CRC_OUT_0,
                            efb::crc16_ccitt(golden::CRC_IN_0, golden::CRC_IN_0_LEN));
    TEST_ASSERT_EQUAL_HEX16(golden::CRC_OUT_1,
                            efb::crc16_ccitt(golden::CRC_IN_1, golden::CRC_IN_1_LEN));
    TEST_ASSERT_EQUAL_HEX16(golden::CRC_OUT_2,
                            efb::crc16_ccitt(golden::CRC_IN_2, golden::CRC_IN_2_LEN));
    TEST_ASSERT_EQUAL_HEX16(golden::CRC_OUT_3,
                            efb::crc16_ccitt(golden::CRC_IN_3, golden::CRC_IN_3_LEN));
}

// CRC-16/CCITT-FALSE 표준 체크값 (PROTOCOL.md §2)
void test_standard_check_value() {
    const uint8_t data[] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
    TEST_ASSERT_EQUAL_HEX16(0x29B1, efb::crc16_ccitt(data, sizeof(data)));
}

void test_empty_input_is_init_value() {
    TEST_ASSERT_EQUAL_HEX16(0xFFFF, efb::crc16_ccitt(nullptr, 0));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_matches_server_vectors);
    RUN_TEST(test_standard_check_value);
    RUN_TEST(test_empty_input_is_init_value);
    return UNITY_END();
}
