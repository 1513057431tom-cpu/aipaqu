import json
from datetime import date, datetime, timezone
from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient

from app.api.routes.reports import get_report_service
from app.core.reports import (
    DailyIntelligenceSnapshot,
    InMemoryReportStore,
    ReportPeriod,
    ReportService,
    SnapshotStatus,
)
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


class UnsafeReportAgent:
    @staticmethod
    def write_report(_workspace_id: str, _payload: dict) -> str:
        return "# AI 日报\n\n信号 signal-1，证据 /api/v1/documents/document-1。"


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


def test_daily_report_marks_pending_intelligence_as_unconfirmed() -> None:
    snapshot = DailyIntelligenceSnapshot(
        id="daily-1",
        workspace_id="default",
        covered_date=date(2026, 8, 14),
        timezone="Asia/Shanghai",
        structured_data_json=json.dumps(
            {
                "inventoryCount": 1,
                "demandCount": 0,
                "openSupplyCount": 0,
                "confirmedSignals": [],
                "pendingSignals": [
                    {
                        "id": "signal-1",
                        "materialId": "material-1",
                        "summary": "公开报价可能上涨，等待人工确认。",
                        "evidenceRef": "/api/v1/documents/document-1",
                    }
                ],
                "recommendations": [],
            },
            ensure_ascii=False,
        ),
        content_digest="digest",
        status=SnapshotStatus.READY,
        approved_by=None,
        approved_at=None,
        created_at=datetime.now(timezone.utc),
    )

    markdown = ReportService._markdown(
        "物料情报日报",
        ReportPeriod.DAILY,
        date(2026, 8, 14),
        date(2026, 8, 14),
        [snapshot],
    )

    assert "待人工复核情报：1" in markdown
    assert "[待复核] `material-1` 公开报价可能上涨" in markdown
    assert "待复核外部信号 `signal-1`" in markdown


def test_ai_report_without_pending_marker_falls_back_to_deterministic_draft() -> None:
    snapshot = DailyIntelligenceSnapshot(
        id="daily-unsafe",
        workspace_id="default",
        covered_date=date(2026, 8, 14),
        timezone="Asia/Shanghai",
        structured_data_json=json.dumps(
            {
                "inventoryCount": 0,
                "demandCount": 0,
                "openSupplyCount": 0,
                "confirmedSignals": [],
                "pendingSignals": [
                    {
                        "id": "signal-1",
                        "materialId": "material-1",
                        "summary": "价格可能上涨。",
                        "evidenceRef": "/api/v1/documents/document-1",
                    }
                ],
                "recommendations": [],
            },
            ensure_ascii=False,
        ),
        content_digest="digest",
        status=SnapshotStatus.READY,
        approved_by=None,
        approved_at=None,
        created_at=datetime.now(timezone.utc),
    )
    service = ReportService(None, None, None, None, None, UnsafeReportAgent())

    markdown = service._render_markdown(
        "default",
        "物料情报日报",
        ReportPeriod.DAILY,
        date(2026, 8, 14),
        date(2026, 8, 14),
        [snapshot],
        None,
    )

    assert markdown.startswith("# 物料情报日报")
    assert "待人工复核情报：1" in markdown


def test_draft_daily_report_can_be_refreshed_without_creating_a_duplicate() -> None:
    from app.core.stores import catalog_store, internal_data_store, recommendation_store

    store = InMemoryReportStore()
    service = ReportService(
        store,
        catalog_store,
        internal_data_store,
        CountingMonitoringStore(),
        recommendation_store,
    )
    report, version = service.create(
        "default",
        "user-1",
        "物料情报日报",
        ReportPeriod.DAILY,
        date(2026, 8, 14),
        date(2026, 8, 14),
    )

    refreshed, refreshed_version = service.refresh_daily(
        "default",
        report.id,
        "user-1",
    )

    assert refreshed.id == report.id
    assert refreshed_version.version == version.version + 1
    assert len(store.list("default")) == 1
    assert store.get_daily_snapshot("default", date(2026, 8, 14)) is not None


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
