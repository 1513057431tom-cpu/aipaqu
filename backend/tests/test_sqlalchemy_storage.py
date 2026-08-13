from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.catalog import CatalogStatus
from app.core.internal_data import InventorySnapshot, SourceSystem
from app.persistence.models import Base
from app.persistence.stores import SqlAlchemyCatalogStore, SqlAlchemyInternalDataStore


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
