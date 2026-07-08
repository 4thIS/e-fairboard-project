from app.config import Settings, get_settings


def test_defaults_are_virtual_mode():
    s = Settings(_env_file=None)
    assert s.transport_mode == "virtual"
    assert s.ack_timeout_s == 1.5
    assert s.link_retries == 3


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
