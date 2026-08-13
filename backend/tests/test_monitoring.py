from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.routes.monitoring import get_monitoring_service
from app.core.monitoring import FetchResult, MonitoringService, run_due_collections, validate_public_url
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
