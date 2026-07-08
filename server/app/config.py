"""환경설정. 값은 lifespan 시점에 참조 — 테스트에서 monkeypatch 가능."""
import os
from pathlib import Path

SERIAL_PORT = os.getenv("EFB_SERIAL_PORT")            # 미설정 → 모의 GW
SERIAL_BAUD = int(os.getenv("EFB_SERIAL_BAUD", "921600"))
DATA_PATH = Path(os.getenv("EFB_DATA", "data/state.json"))
LINK_TIMEOUT = float(os.getenv("EFB_LINK_TIMEOUT", "6.0"))
