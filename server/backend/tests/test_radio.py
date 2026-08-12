"""무선 셋업 — e22 순수 로직 골든벡터 + fake-serial 라우터 분기."""
import pytest

from app.radio import e22
from app.routers import radio

GOLDEN = bytes.fromhex("000000" "62E0" "12" "43" "0000")  # 실측 공장기본 ch18=868


# ---- e22.py 순수 로직 (하드웨어 무관) ----

def test_channel_mhz_roundtrip():
    assert e22.channel_to_mhz(18) == 868
    assert e22.channel_to_mhz(72) == 922
    assert e22.mhz_to_channel(922) == 72
    assert e22.mhz_to_channel(868) == 18


def test_decode_golden_vector():
    d = e22.decode_registers(GOLDEN)
    assert d["channel"] == 18 and d["freq_mhz"] == 868
    assert d["uart_bps"] == 9600 and d["air_bps"] == 2400
    assert d["power_dbm"] == 22
    assert d["address"] == 0 and d["netid"] == 0


def test_write_changes_only_channel():
    cmd = e22.build_write_cmd(GOLDEN, 922)
    assert cmd[:3] == bytes([0xC0, 0x00, 0x09])
    reg = cmd[3:]
    assert reg[e22._CH] == 72                    # 채널만 922로
    assert reg[:e22._CH] == GOLDEN[:e22._CH]      # 앞부분 보존
    assert reg[e22._CH + 1:] == GOLDEN[e22._CH + 1:]  # 뒷부분 보존


def test_build_write_cmd_rejects_bad_length():
    with pytest.raises(ValueError):
        e22.build_write_cmd(b"\x00" * 8, 922)


def test_kr920_band():
    assert not e22.in_kr920(868)
    assert e22.in_kr920(922)


# ---- fake-serial 라우터 분기 ----

class FakeSerial:
    """C1 읽기/C0 쓰기에 반응하는 가짜 HAT. config_mode=False 면 무응답."""

    def __init__(self, regs=GOLDEN, config_mode=True):
        self.regs = bytearray(regs)
        self.config_mode = config_mode
        self._out = bytearray()

    def reset_input_buffer(self):
        self._out.clear()

    def flush(self):
        pass

    def write(self, data):
        if not self.config_mode:
            return
        if data[:1] == b"\xC1":                       # 읽기
            self._out += bytes([0xC1, 0x00, 0x09]) + bytes(self.regs)
        elif data[:1] == b"\xC0":                     # 쓰기 (C0 00 09 + 9B)
            self.regs = bytearray(data[3:12])
            self._out += bytes(data)                  # 에코

    def read(self, n):
        chunk, self._out = self._out[:n], self._out[n:]
        return bytes(chunk)

    def close(self):
        pass


def test_read_config_mode(monkeypatch):
    monkeypatch.setattr(radio, "_open", lambda port: FakeSerial())
    out = radio.read_registers(radio.PortReq(port="COMX"))
    assert out["ok"] and out["registers"]["freq_mhz"] == 868


def test_read_not_config_mode_returns_hint(monkeypatch):
    monkeypatch.setattr(radio, "_open", lambda port: FakeSerial(config_mode=False))
    out = radio.read_registers(radio.PortReq(port="COMX"))
    assert out["ok"] is False and "M1" in out["hint"]


def test_frequency_writes_and_verifies(monkeypatch):
    fake = FakeSerial()
    monkeypatch.setattr(radio, "_open", lambda port: fake)
    monkeypatch.setattr(radio.time, "sleep", lambda s: None)
    out = radio.set_frequency(radio.FreqReq(port="COMX", mhz=922))
    assert out["ok"] is True
    assert out["before"]["freq_mhz"] == 868
    assert out["after"]["freq_mhz"] == 922
    assert out["warn"] is None  # 922 는 KR920 안


def test_frequency_out_of_range_422(monkeypatch):
    monkeypatch.setattr(radio, "_open", lambda port: FakeSerial())
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        radio.set_frequency(radio.FreqReq(port="COMX", mhz=700))
    assert exc.value.status_code == 422


def test_frequency_warns_outside_kr920(monkeypatch):
    monkeypatch.setattr(radio, "_open", lambda port: FakeSerial())
    monkeypatch.setattr(radio.time, "sleep", lambda s: None)
    out = radio.set_frequency(radio.FreqReq(port="COMX", mhz=915))
    assert out["ok"] is True and out["warn"] is not None
