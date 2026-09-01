#pragma once

#include <stddef.h>
#include <stdint.h>

namespace efb {

// PROTOCOL.md §2 — 헤더 7B(VER SRC DST TYPE SEQ FRAG LEN) + PAYLOAD + CRC16(2B, LE).
// 같은 문서 본문의 "8B 헤더 + 2B CRC = 10B"는 필드 표·서버 구현과 어긋난다. 필드 표가 정본.
constexpr uint8_t VER = 0x01;
constexpr uint8_t GATEWAY_ID = 0x00;
constexpr uint8_t BROADCAST = 0xFF;
constexpr uint8_t FRAG_SINGLE = 0x80;  // bit7=LAST, 인덱스 0

constexpr size_t MAX_PAYLOAD = 200;
constexpr size_t HEADER_LEN = 7;
constexpr size_t CRC_LEN = 2;
constexpr size_t MAX_PACKET = HEADER_LEN + MAX_PAYLOAD + CRC_LEN;  // 209
constexpr size_t MAX_TEXT = MAX_PAYLOAD - 2;                       // SET_FIELD/SET_QR 본문 한도

enum MsgType : uint8_t {
    PING = 0x01,
    PONG = 0x02,
    SET_TEMPLATE = 0x10,
    SET_FIELD = 0x11,
    SET_QR = 0x12,
    COMMIT = 0x13,
    IMG_FRAG = 0x14,
    RESET = 0x15,  // 브로드캐스트 전체 초기화 — 노드는 대기 화면으로, ACK 없음 (PROTOCOL.md §5)
    ACK = 0x20,
    STATUS_REQ = 0x30,
    STATUS_RES = 0x31,
};

enum AckResult : uint8_t {
    OK = 0,
    CRC_FAIL = 1,
    BUSY = 2,
    BAD_TYPE = 3,
};

enum class PacketErr : uint8_t {
    NONE = 0,
    TOO_SHORT,
    LEN_MISMATCH,
    CRC,
    UNKNOWN_TYPE,
};

struct Packet {
    uint8_t ver = VER;
    uint8_t src = 0;
    uint8_t dst = 0;
    uint8_t type = 0;
    uint8_t seq = 0;
    uint8_t frag = FRAG_SINGLE;
    uint8_t len = 0;
    uint8_t payload[MAX_PAYLOAD] = {};
};

bool is_known_type(uint8_t type);

// 와이어 바이트 길이. len>200 이거나 out_cap 부족이면 0.
size_t encode(const Packet& p, uint8_t* out, size_t out_cap);
PacketErr decode(const uint8_t* buf, size_t len, Packet& out);

// ---- 페이로드 빌더 (PROTOCOL.md §3.1 — 멀티바이트는 전부 little-endian) ----
// 반환값은 페이로드 길이. 한도 초과나 out_cap 부족이면 0.

size_t build_set_field(uint8_t field_id, const char* text, size_t text_len, uint8_t* out,
                       size_t out_cap);
size_t build_set_qr(uint8_t qr_slot, const char* url, size_t url_len, uint8_t* out,
                    size_t out_cap);
size_t build_ack(uint8_t ack_seq, uint8_t result, uint8_t* out, size_t out_cap);
size_t build_pong(uint16_t batt_mv, int8_t rssi, uint8_t status, uint8_t* out, size_t out_cap);
size_t build_status_res(uint16_t batt_mv, uint8_t last_seq, uint16_t uptime_s, uint8_t err_cnt,
                        uint8_t* out, size_t out_cap);

// ---- 페이로드 파서 ----
// 길이가 모자라면 false. 파이썬 레퍼런스는 IndexError로 죽지만 C++는 밟으면 끝난다.

bool parse_ack(const uint8_t* payload, size_t len, uint8_t& ack_seq, uint8_t& result);
bool parse_pong(const uint8_t* payload, size_t len, uint16_t& batt_mv, int8_t& rssi,
                uint8_t& status);
bool parse_status_res(const uint8_t* payload, size_t len, uint16_t& batt_mv, uint8_t& last_seq,
                      uint16_t& uptime_s, uint8_t& err_cnt);

}  // namespace efb
