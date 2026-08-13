from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.catalog import (
    CatalogStatus,
    DuplicateCatalogCodeError,
    Material,
    Supplier,
)
from app.core.internal_data import (
    ConsumptionSnapshot,
    DuplicateSourceRecordError,
    ImportErrorRecord,
    InternalDataType,
    InternalImportResult,
    InventorySnapshot,
    MaterialDemand,
    OpenSupplySnapshot,
    SourceSystem,
)
from app.persistence.models import (
    ConsumptionSnapshotModel,
    InternalImportModel,
    InventorySnapshotModel,
    MaterialDemandModel,
    MaterialModel,
    OpenSupplySnapshotModel,
    SupplierModel,
)


def utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utc_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def material_from_model(model: MaterialModel) -> Material:
    return Material(
        id=model.id,
        workspace_id=model.workspace_id,
        external_code=model.external_code,
        name=model.name,
        specification=model.specification,
        category=model.category,
        base_unit=model.base_unit,
        safety_stock_qty=model.safety_stock_qty,
        lead_time_days=model.lead_time_days,
        status=CatalogStatus(model.status),
        created_at=utc_aware(model.created_at),
        updated_at=utc_aware(model.updated_at),
    )


def supplier_from_model(model: SupplierModel) -> Supplier:
    return Supplier(
        id=model.id,
        workspace_id=model.workspace_id,
        external_code=model.external_code,
        name=model.name,
        website=model.website,
        country=model.country,
        status=CatalogStatus(model.status),
        created_at=utc_aware(model.created_at),
        updated_at=utc_aware(model.updated_at),
    )


class SqlAlchemyCatalogStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create_material(
        self,
        *,
        workspace_id: str,
        external_code: str,
        name: str,
        specification: str,
        category: str,
        base_unit: str,
        safety_stock_qty: float,
        lead_time_days: int,
    ) -> Material:
        now = datetime.now(timezone.utc)
        model = MaterialModel(
            id=f"mat_{uuid4().hex}",
            workspace_id=workspace_id,
            external_code=external_code,
            external_code_key=external_code.casefold(),
            name=name,
            specification=specification,
            category=category,
            base_unit=base_unit,
            safety_stock_qty=safety_stock_qty,
            lead_time_days=lead_time_days,
            status=CatalogStatus.ACTIVE.value,
            created_at=utc_naive(now),
            updated_at=utc_naive(now),
        )
        with Session(self.engine) as session:
            session.add(model)
            try:
                session.commit()
            except IntegrityError as exc:
                raise DuplicateCatalogCodeError("Material external code already exists.") from exc
            session.refresh(model)
        return material_from_model(model)

    def list_materials(
        self,
        workspace_id: str,
        *,
        query: str = "",
        category: str | None = None,
        status: CatalogStatus | None = None,
    ) -> list[Material]:
        statement = select(MaterialModel).where(MaterialModel.workspace_id == workspace_id)
        if category is not None:
            statement = statement.where(MaterialModel.category == category)
        if status is not None:
            statement = statement.where(MaterialModel.status == status.value)
        with Session(self.engine) as session:
            models = session.scalars(statement).all()
        normalized_query = query.casefold()
        records = [material_from_model(model) for model in models]
        if normalized_query:
            records = [
                item
                for item in records
                if normalized_query in item.external_code.casefold()
                or normalized_query in item.name.casefold()
                or normalized_query in item.specification.casefold()
            ]
        return sorted(records, key=lambda item: (item.external_code.casefold(), item.id))

    def get_material(self, workspace_id: str, material_id: str) -> Material | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(MaterialModel).where(
                    MaterialModel.workspace_id == workspace_id,
                    MaterialModel.id == material_id,
                )
            )
        return material_from_model(model) if model else None

    def get_material_by_external_code(
        self,
        workspace_id: str,
        external_code: str,
    ) -> Material | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(MaterialModel).where(
                    MaterialModel.workspace_id == workspace_id,
                    MaterialModel.external_code_key == external_code.casefold(),
                )
            )
        return material_from_model(model) if model else None

    def create_supplier(
        self,
        *,
        workspace_id: str,
        external_code: str,
        name: str,
        website: str | None,
        country: str,
    ) -> Supplier:
        now = datetime.now(timezone.utc)
        model = SupplierModel(
            id=f"sup_{uuid4().hex}",
            workspace_id=workspace_id,
            external_code=external_code,
            external_code_key=external_code.casefold(),
            name=name,
            website=website,
            country=country,
            status=CatalogStatus.ACTIVE.value,
            created_at=utc_naive(now),
            updated_at=utc_naive(now),
        )
        with Session(self.engine) as session:
            session.add(model)
            try:
                session.commit()
            except IntegrityError as exc:
                raise DuplicateCatalogCodeError("Supplier external code already exists.") from exc
            session.refresh(model)
        return supplier_from_model(model)

    def list_suppliers(
        self,
        workspace_id: str,
        *,
        query: str = "",
        status: CatalogStatus | None = None,
    ) -> list[Supplier]:
        statement = select(SupplierModel).where(SupplierModel.workspace_id == workspace_id)
        if status is not None:
            statement = statement.where(SupplierModel.status == status.value)
        with Session(self.engine) as session:
            models = session.scalars(statement).all()
        normalized_query = query.casefold()
        records = [supplier_from_model(model) for model in models]
        if normalized_query:
            records = [
                item
                for item in records
                if normalized_query in item.external_code.casefold()
                or normalized_query in item.name.casefold()
            ]
        return sorted(records, key=lambda item: (item.external_code.casefold(), item.id))


