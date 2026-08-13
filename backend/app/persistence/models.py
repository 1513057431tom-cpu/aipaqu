from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MaterialModel(Base):
    __tablename__ = "materials"
    __table_args__ = (UniqueConstraint("workspace_id", "external_code_key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    external_code: Mapped[str] = mapped_column(String(80))
    external_code_key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(200))
    specification: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(120), default="")
    base_unit: Mapped[str] = mapped_column(String(32))
    safety_stock_qty: Mapped[float] = mapped_column(Float, default=0)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupplierModel(Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("workspace_id", "external_code_key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    external_code: Mapped[str] = mapped_column(String(80))
    external_code_key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InternalImportModel(Base):
    __tablename__ = "internal_data_imports"
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key"),)

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    content_digest: Mapped[str] = mapped_column(String(64))
    data_type: Mapped[str] = mapped_column(String(32))
    source_system: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    file_name: Mapped[str] = mapped_column(String(255))
    total_rows: Mapped[int] = mapped_column(Integer)
    created_rows: Mapped[int] = mapped_column(Integer)
    failed_rows: Mapped[int] = mapped_column(Integer)
    errors_json: Mapped[str] = mapped_column(Text, default="[]")


class InventorySnapshotModel(Base):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        UniqueConstraint("workspace_id", "source_system", "source_record_ref"),
        Index("ix_inventory_workspace_material_time", "workspace_id", "material_id", "snapshot_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64))
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    location_code: Mapped[str] = mapped_column(String(80))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    on_hand_qty: Mapped[float] = mapped_column(Float)
    available_qty: Mapped[float] = mapped_column(Float)
    reserved_qty: Mapped[float] = mapped_column(Float)
    quality_hold_qty: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    source_system: Mapped[str] = mapped_column(String(32))
    source_record_ref: Mapped[str] = mapped_column(String(240))
    sync_job_id: Mapped[str] = mapped_column(String(64), index=True)


class ConsumptionSnapshotModel(Base):
    __tablename__ = "consumption_snapshots"
    __table_args__ = (
        UniqueConstraint("workspace_id", "source_system", "source_record_ref"),
        Index("ix_consumption_workspace_material_date", "workspace_id", "material_id", "bucket_date"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64))
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    bucket_date: Mapped[date] = mapped_column(Date)
    actual_qty: Mapped[float] = mapped_column(Float)
    planned_qty: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    source_system: Mapped[str] = mapped_column(String(32))
    source_record_ref: Mapped[str] = mapped_column(String(240))
    sync_job_id: Mapped[str] = mapped_column(String(64), index=True)


class MaterialDemandModel(Base):
    __tablename__ = "material_demands"
    __table_args__ = (
        UniqueConstraint("workspace_id", "source_system", "source_record_ref"),
        Index("ix_demand_workspace_material_time", "workspace_id", "material_id", "required_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64))
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    required_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    required_qty: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    source_type: Mapped[str] = mapped_column(String(80))
    source_system: Mapped[str] = mapped_column(String(32))
    source_record_ref: Mapped[str] = mapped_column(String(240))
    sync_job_id: Mapped[str] = mapped_column(String(64), index=True)


class OpenSupplySnapshotModel(Base):
    __tablename__ = "open_supply_snapshots"
    __table_args__ = (
        UniqueConstraint("workspace_id", "source_system", "source_record_ref"),
        Index("ix_supply_workspace_material_time", "workspace_id", "material_id", "expected_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64))
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    order_no: Mapped[str] = mapped_column(String(120))
    order_line_no: Mapped[str] = mapped_column(String(80))
    ordered_qty: Mapped[float] = mapped_column(Float)
    received_qty: Mapped[float] = mapped_column(Float)
    open_qty: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    expected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40))
    source_system: Mapped[str] = mapped_column(String(32))
    source_record_ref: Mapped[str] = mapped_column(String(240))
    sync_job_id: Mapped[str] = mapped_column(String(64), index=True)
