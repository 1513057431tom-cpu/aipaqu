from datetime import date
from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient

from app.api.routes.reports import get_report_service
from app.core.reports import InMemoryReportStore, ReportService
from app.main import create_app


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "change-me-now"},
    )
    assert response.status_code == 200


class CountingMonitoringStore:
    def __init__(self) -> None:
        self.calls = 0

    def list_signals(self, _workspace_id: str):
        self.calls += 1
        return []


def report_client() -> tuple[TestClient, InMemoryReportStore, CountingMonitoringStore]:
    from app.core.stores import catalog_store, internal_data_store, recommendation_store

    app = create_app()
    store = InMemoryReportStore()
    monitoring = CountingMonitoringStore()
    app.dependency_overrides[get_report_service] = lambda: ReportService(
        store,
        catalog_store,
        internal_data_store,
        monitoring,
        recommendation_store,
    )
    client = TestClient(app)
    login(client)
    return client, store, monitoring


def test_weekly_report_lists_missing_daily_inputs_without_collecting() -> None:
    client, _store, monitoring = report_client()

    response = client.post(
        "/api/v1/reports",
        json={
            "reportPeriod": "WEEKLY",
            "periodStart": "2026-08-10",
            "periodEnd": "2026-08-16",
            "title": "Weekly supply report",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PERIOD_INPUT_INCOMPLETE"
    assert response.json()["error"]["details"]["missingDates"] == [
        "2026-08-10",
        "2026-08-11",
        "2026-08-12",
        "2026-08-13",
        "2026-08-14",
        "2026-08-15",
        "2026-08-16",
    ]
    assert monitoring.calls == 0


def test_daily_reports_aggregate_to_weekly_and_export_approved_version() -> None:
    client, store, _monitoring = report_client()
    for day in range(10, 17):
        created = client.post(
            "/api/v1/reports",
            json={
                "reportPeriod": "DAILY",
                "periodStart": f"2026-08-{day:02d}",
                "periodEnd": f"2026-08-{day:02d}",
                "title": f"Daily report 2026-08-{day:02d}",
            },
        )
        assert created.status_code == 201
        approved = client.post(f"/api/v1/reports/{created.json()['id']}/approve")
        assert approved.status_code == 200

    weekly = client.post(
        "/api/v1/reports",
        json={
            "reportPeriod": "WEEKLY",
            "periodStart": "2026-08-10",
            "periodEnd": "2026-08-16",
            "title": "Weekly supply report",
        },
    )
    assert weekly.status_code == 201
    body = weekly.json()
    assert body["inputMode"] == "AGGREGATE_DAILY_SNAPSHOTS"
    assert body["inputSnapshotDates"] == [f"2026-08-{day:02d}" for day in range(10, 17)]
    assert body["currentVersion"]["markdown"].startswith("# Weekly supply report")
    assert "#### 引用" in body["currentVersion"]["markdown"]

    edited_markdown = "# Weekly supply report\n\n人工审核后的周报正文。"
    edited = client.post(
        f"/api/v1/reports/{body['id']}/versions",
        json={"markdown": edited_markdown},
    )
    assert edited.status_code == 201
    assert edited.json()["currentVersion"]["version"] == 2

    unapproved = client.get(f"/api/v1/reports/{body['id']}/exports/markdown")
    assert unapproved.status_code == 409
    client.post(f"/api/v1/reports/{body['id']}/approve")
    markdown = client.get(f"/api/v1/reports/{body['id']}/exports/markdown")
    docx = client.get(f"/api/v1/reports/{body['id']}/exports/docx")

    assert markdown.status_code == 200
    assert markdown.content.decode() == edited_markdown
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert docx.status_code == 200
    assert docx.content.startswith(b"PK")
    assert docx.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert any("Weekly supply report" in paragraph.text for paragraph in Document(BytesIO(docx.content)).paragraphs)
    assert len(store.list_daily_snapshots("default", date(2026, 8, 10), date(2026, 8, 16))) == 7


def test_daily_report_date_is_unique() -> None:
    client, _store, _monitoring = report_client()
    payload = {
        "reportPeriod": "DAILY",
        "periodStart": "2026-08-13",
        "periodEnd": "2026-08-13",
        "title": "Daily report",
    }

    assert client.post("/api/v1/reports", json=payload).status_code == 201
    duplicate = client.post("/api/v1/reports", json=payload)

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DAILY_REPORT_EXISTS"

    listing = client.get("/api/v1/reports?pageSize=1")
    assert listing.status_code == 200
    assert listing.json()["pagination"]["totalItems"] == 1
