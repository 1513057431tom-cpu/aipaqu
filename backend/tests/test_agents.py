from fastapi.testclient import TestClient

from app.core.agents import DEFAULT_AGENT_PROMPTS
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


def test_admin_can_save_model_configuration_without_reading_api_key_back() -> None:
    client = TestClient(create_app())
    login(client)

    response = client.put(
        "/api/v1/model-configuration",
        json={
            "provider": "DEEPSEEK",
            "model": "deepseek-reasoner",
            "baseUrl": "https://api.deepseek.com",
            "apiKey": "sk-test-secret-1234",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "DEEPSEEK"
    assert body["model"] == "deepseek-reasoner"
    assert body["apiKeyConfigured"] is True
    assert body["apiKeyMasked"] == "********1234"
    assert "apiKey" not in body

    saved = client.get("/api/v1/model-configuration")
    assert saved.status_code == 200
    assert saved.json() == body


def test_admin_can_update_material_monitor_agent_configuration() -> None:
    client = TestClient(create_app())
    login(client)

    response = client.patch(
        "/api/v1/agents/material-monitor/configuration",
        json={
            "systemPrompt": "只根据可追溯证据分析物料变化，不得编造事实。",
            "defaultExecutionMode": "LIVE",
            "toolKeys": ["material_catalog", "evidence_store"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["systemPrompt"].startswith("只根据可追溯证据")
    assert body["defaultExecutionMode"] == "LIVE"
    assert body["toolKeys"] == ["material_catalog", "evidence_store"]

    saved = client.get("/api/v1/agents/material-monitor/configuration")
    assert saved.status_code == 200
    assert saved.json() == body


def test_default_agent_configurations_use_chinese_customer_copy() -> None:
    assert len(DEFAULT_AGENT_PROMPTS) == 5
    assert all("智能体" in prompt for prompt in DEFAULT_AGENT_PROMPTS.values())
    assert all(" Agent" not in prompt for prompt in DEFAULT_AGENT_PROMPTS.values())


def test_admin_can_manage_report_templates() -> None:
    client = TestClient(create_app())
    login(client)

    templates = client.get("/api/v1/report-templates")
    updated = client.put(
        "/api/v1/report-templates/DAILY",
        json={
            "name": "采购日报模板",
            "content": "# {{title}}\n\n## 物料情报\n{{material_intelligence}}\n\n{{evidence}}",
        },
    )

    assert templates.status_code == 200
    assert [item["period"] for item in templates.json()["data"]] == [
        "DAILY",
        "WEEKLY",
        "MONTHLY",
    ]
    assert updated.status_code == 200
    assert updated.json()["name"] == "采购日报模板"


def test_agent_configuration_rejects_unknown_tools() -> None:
    client = TestClient(create_app())
    login(client)

    response = client.patch(
        "/api/v1/agents/material-monitor/configuration",
        json={"toolKeys": ["shell_access"]},
    )

    assert response.status_code == 422
