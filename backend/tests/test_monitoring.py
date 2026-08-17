from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.routes.monitoring import get_monitoring_service
from app.core.monitoring import (
    CollectionMode,
    FetchResult,
    MonitoringService,
    SignalAnalysis,
    extract_html,
    run_due_collections,
    validate_public_url,
)
from app.core.stores import monitoring_store
from app.main import create_app


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "change-me-now"},
    )
    assert response.status_code == 200


def create_material(client: TestClient, external_code: str) -> str:
    response = client.post(
        "/api/v1/materials",
        json={
            "externalCode": external_code,
            "name": "Monitored material",
            "specification": "",
            "category": "raw",
            "baseUnit": "kg",
            "safetyStockQty": 0,
            "leadTimeDays": 7,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@dataclass
class SequenceFetcher:
    results: list[FetchResult]

    def fetch(self, _url: str, _allowed_domain: str) -> FetchResult:
        return self.results.pop(0)


@dataclass
class SourceBrowserFetcher:
    results: list[FetchResult]

    def fetch(self, _source) -> FetchResult:
        return self.results.pop(0)


@dataclass
class FixedSignalAnalyzer:
    material_id: str

    def analyze(self, _source, _document, _previous) -> SignalAnalysis:
        return SignalAnalysis(
            relevant=True,
            summary="酸枣仁公开报价由每公斤 100 元调整为 115 元。",
            previous_value="100 元/公斤",
            current_value="115 元/公斤",
            confidence=0.93,
            rationale="新旧证据均明确包含物料名、单位和报价。",
            material_id=self.material_id,
            model="deepseek-chat",
        )


def test_public_url_validation_blocks_private_and_mismatched_hosts() -> None:
    assert validate_public_url("https://example.com/prices", "example.com") == (
        "https://example.com/prices",
        "example.com",
    )

    for url, domain in (
        ("http://127.0.0.1/admin", "127.0.0.1"),
        ("http://localhost/admin", "localhost"),
        ("https://other.example/prices", "example.com"),
        ("https://example.com:22/prices", "example.com"),
        ("file:///etc/passwd", "example.com"),
    ):
        try:
            validate_public_url(url, domain)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected URL to be rejected: {url}")


def test_html_extraction_ignores_script_style_and_template_content() -> None:
    title, text = extract_html(
        b"""
        <html><head><title>Price board</title><style>.price { color: red; }</style></head>
        <body><script>window.secretNoise = 'ignore me';</script>
        <main><h1>Material A</h1><p>Price: 115 CNY</p>
        <template>hidden template text</template></main></body></html>
        """,
        "main",
        "text/html; charset=utf-8",
    )

    assert title == "Price board"
    assert text == "Material A Price: 115 CNY"


def test_collection_creates_baseline_then_change_signal_with_evidence() -> None:
    app = create_app()
    fetcher = SequenceFetcher(
        [
            FetchResult(
                final_url="https://example.com/prices",
                status_code=200,
                content_type="text/html; charset=utf-8",
                body=b"<html><title>Price</title><body><main>Price: 100 CNY</main></body></html>",
            ),
            FetchResult(
                final_url="https://example.com/prices",
                status_code=200,
                content_type="text/html; charset=utf-8",
                body=b"<html><title>Price</title><body><main>Price: 115 CNY</main></body></html>",
            ),
        ]
    )
    app.dependency_overrides[get_monitoring_service] = lambda: MonitoringService(
        monitoring_store,
        fetcher=fetcher,
    )
    client = TestClient(app)
    login(client)
    material_id = create_material(client, "MONITOR-MAT-001")

    source_response = client.post(
        "/api/v1/sources",
        json={
            "name": "Public price page",
            "targetUrl": "https://example.com/prices",
            "allowedDomain": "example.com",
            "scheduleMinutes": 60,
            "signalType": "PRICE",
            "materialId": material_id,
            "extractionSelector": "main",
        },
    )
    assert source_response.status_code == 201
    source_id = source_response.json()["id"]

    baseline = client.post(f"/api/v1/sources/{source_id}/collect")
    changed = client.post(f"/api/v1/sources/{source_id}/collect")
    signals = client.get("/api/v1/external-signals", params={"sourceId": source_id})

    assert baseline.status_code == 200
    assert baseline.json()["job"]["status"] == "SUCCEEDED"
    assert baseline.json()["signal"] is None
    assert baseline.json()["downstreamStatus"] == "QUEUED"
    assert changed.status_code == 200
    assert changed.json()["job"]["status"] == "SUCCEEDED"
    assert changed.json()["signal"]["signalType"] == "PRICE"
    assert changed.json()["signal"]["previousValue"] == "Price: 100 CNY"
    assert changed.json()["signal"]["currentValue"] == "Price: 115 CNY"
    assert signals.status_code == 200
    assert signals.json()["pagination"]["totalItems"] == 1
    assert signals.json()["data"][0]["evidenceRef"].startswith("/api/v1/documents/")

    signal_id = signals.json()["data"][0]["id"]
    reviewed = client.patch(
        f"/api/v1/external-signals/{signal_id}",
        json={"reviewStatus": "CONFIRMED"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["reviewStatus"] == "CONFIRMED"
    assert reviewed.json()["reviewedBy"]
    assert reviewed.json()["reviewedAt"]


def test_signal_review_rejects_pending_and_missing_signal() -> None:
    client = TestClient(create_app())
    login(client)

    pending = client.patch(
        "/api/v1/external-signals/missing",
        json={"reviewStatus": "PENDING"},
    )
    missing = client.patch(
        "/api/v1/external-signals/missing",
        json={"reviewStatus": "DISMISSED"},
    )

    assert pending.status_code == 422
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SIGNAL_NOT_FOUND"


def test_access_challenge_stops_collection_without_creating_signal() -> None:
    app = create_app()
    app.dependency_overrides[get_monitoring_service] = lambda: MonitoringService(
        monitoring_store,
        fetcher=SequenceFetcher(
            [
                FetchResult(
                    final_url="https://challenge.example.com/stock",
                    status_code=403,
                    content_type="text/html",
                    body=b"Access denied - CAPTCHA required",
                )
            ]
        ),
    )
    client = TestClient(app)
    login(client)
    material_id = create_material(client, "MONITOR-MAT-CHALLENGE")
    source = client.post(
        "/api/v1/sources",
        json={
            "name": "Challenge page",
            "targetUrl": "https://challenge.example.com/stock",
            "allowedDomain": "challenge.example.com",
            "scheduleMinutes": 60,
            "signalType": "AVAILABILITY",
            "materialId": material_id,
            "extractionSelector": "body",
        },
    )

    response = client.post(f"/api/v1/sources/{source.json()['id']}/collect")

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "WAITING_HUMAN"
    assert response.json()["job"]["errorCode"] == "ACCESS_CHALLENGE"
    assert response.json()["signal"] is None


def test_duplicate_source_url_returns_conflict() -> None:
    client = TestClient(create_app())
    login(client)
    material_id = create_material(client, "MONITOR-MAT-DUPLICATE")
    payload = {
        "name": "Duplicate page",
        "targetUrl": "https://example.com/duplicate",
        "allowedDomain": "example.com",
        "scheduleMinutes": 60,
        "signalType": "PRICE",
        "materialId": material_id,
        "extractionSelector": "body",
    }

    first = client.post("/api/v1/sources", json=payload)
    second = client.post("/api/v1/sources", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SOURCE_URL_DUPLICATE"


def test_due_collection_batch_runs_only_sources_past_their_schedule() -> None:
    from datetime import datetime, timedelta, timezone
    from app.core.monitoring import InMemoryMonitoringStore, SignalType, Source, SourceStatus

    store = InMemoryMonitoringStore()
    now = datetime(2026, 8, 13, 3, 0, tzinfo=timezone.utc)
    for source_id, collected_at in (
        ("due", now - timedelta(minutes=61)),
        ("fresh", now - timedelta(minutes=30)),
    ):
        store.create_source(Source(
            id=source_id, workspace_id="default", name=source_id,
            target_url=f"https://{source_id}.example.com/", allowed_domain="example.com",
            schedule_minutes=60, signal_type=SignalType.PRICE, material_id="mat-1",
            supplier_id=None, extraction_selector="body", status=SourceStatus.ACTIVE,
            last_collected_at=collected_at, last_collection_status=None,
            last_content_digest=None, created_at=now, updated_at=now,
        ))
    fetcher = SequenceFetcher([FetchResult(
        final_url="https://due.example.com/", status_code=200,
        content_type="text/html", body=b"<body>baseline</body>",
    )])

    results = run_due_collections(store, fetcher=fetcher, now=now)

    assert [result.job.source_id for result in results] == ["due"]


def test_material_group_source_can_be_edited_and_archived() -> None:
    client = TestClient(create_app())
    login(client)
    group = client.post(
        "/api/v1/material-groups",
        json={"code": "RAW", "name": "原料组", "parentId": None, "sortOrder": 1},
    )
    assert group.status_code == 201
    payload = {
        "name": "原料行情",
        "targetUrl": "https://example.com/materials",
        "allowedDomain": "example.com",
        "scheduleMinutes": 60,
        "signalType": "PRICE",
        "materialGroupId": group.json()["id"],
        "collectionMode": "AI_BROWSER",
        "navigationGoal": "搜索组内物料并读取价格标签",
    }

    created = client.post("/api/v1/sources", json=payload)
    assert created.status_code == 201
    assert created.json()["materialGroupId"] == group.json()["id"]
    assert created.json()["collectionMode"] == "AI_BROWSER"

    updated = client.patch(
        f"/api/v1/sources/{created.json()['id']}",
        json={**payload, "name": "原料价格监控", "status": "PAUSED"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "原料价格监控"
    assert updated.json()["status"] == "PAUSED"

    archived = client.delete(f"/api/v1/sources/{created.json()['id']}")
    assert archived.status_code == 204
    assert all(
        item["id"] != created.json()["id"]
        for item in client.get("/api/v1/sources").json()["data"]
    )


def test_ai_browser_collection_persists_structured_signal_and_filter() -> None:
    app = create_app()
    client = TestClient(app)
    login(client)
    material_id = create_material(client, "MONITOR-AI-001")
    service = MonitoringService(
        monitoring_store,
        browser_fetcher=SourceBrowserFetcher(
            [
                FetchResult(
                    final_url="https://example.com/search",
                    status_code=200,
                    content_type="text/html; charset=utf-8",
                    body=b"<html><body><main>Material price: 100</main></body></html>",
                ),
                FetchResult(
                    final_url="https://example.com/search",
                    status_code=200,
                    content_type="text/html; charset=utf-8",
                    body=b"<html><body><main>Material price: 115</main></body></html>",
                ),
            ]
        ),
        signal_analyzer=FixedSignalAnalyzer(material_id),
    )
    app.dependency_overrides[get_monitoring_service] = lambda: service
    source = client.post(
        "/api/v1/sources",
        json={
            "name": "AI price search",
            "targetUrl": "https://example.com/search",
            "allowedDomain": "example.com",
            "scheduleMinutes": 60,
            "signalType": "PRICE",
            "materialId": material_id,
            "collectionMode": CollectionMode.AI_BROWSER.value,
            "navigationGoal": "搜索物料价格",
            "extractionSelector": "main",
        },
    )
    assert source.status_code == 201

    client.post(f"/api/v1/sources/{source.json()['id']}/collect")
    changed = client.post(f"/api/v1/sources/{source.json()['id']}/collect")
    signal = changed.json()["signal"]

    assert signal["aiAnalyzed"] is True
    assert signal["summary"].startswith("酸枣仁")
    assert signal["confidence"] == 0.93
    assert signal["analysisModel"] == "deepseek-chat"
    signal_query = {
        "sourceId": source.json()["id"],
        "reviewStatus": "CONFIRMED",
    }
    assert client.get(
        "/api/v1/external-signals", params=signal_query
    ).json()["pagination"]["totalItems"] == 0
    client.patch(
        f"/api/v1/external-signals/{signal['id']}",
        json={"reviewStatus": "CONFIRMED"},
    )
    assert client.get(
        "/api/v1/external-signals", params=signal_query
    ).json()["pagination"]["totalItems"] == 1
