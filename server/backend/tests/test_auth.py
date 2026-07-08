from tests.conftest import TEST_PASSWORD


def test_login_with_correct_password_returns_token(client):
    res = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert res.status_code == 200
    assert len(res.json()["token"]) > 20


def test_login_with_wrong_password_401(client):
    assert client.post("/api/auth/login",
                       json={"password": "nope"}).status_code == 401
