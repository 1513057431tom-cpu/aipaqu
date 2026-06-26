from fastapi.testclient import TestClient

from app.main import create_app


def test_live_health_returns_service_identity() -> None:
    client = TestClient(create_app())

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Aipaqu API",
        "version": "0.1.0",
    }


def test_ready_health_reports_unchecked_dependencies() -> None:
    client = TestClient(create_app())

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "dependencies": {
            "mysql": "not_checked",
            "redis": "not_checked",
            "elasticsearch": "not_checked",
        },
    }

