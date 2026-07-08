from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    transport_mode: Literal["virtual", "serial"] = "virtual"
    serial_port: str = "COM3"
    admin_password: str = "changeme"

    # 링크 (PROTOCOL.md §5)
    ack_timeout_s: float = 1.5
    link_retries: int = 3

    # 시뮬레이터
    sim_airtime_s: float = 0.35
    sim_loss_rate: float = 0.0
    sim_refresh_partial_s: float = 1.0
    sim_refresh_full_s: float = 3.0

    # 모니터링·저장
    status_poll_interval_s: float = 15.0
    data_file: str = "data/state.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
