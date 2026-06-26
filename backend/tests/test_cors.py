from fastapi.testclient import TestClient

from app.main import create_app


def test_cors_allows_configured_frontend_origin_with_credentials() -> None:
    client = TestClient(create_app())

    for origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
        response = client.options(
            "/api/v1/auth/me",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"
