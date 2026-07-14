#include <node/state_machine.h>

#include <string.h>

namespace node {

namespace {
constexpr uint32_t BROADCAST_ACK_SLOT_MS = 200;  // PROTOCOL.md §5: NodeID×200ms
}

void StateMachine::on_radio_bytes(const uint8_t* buf, size_t len, int8_t rssi) {
    efb::Packet p;
    if (efb::decode(buf, len, p) != efb::PacketErr::NONE) {
        ++err_cnt_;  // SEQ조차 못 믿으니 ACK를 보낼 수 없다 — 서버가 재전송한다
        return;
    }
    if (p.dst != node_id_ && p.dst != efb::BROADCAST) return;

    // 조회는 멱등 검사 대상이 아니다 — 같은 SEQ로 다시 물으면 최신값을 답한다.
    if (p.type == efb::PING || p.type == efb::STATUS_REQ) {
        reply_query(p, rssi);
        return;
    }

    // 재전송(동일 TYPE,SEQ)은 재적용 없이 ACK만 (PROTOCOL.md §5).
    if (has_last_handled_ && last_type_ == p.type && last_handled_seq_ == p.seq) {
        send_ack(p, efb::OK);
        return;
    }

    const uint8_t result = apply(p);
    if (result != efb::OK) {
        ++err_cnt_;
        send_ack(p, result);
        return;
    }

    // ★ 멱등 키를 렌더 "전에" 기록한다.
    //
    // 서버 T_ack=1500ms 인데 COMMIT 왕복은 전체갱신 기준 3.7초라 재전송이 반드시 온다.
    // 레퍼런스(simulator/node.py:65-69)는 키를 렌더가 끝난 뒤 찍어서, 렌더 도중 도착한
    // 재전송이 필터를 통과하고 e-Paper를 두 번 갱신시킨다(실측 확인). 순서를 뒤집으면
    // 서버도 문서도 건드리지 않고 여기서 막힌다.
    has_last_handled_ = true;
    last_type_ = p.type;
    last_handled_seq_ = p.seq;
    last_seq_ = p.seq;

    if (p.type == efb::COMMIT) {
        commit_staged();
        display_.render(committed_, p.payload[0]);  // 블로킹 — 이 동안 무선을 못 듣는다
    }
    send_ack(p, efb::OK);
}

uint8_t StateMachine::apply(const efb::Packet& p) {
    switch (p.type) {
        case efb::SET_TEMPLATE: {
            if (p.len < 1) return efb::BAD_TYPE;
            staged_.template_id = p.payload[0];
            staged_template_ = true;
            return efb::OK;
        }
        case efb::SET_FIELD: {
            if (p.len < 2) return efb::BAD_TYPE;
            const uint8_t field_id = p.payload[0];
            const uint8_t text_len = p.payload[1];
            if (field_id >= MAX_FIELDS) return efb::BAD_TYPE;
            if (text_len > MAX_TEXT_LEN) return efb::BAD_TYPE;
            if (static_cast<size_t>(2) + text_len > p.len) return efb::BAD_TYPE;
            memcpy(staged_.fields[field_id], p.payload + 2, text_len);
            staged_.fields[field_id][text_len] = '\0';
            staged_.has_field[field_id] = true;
            return efb::OK;
        }
        case efb::SET_QR: {
            if (p.len < 2) return efb::BAD_TYPE;
            const uint8_t url_len = p.payload[1];
            if (url_len > MAX_TEXT_LEN) return efb::BAD_TYPE;
            if (static_cast<size_t>(2) + url_len > p.len) return efb::BAD_TYPE;
            memcpy(staged_.qr_url, p.payload + 2, url_len);
            staged_.qr_url[url_len] = '\0';
            staged_.has_qr = true;
            staged_qr_ = true;
            return efb::OK;
        }
        case efb::COMMIT: {
            if (p.len < 1) return efb::BAD_TYPE;  // refresh_mode 없음
            return efb::OK;                       // 실제 반영은 on_radio_bytes 에서
        }
        default:
            return efb::BAD_TYPE;  // IMG_FRAG 등 미지원
    }
}

void StateMachine::commit_staged() {
    if (staged_template_) committed_.template_id = staged_.template_id;
    for (size_t i = 0; i < MAX_FIELDS; ++i) {
        if (!staged_.has_field[i]) continue;
        memcpy(committed_.fields[i], staged_.fields[i], MAX_TEXT_LEN + 1);
        committed_.has_field[i] = true;
    }
    if (staged_qr_) {
        memcpy(committed_.qr_url, staged_.qr_url, MAX_TEXT_LEN + 1);
        committed_.has_qr = true;
    }

    for (size_t i = 0; i < MAX_FIELDS; ++i) staged_.has_field[i] = false;
    staged_.has_qr = false;
    staged_template_ = false;
    staged_qr_ = false;
}

void StateMachine::send_ack(const efb::Packet& p, uint8_t result) {
    if (p.dst == efb::BROADCAST) {
        clock_.delay(node_id_ * BROADCAST_ACK_SLOT_MS);  // ACK 충돌 회피 (PROTOCOL.md §5)
    }
    uint8_t payload[2];
    const size_t n = efb::build_ack(p.seq, result, payload, sizeof(payload));
    send(p.src, efb::ACK, p.seq, payload, n);
}

void StateMachine::reply_query(const efb::Packet& p, int8_t rssi) {
    uint8_t payload[8];
    if (p.type == efb::PING) {
        const size_t n = efb::build_pong(battery_.read_mv(), rssi, 0, payload, sizeof(payload));
        send(p.src, efb::PONG, p.seq, payload, n);
    } else {
        const size_t n = efb::build_status_res(battery_.read_mv(), last_seq_, uptime_s(),
                                               err_cnt_, payload, sizeof(payload));
        send(p.src, efb::STATUS_RES, p.seq, payload, n);
    }
}

void StateMachine::send(uint8_t dst, uint8_t type, uint8_t seq, const uint8_t* payload,
                        size_t len) {
    efb::Packet r;
    r.src = node_id_;
    r.dst = dst;
    r.type = type;
    r.seq = seq;
    r.len = static_cast<uint8_t>(len);
    if (len) memcpy(r.payload, payload, len);

    uint8_t wire[efb::MAX_PACKET];
    const size_t n = efb::encode(r, wire, sizeof(wire));
    if (n) radio_.send(wire, n);
}

uint16_t StateMachine::uptime_s() const {
    return static_cast<uint16_t>(((clock_.millis() - boot_ms_) / 1000) & 0xFFFF);
}

}  // namespace node
