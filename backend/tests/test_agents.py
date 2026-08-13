from fastapi.testclient import TestClient

from app.main import create_app


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "change-me-now"},
    )
    assert response.status_code == 200


def test_deepseek_agent_definition_is_visible_without_exposing_credentials() -> None:
    client = TestClient(create_app())
    login(client)

    response = client.get("/api/v1/agents")

    assert response.status_code == 200
    agent = response.json()["data"][0]
    assert agent["key"] == "material-monitor"
    assert agent["provider"] == "DEEPSEEK"
    assert agent["model"] == "deepseek-chat"
    assert "apiKey" not in agent


def test_material_monitor_test_run_executes_graph_and_records_nodes() -> None:
    client = TestClient(create_app())
    login(client)

    response = client.post(
        "/api/v1/agents/material-monitor/runs",
        json={"executionMode": "TEST", "materialIds": []},
    )

    assert response.status_code == 202
    run = response.json()
    assert run["status"] == "COMPLETED"
    assert run["executionMode"] == "TEST"
    assert run["modelInvoked"] is False
    assert [step["key"] for step in run["steps"]] == [
        "load_scope",
        "collect_evidence",
        "analyze_changes",
        "prepare_outputs",
    ]
    assert all(step["status"] == "COMPLETED" for step in run["steps"])

    runs = client.get("/api/v1/agent-runs")
    assert runs.status_code == 200
    assert runs.json()["data"][0]["id"] == run["id"]


def test_live_run_requires_deepseek_configuration() -> None:
    client = TestClient(create_app())
    login(client)

    response = client.post(
        "/api/v1/agents/material-monitor/runs",
        json={"executionMode": "LIVE", "materialIds": []},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MODEL_NOT_CONFIGURED"
