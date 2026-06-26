from fastapi.testclient import TestClient

from app.main import create_app


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "change-me-now"},
    )
    assert response.status_code == 200


def test_list_briefs_requires_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/briefs")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_create_brief_returns_workspace_scoped_draft() -> None:
    client = TestClient(create_app())
    login(client)

    response = client.post(
        "/api/v1/briefs",
        json={
            "title": "新能源汽车行业周报",
            "objective": "分析价格、销量、政策和重点企业动态",
            "requiredQuestions": ["本周市场最重要的变化是什么？"],
            "dateRange": {
                "kind": "WEEK",
                "referenceDate": "2026-06-26",
                "timezone": "Asia/Shanghai",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "新能源汽车行业周报"
    assert body["status"] == "DRAFT"
    assert body["workspaceId"] == "default"
    assert body["dateRange"]["kind"] == "WEEK"


def test_list_briefs_returns_only_current_workspace_items() -> None:
    client = TestClient(create_app())
    login(client)
    client.post(
        "/api/v1/briefs",
        json={
            "title": "机器人产业日报",
            "objective": "追踪新品、融资和政策",
            "requiredQuestions": ["今天有哪些重要变化？"],
            "dateRange": {
                "kind": "DAY",
                "referenceDate": "2026-06-26",
                "timezone": "Asia/Shanghai",
            },
        },
    )

    response = client.get("/api/v1/briefs")

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["totalItems"] >= 1
    assert any(item["title"] == "机器人产业日报" for item in body["data"])


def test_create_brief_validates_required_questions() -> None:
    client = TestClient(create_app())
    login(client)

    response = client.post(
        "/api/v1/briefs",
        json={
            "title": "无问题 Brief",
            "objective": "应该被拒绝",
            "requiredQuestions": ["   "],
            "dateRange": {
                "kind": "DAY",
                "referenceDate": "2026-06-26",
                "timezone": "Asia/Shanghai",
            },
        },
    )

    assert response.status_code == 422
