from fastapi.testclient import TestClient

from app.main import create_app


def test_login_sets_session_cookie_and_returns_user() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "change-me-now"},
    )

    assert response.status_code == 200
    assert "aipaqu_session" in response.cookies
    assert response.json() == {
        "user": {
            "id": "dev-admin",
            "email": "admin@example.com",
            "role": "ADMIN",
            "workspaceId": "default",
        }
    }


def test_me_requires_authenticated_session() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_me_returns_current_user_after_login() -> None:
    client = TestClient(create_app())
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "change-me-now"},
    )

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "ADMIN"


def test_login_rejects_invalid_credentials() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_logout_clears_session() -> None:
    client = TestClient(create_app())
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "change-me-now"},
    )

    logout_response = client.post("/api/v1/auth/logout")
    me_response = client.get("/api/v1/auth/me")

    assert logout_response.status_code == 204
    assert me_response.status_code == 401

