import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_PASSWORD = "test-pass"


def make_settings(tmp_path, **over) -> Settings:
    # link_retries=12: 손실 30% 테스트는 명령·ACK 양방향 손실이라 시도당
    # 성공률이 0.49로 떨어짐 → 재시도 여유 필요. 운영 기본은 스펙값 3.
    return Settings(_env_file=None, admin_password=TEST_PASSWORD,
                    transport_mode="virtual", sim_airtime_s=0.0,
                    ack_timeout_s=0.05, link_retries=12,
                    sim_refresh_partial_s=0.0, sim_refresh_full_s=0.0,
                    status_poll_interval_s=3600.0,
                    data_file=str(tmp_path / "state.json"), **over)


@pytest.fixture
def client(tmp_path):
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    token = client.post("/api/auth/login",
                        json={"password": TEST_PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}
