from dataclasses import replace
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.catalog import CatalogStatus
from app.core.internal_data import InventorySnapshot, SourceSystem
from app.core.monitoring import (
    CollectionJob,
    CollectionStatus,
    Document,
    ExternalSignal,
    ReviewStatus,
    SignalType,
    Source,
    SourceStatus,
)
from app.persistence.models import Base
from app.persistence.stores import (
    SqlAlchemyCatalogStore,
    SqlAlchemyInternalDataStore,
    SqlAlchemyMonitoringStore,
)


def create_test_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def test_catalog_records_survive_repository_recreation() -> None:
    engine = create_test_engine()
    first_store = SqlAlchemyCatalogStore(engine)
    material = first_store.create_material(
        workspace_id="storage-test",
        external_code="DB-MAT-001",
        name="Database material",
        specification="25kg",
        category="raw",
        base_unit="kg",
        safety_stock_qty=500,
        lead_time_days=10,
    )

    second_store = SqlAlchemyCatalogStore(engine)
    loaded = second_store.get_material("storage-test", material.id)

    assert loaded is not None
    assert loaded.external_code == "DB-MAT-001"
    assert loaded.status == CatalogStatus.ACTIVE

    updated = second_store.update_material(
        replace(
            loaded,
            name="Updated database material",
            safety_stock_qty=750,
            updated_at=datetime(2026, 8, 13, 3, 0, tzinfo=timezone.utc),
        )
    )
    recreated = SqlAlchemyCatalogStore(engine).get_material("storage-test", material.id)

    assert updated.name == "Updated database material"
    assert recreated == updated


def test_internal_snapshots_survive_repository_recreation() -> None:
    engine = create_test_engine()
    catalog_store = SqlAlchemyCatalogStore(engine)
    material = catalog_store.create_material(
        workspace_id="storage-test",
        external_code="DB-INV-001",
        name="Inventory material",
        specification="",
        category="",
        base_unit="kg",
        safety_stock_qty=0,
        lead_time_days=0,
    )
    first_store = SqlAlchemyInternalDataStore(engine)
    first_store.add_record(
        data_type="INVENTORY",
        record=InventorySnapshot(
            id=first_store.next_id("inv"),
            workspace_id="storage-test",
            material_id=material.id,
            location_code="WH-A",
            snapshot_at=datetime(2026, 8, 13, 0, 0, tzinfo=timezone.utc),
            on_hand_qty=100,
            available_qty=80,
            reserved_qty=10,
            quality_hold_qty=10,
            unit="kg",
            source_system=SourceSystem.ERP,
            source_record_ref="db-inv-001",
            sync_job_id="sync-db-001",
        ),
    )

    second_store = SqlAlchemyInternalDataStore(engine)
    records = second_store.list_inventory("storage-test")

    assert len(records) == 1
    assert records[0].available_qty == 80
    assert records[0].snapshot_at.tzinfo == timezone.utc


def test_monitoring_evidence_and_signal_survive_repository_recreation() -> None:
    engine = create_test_engine()
    store = SqlAlchemyMonitoringStore(engine)
    now = datetime(2026, 8, 13, 2, 0, tzinfo=timezone.utc)
    source = Source(
        id="src-db-001",
        workspace_id="storage-test",
        name="Public page",
        target_url="https://example.com/price",
        allowed_domain="example.com",
        schedule_minutes=60,
        signal_type=SignalType.PRICE,
        material_id="mat-external",
        supplier_id=None,
        extraction_selector="main",
        status=SourceStatus.ACTIVE,
        last_collected_at=now,
        last_collection_status=CollectionStatus.SUCCEEDED,
        last_content_digest="new-digest",
        created_at=now,
        updated_at=now,
    )
    document = Document(
        id="doc-db-001",
        workspace_id="storage-test",
        source_id=source.id,
        collection_job_id="job-db-001",
        final_url=source.target_url,
        status_code=200,
        content_type="text/html",
        title="Price",
        extracted_text="Price: 115",
        content_digest="new-digest",
        previous_content_digest="old-digest",
        changed=True,
        collected_at=now,
    )
    job = CollectionJob(
        id="job-db-001",
        workspace_id="storage-test",
        source_id=source.id,
        status=CollectionStatus.SUCCEEDED,
        started_at=now,
        finished_at=now,
        status_code=200,
        document_id=document.id,
        content_changed=True,
        error_code=None,
        error_message=None,
    )
    signal = ExternalSignal(
        id="sig-db-001",
        workspace_id="storage-test",
        source_id=source.id,
        document_id=document.id,
        signal_type=SignalType.PRICE,
        material_id="mat-external",
        supplier_id=None,
        binding_key="MATERIAL:mat-external",
        occurred_at=now,
        observed_at=now,
        previous_value="Price: 100",
        current_value="Price: 115",
        confidence=1.0,
        evidence_ref=f"/api/v1/documents/{document.id}",
        review_status=ReviewStatus.PENDING,
        reviewed_by=None,
        reviewed_at=None,
        content_digest="new-digest",
    )

    store.create_source(source)
    store.save_collection(source, job, document, signal)

    recreated = SqlAlchemyMonitoringStore(engine)
    assert recreated.get_source("storage-test", source.id) == source
    assert recreated.get_document("storage-test", document.id) == document
    assert recreated.list_signals("storage-test") == [signal]

    reviewed = recreated.update_signal_review(
        replace(
            signal,
            review_status=ReviewStatus.CONFIRMED,
            reviewed_by="user-1",
            reviewed_at=now,
        )
    )
    assert recreated.get_signal("storage-test", signal.id) == reviewed
