#include <efb/packet.h>

#include <string.h>

#include <efb/crc16.h>

namespace efb {

namespace {

void put_u16_le(uint8_t* p, uint16_t v) {
    p[0] = static_cast<uint8_t>(v & 0xFF);
    p[1] = static_cast<uint8_t>(v >> 8);
}

uint16_t get_u16_le(const uint8_t* p) {
    return static_cast<uint16_t>(p[0] | (static_cast<uint16_t>(p[1]) << 8));
}

}  // namespace

bool is_known_type(uint8_t type) {
    switch (type) {
        case PING:
        case PONG:
        case SET_TEMPLATE:
        case SET_FIELD:
        case SET_QR:
        case COMMIT:
        case IMG_FRAG:
        case RESET:
        case ACK:
        case STATUS_REQ:
        case STATUS_RES:
            return true;
        default:
            return false;
    }
}

size_t encode(const Packet& p, uint8_t* out, size_t out_cap) {
    if (p.len > MAX_PAYLOAD) return 0;
    const size_t total = HEADER_LEN + p.len + CRC_LEN;
    if (out_cap < total) return 0;

    out[0] = p.ver;
    out[1] = p.src;
    out[2] = p.dst;
    out[3] = p.type;
    out[4] = p.seq;
    out[5] = p.frag;
    out[6] = p.len;
    if (p.len) memcpy(out + HEADER_LEN, p.payload, p.len);

    const uint16_t crc = crc16_ccitt(out, HEADER_LEN + p.len);  // CRC 대상 = VER..PAYLOAD
    put_u16_le(out + HEADER_LEN + p.len, crc);
    return total;
}

PacketErr decode(const uint8_t* buf, size_t len, Packet& out) {
    if (len < HEADER_LEN + CRC_LEN) return PacketErr::TOO_SHORT;

    const uint8_t payload_len = buf[6];
    if (len != HEADER_LEN + static_cast<size_t>(payload_len) + CRC_LEN) {
        return PacketErr::LEN_MISMATCH;
    }

    const size_t body_len = HEADER_LEN + payload_len;
    if (crc16_ccitt(buf, body_len) != get_u16_le(buf + body_len)) return PacketErr::CRC;
    if (!is_known_type(buf[3])) return PacketErr::UNKNOWN_TYPE;

    out.ver = buf[0];
    out.src = buf[1];
    out.dst = buf[2];
    out.type = buf[3];
    out.seq = buf[4];
    out.frag = buf[5];
    out.len = payload_len;
    if (payload_len) memcpy(out.payload, buf + HEADER_LEN, payload_len);
    return PacketErr::NONE;
}

size_t build_set_field(uint8_t field_id, const char* text, size_t text_len, uint8_t* out,
                       size_t out_cap) {
    if (text_len > MAX_TEXT || out_cap < text_len + 2) return 0;
    out[0] = field_id;
    out[1] = static_cast<uint8_t>(text_len);
    if (text_len) memcpy(out + 2, text, text_len);
    return text_len + 2;
}

size_t build_set_qr(uint8_t qr_slot, const char* url, size_t url_len, uint8_t* out,
                    size_t out_cap) {
    if (url_len > MAX_TEXT || out_cap < url_len + 2) return 0;
    out[0] = qr_slot;
    out[1] = static_cast<uint8_t>(url_len);
    if (url_len) memcpy(out + 2, url, url_len);
    return url_len + 2;
}

size_t build_ack(uint8_t ack_seq, uint8_t result, uint8_t* out, size_t out_cap) {
    if (out_cap < 2) return 0;
    out[0] = ack_seq;
    out[1] = result;
    return 2;
}

size_t build_pong(uint16_t batt_mv, int8_t rssi, uint8_t status, uint8_t* out, size_t out_cap) {
    if (out_cap < 4) return 0;
    put_u16_le(out, batt_mv);
    out[2] = static_cast<uint8_t>(rssi);
    out[3] = status;
    return 4;
}

size_t build_status_res(uint16_t batt_mv, uint8_t last_seq, uint16_t uptime_s, uint8_t err_cnt,
                        uint8_t* out, size_t out_cap) {
    if (out_cap < 6) return 0;
    put_u16_le(out, batt_mv);
    out[2] = last_seq;
    put_u16_le(out + 3, uptime_s);
    out[5] = err_cnt;
    return 6;
}

bool parse_ack(const uint8_t* payload, size_t len, uint8_t& ack_seq, uint8_t& result) {
    if (len < 2) return false;
    ack_seq = payload[0];
    result = payload[1];
    return true;
}

bool parse_pong(const uint8_t* payload, size_t len, uint16_t& batt_mv, int8_t& rssi,
                uint8_t& status) {
    if (len < 4) return false;
    batt_mv = get_u16_le(payload);
    rssi = static_cast<int8_t>(payload[2]);
    status = payload[3];
    return true;
}

bool parse_status_res(const uint8_t* payload, size_t len, uint16_t& batt_mv, uint8_t& last_seq,
                      uint16_t& uptime_s, uint8_t& err_cnt) {
    if (len < 6) return false;
    batt_mv = get_u16_le(payload);
    last_seq = payload[2];
    uptime_s = get_u16_le(payload + 3);
    err_cnt = payload[5];
    return true;
}

}  // namespace efb