RECORD_MODELS = {
    InternalDataType.INVENTORY: InventorySnapshotModel,
    InternalDataType.CONSUMPTION: ConsumptionSnapshotModel,
    InternalDataType.DEMAND: MaterialDemandModel,
    InternalDataType.OPEN_SUPPLY: OpenSupplySnapshotModel,
}


class SqlAlchemyInternalDataStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def next_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

    def add_record(self, data_type: InternalDataType | str, record) -> None:
        normalized_type = InternalDataType(data_type)
        values = asdict(record)
        values["source_system"] = record.source_system.value
        for key in ("snapshot_at", "required_at", "expected_at"):
            if key in values:
                values[key] = utc_naive(values[key])
        model = RECORD_MODELS[normalized_type](**values)
        with Session(self.engine) as session:
            session.add(model)
            try:
                session.commit()
            except IntegrityError as exc:
                raise DuplicateSourceRecordError("Source record has already been imported.") from exc

    def get_import(self, workspace_id: str, idempotency_key: str) -> InternalImportResult | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(InternalImportModel).where(
                    InternalImportModel.workspace_id == workspace_id,
                    InternalImportModel.idempotency_key == idempotency_key,
                )
            )
        if model is None:
            return None
        errors = tuple(ImportErrorRecord(**item) for item in json.loads(model.errors_json))
        return InternalImportResult(
            job_id=model.job_id,
            workspace_id=model.workspace_id,
            idempotency_key=model.idempotency_key,
            content_digest=model.content_digest,
            data_type=InternalDataType(model.data_type),
            source_system=SourceSystem(model.source_system),
            status=model.status,
            file_name=model.file_name,
            total_rows=model.total_rows,
            created_rows=model.created_rows,
            failed_rows=model.failed_rows,
            errors=errors,
            replayed=True,
        )

    def save_import(self, result: InternalImportResult) -> None:
        model = InternalImportModel(
            job_id=result.job_id,
            workspace_id=result.workspace_id,
            idempotency_key=result.idempotency_key,
            content_digest=result.content_digest,
            data_type=result.data_type.value,
            source_system=result.source_system.value,
            status=result.status,
            file_name=result.file_name,
            total_rows=result.total_rows,
            created_rows=result.created_rows,
            failed_rows=result.failed_rows,
            errors_json=json.dumps([asdict(item) for item in result.errors], ensure_ascii=False),
        )
        with Session(self.engine) as session:
            session.add(model)
            session.commit()

    def list_inventory(self, workspace_id: str) -> list[InventorySnapshot]:
        models = self._list(InventorySnapshotModel, workspace_id, "snapshot_at", descending=True)
        return [
            InventorySnapshot(
                id=item.id, workspace_id=item.workspace_id, material_id=item.material_id,
                location_code=item.location_code, snapshot_at=utc_aware(item.snapshot_at),
                on_hand_qty=item.on_hand_qty, available_qty=item.available_qty,
                reserved_qty=item.reserved_qty, quality_hold_qty=item.quality_hold_qty,
                unit=item.unit, source_system=SourceSystem(item.source_system),
                source_record_ref=item.source_record_ref, sync_job_id=item.sync_job_id,
            )
            for item in models
        ]

    def list_consumption(self, workspace_id: str) -> list[ConsumptionSnapshot]:
        models = self._list(ConsumptionSnapshotModel, workspace_id, "bucket_date", descending=True)
        return [
            ConsumptionSnapshot(
                id=item.id, workspace_id=item.workspace_id, material_id=item.material_id,
                bucket_date=item.bucket_date, actual_qty=item.actual_qty,
                planned_qty=item.planned_qty, unit=item.unit,
                source_system=SourceSystem(item.source_system), source_record_ref=item.source_record_ref,
                sync_job_id=item.sync_job_id,
            )
            for item in models
        ]

    def list_demands(self, workspace_id: str) -> list[MaterialDemand]:
        models = self._list(MaterialDemandModel, workspace_id, "required_at")
        return [
            MaterialDemand(
                id=item.id, workspace_id=item.workspace_id, material_id=item.material_id,
                required_at=utc_aware(item.required_at), required_qty=item.required_qty,
                unit=item.unit, source_type=item.source_type,
                source_system=SourceSystem(item.source_system), source_record_ref=item.source_record_ref,
                sync_job_id=item.sync_job_id,
            )
            for item in models
        ]

    def list_open_supply(self, workspace_id: str) -> list[OpenSupplySnapshot]:
        models = self._list(OpenSupplySnapshotModel, workspace_id, "expected_at")
        return [
            OpenSupplySnapshot(
                id=item.id, workspace_id=item.workspace_id, material_id=item.material_id,
                order_no=item.order_no, order_line_no=item.order_line_no,
                ordered_qty=item.ordered_qty, received_qty=item.received_qty,
                open_qty=item.open_qty, unit=item.unit, expected_at=utc_aware(item.expected_at),
                status=item.status, source_system=SourceSystem(item.source_system),
                source_record_ref=item.source_record_ref, sync_job_id=item.sync_job_id,
            )
            for item in models
        ]

    def _list(self, model_type, workspace_id: str, order_field: str, descending: bool = False):
        order_column = getattr(model_type, order_field)
        order = order_column.desc() if descending else order_column.asc()
        with Session(self.engine) as session:
            return list(
                session.scalars(
                    select(model_type).where(model_type.workspace_id == workspace_id).order_by(order)
                ).all()
            )
