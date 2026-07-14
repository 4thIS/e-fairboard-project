#include <string.h>
#include <unity.h>

#include <efb/framing.h>

#include "../golden_vectors.h"

void setUp() {}
void tearDown() {}

// 프레임 = COBS(논리패킷) + 0x00 (PROTOCOL.md §7). 서버 encode_frame 과 바이트 일치해야 한다.
void test_encode_frame_matches_server() {
    uint8_t out[efb::MAX_FRAME];
    size_t n = efb::encode_frame(golden::PKT_WIRE_2, golden::PKT_WIRE_2_LEN, out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(golden::PKT_FRAME_2_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PKT_FRAME_2, out, n);
    TEST_ASSERT_EQUAL_HEX8(0x00, out[n - 1]);
    for (size_t i = 0; i + 1 < n; ++i) TEST_ASSERT_NOT_EQUAL_UINT8(0x00, out[i]);
}

void test_feed_single_complete_frame() {
    efb::FrameAccumulator acc;
    acc.feed(golden::PKT_FRAME_0, golden::PKT_FRAME_0_LEN);

    uint8_t out[efb::MAX_FRAME];
    size_t n = acc.next(out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(golden::PKT_WIRE_0_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PKT_WIRE_0, out, n);
    TEST_ASSERT_EQUAL_size_t(0, acc.next(out, sizeof(out)));
}

// UART는 프레임 경계를 지켜주지 않는다 — 청크가 잘려 들어와도 재조립돼야 한다.
void test_feed_split_across_chunks() {
    efb::FrameAccumulator acc;
    uint8_t out[efb::MAX_FRAME];

    acc.feed(golden::PKT_FRAME_2, 3);
    TEST_ASSERT_EQUAL_size_t(0, acc.next(out, sizeof(out)));

    acc.feed(golden::PKT_FRAME_2 + 3, golden::PKT_FRAME_2_LEN - 3);
    size_t n = acc.next(out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(golden::PKT_WIRE_2_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PKT_WIRE_2, out, n);
}

void test_feed_multiple_frames_in_one_chunk() {
    uint8_t chunk[efb::MAX_FRAME * 2];
    memcpy(chunk, golden::PKT_FRAME_0, golden::PKT_FRAME_0_LEN);
    memcpy(chunk + golden::PKT_FRAME_0_LEN, golden::PKT_FRAME_1, golden::PKT_FRAME_1_LEN);

    efb::FrameAccumulator acc;
    acc.feed(chunk, golden::PKT_FRAME_0_LEN + golden::PKT_FRAME_1_LEN);

    uint8_t out[efb::MAX_FRAME];
    size_t n = acc.next(out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(golden::PKT_WIRE_0_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PKT_WIRE_0, out, n);

    n = acc.next(out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(golden::PKT_WIRE_1_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PKT_WIRE_1, out, n);

    TEST_ASSERT_EQUAL_size_t(0, acc.next(out, sizeof(out)));
}

// 깨진 프레임은 폐기하고 스트림은 계속된다 — 최종 방어선은 상위 CRC.
void test_corrupt_frame_is_dropped_and_stream_continues() {
    const uint8_t bad[] = {0x05, 0x11, 0x22, 0x00};  // 잘린 COBS 블록 + 구분자
    efb::FrameAccumulator acc;
    acc.feed(bad, sizeof(bad));
    acc.feed(golden::PKT_FRAME_0, golden::PKT_FRAME_0_LEN);

    uint8_t out[efb::MAX_FRAME];
    size_t n = acc.next(out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(golden::PKT_WIRE_0_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PKT_WIRE_0, out, n);
}

void test_empty_frame_ignored() {
    const uint8_t zeros[] = {0x00, 0x00};
    efb::FrameAccumulator acc;
    acc.feed(zeros, sizeof(zeros));

    uint8_t out[efb::MAX_FRAME];
    TEST_ASSERT_EQUAL_size_t(0, acc.next(out, sizeof(out)));
}

// 구분자 없는 쓰레기가 계속 흘러들어와도 내부 버퍼가 넘치면 안 된다 (게이트웨이는 24/7 돈다).
//
// 쓰레기 직후의 프레임은 쓰레기와 한 덩어리라 복구 불가능하다 — 구분자가 없으니 경계를
// 알 방법이 없다. 서버가 재전송하므로 유실은 감수하고, 그 다음 프레임부터 되찾으면 된다.
void test_overlong_garbage_does_not_overflow() {
    efb::FrameAccumulator acc;
    uint8_t junk[64];
    memset(junk, 0xAA, sizeof(junk));
    for (int i = 0; i < 100; ++i) acc.feed(junk, sizeof(junk));  // 6400B, 구분자 없음

    acc.feed(golden::PKT_FRAME_0, golden::PKT_FRAME_0_LEN);  // 쓰레기에 붙어 유실
    acc.feed(golden::PKT_FRAME_1, golden::PKT_FRAME_1_LEN);  // 경계 회복 후 정상 수신

    uint8_t out[efb::MAX_FRAME];
    size_t n = acc.next(out, sizeof(out));
    TEST_ASSERT_EQUAL_size_t(golden::PKT_WIRE_1_LEN, n);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(golden::PKT_WIRE_1, out, n);
    TEST_ASSERT_EQUAL_size_t(0, acc.next(out, sizeof(out)));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_encode_frame_matches_server);
    RUN_TEST(test_feed_single_complete_frame);
    RUN_TEST(test_feed_split_across_chunks);
    RUN_TEST(test_feed_multiple_frames_in_one_chunk);
    RUN_TEST(test_corrupt_frame_is_dropped_and_stream_continues);
    RUN_TEST(test_empty_frame_ignored);
    RUN_TEST(test_overlong_garbage_does_not_overflow);
    return UNITY_END();
}
