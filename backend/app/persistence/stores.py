from __future__ import annotations

import json
import hashlib
from dataclasses import asdict
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Engine, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.catalog import (
    CatalogStatus,
    DuplicateCatalogCodeError,
    DuplicateMaterialGroupCodeError,
    Material,
    MaterialGroup,
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
from app.core.monitoring import (
    CollectionJob,
    CollectionStatus,
    CollectionMode,
    Document,
    DuplicateSourceUrlError,
    ExternalSignal,
    ReviewStatus,
    SignalType,
    Source,
    SourceStatus,
)
from app.core.recommendations import (
    DecisionType,
    ProcurementRecommendation,
    RecommendationCalculation,
    RecommendationDecision,
    RecommendationStatus,
    RecommendationVersionConflictError,
    RiskLevel,
)
from app.core.reports import (
    DailyIntelligenceSnapshot,
    DuplicateDailyReportError,
    Report,
    ReportPeriod,
    ReportStatus,
    ReportVersion,
    SnapshotStatus,
)
from app.persistence.models import (
    CollectionJobModel,
    ConsumptionSnapshotModel,
    DailyIntelligenceSnapshotModel,
    DocumentModel,
    ExternalSignalModel,
    InternalImportModel,
    InventorySnapshotModel,
    MaterialDemandModel,
    MaterialGroupModel,
    MaterialModel,
    OpenSupplySnapshotModel,
    ProcurementRecommendationModel,
    RecommendationDecisionModel,
    ReportModel,
    ReportVersionModel,
    SourceModel,
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
        group_id=model.group_id,
        status=CatalogStatus(model.status),
        created_at=utc_aware(model.created_at),
        updated_at=utc_aware(model.updated_at),
    )


def material_group_from_model(model: MaterialGroupModel) -> MaterialGroup:
    return MaterialGroup(
        id=model.id,
        workspace_id=model.workspace_id,
        code=model.code,
        name=model.name,
        parent_id=model.parent_id,
        sort_order=model.sort_order,
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
        group_id: str | None = None,
    ) -> Material:
        if group_id is not None and self.get_material_group(workspace_id, group_id) is None:
            raise LookupError("Material group was not found.")
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
            group_id=group_id,
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
        group_id: str | None = None,
        status: CatalogStatus | None = None,
    ) -> list[Material]:
        statement = select(MaterialModel).where(MaterialModel.workspace_id == workspace_id)
        if category is not None:
            statement = statement.where(MaterialModel.category == category)
        if group_id is not None:
            statement = statement.where(MaterialModel.group_id == group_id)
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

    def update_material(self, material: Material) -> Material:
        with Session(self.engine) as session:
            model = session.scalar(
                select(MaterialModel).where(
                    MaterialModel.workspace_id == material.workspace_id,
                    MaterialModel.id == material.id,
                )
            )
            if model is None:
                raise LookupError("Material was not found.")
            if (
                material.group_id is not None
                and self.get_material_group(material.workspace_id, material.group_id) is None
            ):
                raise LookupError("Material group was not found.")
            model.external_code = material.external_code
            model.external_code_key = material.external_code.casefold()
            model.name = material.name
            model.specification = material.specification
            model.category = material.category
            model.base_unit = material.base_unit
            model.safety_stock_qty = material.safety_stock_qty
            model.lead_time_days = material.lead_time_days
            model.group_id = material.group_id
            model.updated_at = utc_naive(material.updated_at)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise DuplicateCatalogCodeError(
                    "Material external code already exists."
                ) from exc
            session.refresh(model)
            return material_from_model(model)

    def create_material_group(
        self,
        *,
        workspace_id: str,
        code: str,
        name: str,
        parent_id: str | None,
        sort_order: int,
    ) -> MaterialGroup:
        if parent_id is not None and self.get_material_group(workspace_id, parent_id) is None:
            raise LookupError("Material group was not found.")
        now = datetime.now(timezone.utc)
        model = MaterialGroupModel(
            id=f"grp_{uuid4().hex}",
            workspace_id=workspace_id,
            code=code,
            code_key=code.casefold(),
            name=name,
            parent_id=parent_id,
            sort_order=sort_order,
            created_at=utc_naive(now),
            updated_at=utc_naive(now),
        )
        with Session(self.engine) as session:
            session.add(model)
            try:
                session.commit()
            except IntegrityError as exc:
                raise DuplicateMaterialGroupCodeError(
                    "Material group code already exists."
                ) from exc
            session.refresh(model)
        return material_group_from_model(model)

    def list_material_groups(self, workspace_id: str) -> list[MaterialGroup]:
        with Session(self.engine) as session:
            models = session.scalars(
                select(MaterialGroupModel).where(MaterialGroupModel.workspace_id == workspace_id)
            ).all()
        groups = [material_group_from_model(model) for model in models]
        return sorted(groups, key=lambda item: (item.sort_order, item.name.casefold(), item.id))

    def get_material_group(self, workspace_id: str, group_id: str) -> MaterialGroup | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(MaterialGroupModel).where(
                    MaterialGroupModel.workspace_id == workspace_id,
                    MaterialGroupModel.id == group_id,
                )
            )
        return material_group_from_model(model) if model else None

    def count_materials_by_group(self, workspace_id: str) -> dict[str, int]:
        with Session(self.engine) as session:
            rows = session.execute(
                select(MaterialModel.group_id, func.count(MaterialModel.id)).where(
                    MaterialModel.workspace_id == workspace_id,
                    MaterialModel.group_id.is_not(None),
                ).group_by(MaterialModel.group_id)
            ).all()
        return {group_id: count for group_id, count in rows if group_id is not None}

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


def source_from_model(model: SourceModel) -> Source:
    return Source(
        id=model.id,
        workspace_id=model.workspace_id,
        name=model.name,
        target_url=model.target_url,
        allowed_domain=model.allowed_domain,
        schedule_minutes=model.schedule_minutes,
        signal_type=SignalType(model.signal_type),
        material_id=model.material_id,
        material_group_id=model.material_group_id,
        supplier_id=model.supplier_id,
        extraction_selector=model.extraction_selector,
        collection_mode=CollectionMode(model.collection_mode),
        navigation_goal=model.navigation_goal,
        status=SourceStatus(model.status),
        last_collected_at=utc_aware(model.last_collected_at) if model.last_collected_at else None,
        last_collection_status=(
            CollectionStatus(model.last_collection_status)
            if model.last_collection_status
            else None
        ),
        last_content_digest=model.last_content_digest,
        created_at=utc_aware(model.created_at),
        updated_at=utc_aware(model.updated_at),
    )


def document_from_model(model: DocumentModel) -> Document:
    return Document(
        id=model.id,
        workspace_id=model.workspace_id,
        source_id=model.source_id,
        collection_job_id=model.collection_job_id,
        final_url=model.final_url,
        status_code=model.status_code,
        content_type=model.content_type,
        title=model.title,
        extracted_text=model.extracted_text,
        content_digest=model.content_digest,
        previous_content_digest=model.previous_content_digest,
        changed=bool(model.changed),
        collected_at=utc_aware(model.collected_at),
    )


def job_from_model(model: CollectionJobModel) -> CollectionJob:
    return CollectionJob(
        id=model.id,
        workspace_id=model.workspace_id,
        source_id=model.source_id,
        status=CollectionStatus(model.status),
        started_at=utc_aware(model.started_at),
        finished_at=utc_aware(model.finished_at),
        status_code=model.status_code,
        document_id=model.document_id,
        content_changed=bool(model.content_changed),
        error_code=model.error_code,
        error_message=model.error_message,
    )


def signal_from_model(model: ExternalSignalModel) -> ExternalSignal:
    return ExternalSignal(
        id=model.id,
        workspace_id=model.workspace_id,
        source_id=model.source_id,
        document_id=model.document_id,
        signal_type=SignalType(model.signal_type),
        material_id=model.material_id,
        supplier_id=model.supplier_id,
        binding_key=model.binding_key,
        occurred_at=utc_aware(model.occurred_at),
        observed_at=utc_aware(model.observed_at),
        previous_value=model.previous_value,
        current_value=model.current_value,
        confidence=model.confidence,
        evidence_ref=model.evidence_ref,
        review_status=ReviewStatus(model.review_status),
        reviewed_by=model.reviewed_by,
        reviewed_at=utc_aware(model.reviewed_at) if model.reviewed_at else None,
        content_digest=model.content_digest,
        summary=model.summary,
        analysis_rationale=model.analysis_rationale,
        analysis_model=model.analysis_model,
        ai_analyzed=bool(model.ai_analyzed),
    )


class SqlAlchemyMonitoringStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create_source(self, source: Source) -> Source:
        with Session(self.engine) as session:
            session.add(self._source_model(source))
            try:
                session.commit()
            except IntegrityError as exc:
                raise DuplicateSourceUrlError(
                    "Source URL already exists in this workspace."
                ) from exc
        return source

    def update_source(self, source: Source) -> Source:
        with Session(self.engine) as session:
            session.merge(self._source_model(source))
            try:
                session.commit()
            except IntegrityError as exc:
                raise DuplicateSourceUrlError(
                    "Source URL already exists in this workspace."
                ) from exc
        return source

    def all_sources(self) -> list[Source]:
        with Session(self.engine) as session:
            models = session.scalars(select(SourceModel)).all()
        return [source_from_model(model) for model in models]

    def get_source(self, workspace_id: str, source_id: str) -> Source | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(SourceModel).where(
                    SourceModel.workspace_id == workspace_id,
                    SourceModel.id == source_id,
                )
            )
        return source_from_model(model) if model else None

    def list_sources(self, workspace_id: str) -> list[Source]:
        with Session(self.engine) as session:
            models = session.scalars(
                select(SourceModel)
                .where(
                    SourceModel.workspace_id == workspace_id,
                    SourceModel.status != SourceStatus.ARCHIVED.value,
                )
                .order_by(SourceModel.name, SourceModel.id)
            ).all()
        return [source_from_model(model) for model in models]

    def get_latest_document(self, workspace_id: str, source_id: str) -> Document | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(DocumentModel)
                .where(
                    DocumentModel.workspace_id == workspace_id,
                    DocumentModel.source_id == source_id,
                )
                .order_by(DocumentModel.collected_at.desc(), DocumentModel.id.desc())
                .limit(1)
            )
        return document_from_model(model) if model else None

    def save_collection(
        self,
        source: Source,
        job: CollectionJob,
        document: Document | None,
        signal: ExternalSignal | None,
    ) -> None:
        with Session(self.engine) as session:
            session.merge(self._source_model(source))
            if document:
                session.add(self._document_model(document))
            session.add(self._job_model(job))
            if signal and session.scalar(
                select(ExternalSignalModel.id).where(
                    ExternalSignalModel.source_id == signal.source_id,
                    ExternalSignalModel.signal_type == signal.signal_type.value,
                    ExternalSignalModel.binding_key == signal.binding_key,
                    ExternalSignalModel.content_digest == signal.content_digest,
                )
            ) is None:
                session.add(self._signal_model(signal))
            session.commit()

    def list_jobs(self, workspace_id: str, source_id: str | None = None) -> list[CollectionJob]:
        statement = select(CollectionJobModel).where(
            CollectionJobModel.workspace_id == workspace_id
        )
        if source_id:
            statement = statement.where(CollectionJobModel.source_id == source_id)
        statement = statement.order_by(
            CollectionJobModel.started_at.desc(),
            CollectionJobModel.id.desc(),
        )
        with Session(self.engine) as session:
            models = session.scalars(statement).all()
        return [job_from_model(model) for model in models]

    def list_signals(self, workspace_id: str, source_id: str | None = None) -> list[ExternalSignal]:
        statement = select(ExternalSignalModel).where(
            ExternalSignalModel.workspace_id == workspace_id
        )
        if source_id:
            statement = statement.where(ExternalSignalModel.source_id == source_id)
        statement = statement.order_by(
            ExternalSignalModel.observed_at.desc(),
            ExternalSignalModel.id.desc(),
        )
        with Session(self.engine) as session:
            models = session.scalars(statement).all()
        return [signal_from_model(model) for model in models]

    def get_signal(self, workspace_id: str, signal_id: str) -> ExternalSignal | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(ExternalSignalModel).where(
                    ExternalSignalModel.workspace_id == workspace_id,
                    ExternalSignalModel.id == signal_id,
                )
            )
        return signal_from_model(model) if model else None

    def update_signal_review(self, signal: ExternalSignal) -> ExternalSignal:
        with Session(self.engine) as session:
            model = session.scalar(
                select(ExternalSignalModel).where(
                    ExternalSignalModel.workspace_id == signal.workspace_id,
                    ExternalSignalModel.id == signal.id,
                )
            )
            if model is None:
                raise LookupError("Signal was not found.")
            model.review_status = signal.review_status.value
            model.reviewed_by = signal.reviewed_by
            model.reviewed_at = utc_naive(signal.reviewed_at) if signal.reviewed_at else None
            session.commit()
        return signal

    def get_document(self, workspace_id: str, document_id: str) -> Document | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(DocumentModel).where(
                    DocumentModel.workspace_id == workspace_id,
                    DocumentModel.id == document_id,
                )
            )
        return document_from_model(model) if model else None

    @staticmethod
    def _source_model(item: Source) -> SourceModel:
        return SourceModel(
            id=item.id,
            workspace_id=item.workspace_id,
            name=item.name,
            target_url=item.target_url,
            target_url_key=hashlib.sha256(item.target_url.encode("utf-8")).hexdigest(),
            allowed_domain=item.allowed_domain,
            schedule_minutes=item.schedule_minutes,
            signal_type=item.signal_type.value,
            material_id=item.material_id,
            material_group_id=item.material_group_id,
            supplier_id=item.supplier_id,
            extraction_selector=item.extraction_selector,
            collection_mode=item.collection_mode.value,
            navigation_goal=item.navigation_goal,
            status=item.status.value,
            last_collected_at=utc_naive(item.last_collected_at) if item.last_collected_at else None,
            last_collection_status=(
                item.last_collection_status.value if item.last_collection_status else None
            ),
            last_content_digest=item.last_content_digest,
            created_at=utc_naive(item.created_at),
            updated_at=utc_naive(item.updated_at),
        )

    @staticmethod
    def _job_model(item: CollectionJob) -> CollectionJobModel:
        return CollectionJobModel(
            id=item.id,
            workspace_id=item.workspace_id,
            source_id=item.source_id,
            status=item.status.value,
            started_at=utc_naive(item.started_at),
            finished_at=utc_naive(item.finished_at),
            status_code=item.status_code,
            document_id=item.document_id,
            content_changed=int(item.content_changed),
            error_code=item.error_code,
            error_message=item.error_message,
        )

    @staticmethod
    def _document_model(item: Document) -> DocumentModel:
        return DocumentModel(
            id=item.id,
            workspace_id=item.workspace_id,
            source_id=item.source_id,
            collection_job_id=item.collection_job_id,
            final_url=item.final_url,
            status_code=item.status_code,
            content_type=item.content_type,
            title=item.title,
            extracted_text=item.extracted_text,
            content_digest=item.content_digest,
            previous_content_digest=item.previous_content_digest,
            changed=int(item.changed),
            collected_at=utc_naive(item.collected_at),
        )

    @staticmethod
    def _signal_model(item: ExternalSignal) -> ExternalSignalModel:
        return ExternalSignalModel(
            id=item.id,
            workspace_id=item.workspace_id,
            source_id=item.source_id,
            document_id=item.document_id,
            signal_type=item.signal_type.value,
            material_id=item.material_id,
            supplier_id=item.supplier_id,
            binding_key=item.binding_key,
            occurred_at=utc_naive(item.occurred_at),
            observed_at=utc_naive(item.observed_at),
            previous_value=item.previous_value,
            current_value=item.current_value,
            confidence=item.confidence,
            evidence_ref=item.evidence_ref,
            review_status=item.review_status.value,
            reviewed_by=item.reviewed_by,
            reviewed_at=utc_naive(item.reviewed_at) if item.reviewed_at else None,
            content_digest=item.content_digest,
            summary=item.summary,
            analysis_rationale=item.analysis_rationale,
            analysis_model=item.analysis_model,
            ai_analyzed=int(item.ai_analyzed),
        )


def recommendation_from_model(model: ProcurementRecommendationModel) -> ProcurementRecommendation:
    calculation = json.loads(model.calculation_json)
    return ProcurementRecommendation(
        id=model.id,
        workspace_id=model.workspace_id,
        material_id=model.material_id,
        as_of_date=model.as_of_date,
        horizon_end=model.horizon_end,
        recommended_order_date=model.recommended_order_date,
        latest_order_date=model.latest_order_date,
        recommended_qty=model.recommended_qty,
        unit=model.unit,
        risk_level=RiskLevel(model.risk_level),
        reason_codes=tuple(json.loads(model.reason_codes_json)),
        calculation=RecommendationCalculation(**calculation),
        explanation=model.explanation,
        input_digest=model.input_digest,
        algorithm_key=model.algorithm_key,
        algorithm_version=model.algorithm_version,
        evidence_refs=tuple(json.loads(model.evidence_refs_json)),
        external_signal_ids=tuple(json.loads(model.external_signal_ids_json)),
        status=RecommendationStatus(model.status),
        version=model.version,
        created_at=utc_aware(model.created_at),
        updated_at=utc_aware(model.updated_at),
    )


def decision_from_model(model: RecommendationDecisionModel) -> RecommendationDecision:
    return RecommendationDecision(
        id=model.id,
        recommendation_id=model.recommendation_id,
        decision=DecisionType(model.decision),
        adjusted_order_date=model.adjusted_order_date,
        adjusted_qty=model.adjusted_qty,
        reason=model.reason,
        actor_id=model.actor_id,
        created_at=utc_aware(model.created_at),
    )


class SqlAlchemyRecommendationStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def find_by_digest(self, workspace_id: str, material_id: str, input_digest: str) -> ProcurementRecommendation | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(ProcurementRecommendationModel).where(
                    ProcurementRecommendationModel.workspace_id == workspace_id,
                    ProcurementRecommendationModel.material_id == material_id,
                    ProcurementRecommendationModel.input_digest == input_digest,
                )
            )
        return recommendation_from_model(model) if model else None

    def save(self, recommendation: ProcurementRecommendation) -> ProcurementRecommendation:
        with Session(self.engine) as session:
            session.add(self._model(recommendation))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = self.find_by_digest(
                    recommendation.workspace_id,
                    recommendation.material_id,
                    recommendation.input_digest,
                )
                if existing is None:
                    raise
                return existing
        return recommendation

    def list(self, workspace_id: str) -> list[ProcurementRecommendation]:
        with Session(self.engine) as session:
            models = session.scalars(
                select(ProcurementRecommendationModel)
                .where(ProcurementRecommendationModel.workspace_id == workspace_id)
                .order_by(
                    ProcurementRecommendationModel.latest_order_date,
                    ProcurementRecommendationModel.created_at.desc(),
                )
            ).all()
        return [recommendation_from_model(model) for model in models]

    def get(self, workspace_id: str, recommendation_id: str) -> ProcurementRecommendation | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(ProcurementRecommendationModel).where(
                    ProcurementRecommendationModel.workspace_id == workspace_id,
                    ProcurementRecommendationModel.id == recommendation_id,
                )
            )
        return recommendation_from_model(model) if model else None

    def list_decisions(self, recommendation_id: str) -> list[RecommendationDecision]:
        with Session(self.engine) as session:
            models = session.scalars(
                select(RecommendationDecisionModel)
                .where(RecommendationDecisionModel.recommendation_id == recommendation_id)
                .order_by(RecommendationDecisionModel.created_at, RecommendationDecisionModel.id)
            ).all()
        return [decision_from_model(model) for model in models]

    def decide(self, recommendation: ProcurementRecommendation, decision: RecommendationDecision, expected_version: int) -> ProcurementRecommendation:
        with Session(self.engine) as session:
            result = session.execute(
                update(ProcurementRecommendationModel)
                .where(
                    ProcurementRecommendationModel.workspace_id == recommendation.workspace_id,
                    ProcurementRecommendationModel.id == recommendation.id,
                    ProcurementRecommendationModel.version == expected_version,
                )
                .values(
                    status=recommendation.status.value,
                    version=recommendation.version,
                    updated_at=utc_naive(recommendation.updated_at),
                )
            )
            if result.rowcount != 1:
                session.rollback()
                raise RecommendationVersionConflictError("Recommendation version has changed.")
            session.add(RecommendationDecisionModel(
                id=decision.id,
                recommendation_id=decision.recommendation_id,
                decision=decision.decision.value,
                adjusted_order_date=decision.adjusted_order_date,
                adjusted_qty=decision.adjusted_qty,
                reason=decision.reason,
                actor_id=decision.actor_id,
                created_at=utc_naive(decision.created_at),
            ))
            session.commit()
        return recommendation

    @staticmethod
    def _model(item: ProcurementRecommendation) -> ProcurementRecommendationModel:
        return ProcurementRecommendationModel(
            id=item.id,
            workspace_id=item.workspace_id,
            material_id=item.material_id,
            as_of_date=item.as_of_date,
            horizon_end=item.horizon_end,
            recommended_order_date=item.recommended_order_date,
            latest_order_date=item.latest_order_date,
            recommended_qty=item.recommended_qty,
            unit=item.unit,
            risk_level=item.risk_level.value,
            reason_codes_json=json.dumps(item.reason_codes),
            calculation_json=json.dumps(asdict(item.calculation)),
            explanation=item.explanation,
            input_digest=item.input_digest,
            algorithm_key=item.algorithm_key,
            algorithm_version=item.algorithm_version,
            evidence_refs_json=json.dumps(item.evidence_refs),
            external_signal_ids_json=json.dumps(item.external_signal_ids),
            status=item.status.value,
            version=item.version,
            created_at=utc_naive(item.created_at),
            updated_at=utc_naive(item.updated_at),
        )


def report_from_model(model: ReportModel) -> Report:
    return Report(
        id=model.id,
        workspace_id=model.workspace_id,
        title=model.title,
        report_period=ReportPeriod(model.report_period),
        input_mode=model.input_mode,
        period_start=model.period_start,
        period_end=model.period_end,
        status=ReportStatus(model.status),
        current_version_id=model.current_version_id,
        input_snapshot_ids=tuple(json.loads(model.input_snapshot_ids_json)),
        input_snapshot_dates=tuple(date.fromisoformat(item) for item in json.loads(model.input_snapshot_dates_json)),
        approved_by=model.approved_by,
        approved_at=utc_aware(model.approved_at) if model.approved_at else None,
        created_at=utc_aware(model.created_at),
        updated_at=utc_aware(model.updated_at),
    )


def report_version_from_model(model: ReportVersionModel) -> ReportVersion:
    return ReportVersion(
        id=model.id,
        report_id=model.report_id,
        version=model.version,
        markdown=model.markdown,
        content_digest=model.content_digest,
        change_source=model.change_source,
        created_by=model.created_by,
        created_at=utc_aware(model.created_at),
    )


def daily_snapshot_from_model(model: DailyIntelligenceSnapshotModel) -> DailyIntelligenceSnapshot:
    return DailyIntelligenceSnapshot(
        id=model.id,
        workspace_id=model.workspace_id,
        covered_date=model.covered_date,
        timezone=model.timezone,
        structured_data_json=model.structured_data_json,
        content_digest=model.content_digest,
        status=SnapshotStatus(model.status),
        approved_by=model.approved_by,
        approved_at=utc_aware(model.approved_at) if model.approved_at else None,
        created_at=utc_aware(model.created_at),
    )


class SqlAlchemyReportStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create(
        self,
        report: Report,
        version: ReportVersion,
        snapshot: DailyIntelligenceSnapshot | None,
    ) -> Report:
        with Session(self.engine) as session:
            if snapshot:
                session.add(self._snapshot_model(snapshot))
            session.add(self._report_model(report))
            session.add(self._version_model(version))
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                if snapshot and self.get_daily_snapshot(snapshot.workspace_id, snapshot.covered_date):
                    raise DuplicateDailyReportError(
                        "该日期已存在日报。"
                    ) from exc
                raise
        return report

    def list(self, workspace_id: str) -> list[Report]:
        with Session(self.engine) as session:
            models = session.scalars(
                select(ReportModel)
                .where(ReportModel.workspace_id == workspace_id)
                .order_by(ReportModel.period_start.desc(), ReportModel.created_at.desc())
            ).all()
        return [report_from_model(model) for model in models]

    def get(self, workspace_id: str, report_id: str) -> Report | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(ReportModel).where(
                    ReportModel.workspace_id == workspace_id,
                    ReportModel.id == report_id,
                )
            )
        return report_from_model(model) if model else None

    def get_version(self, version_id: str) -> ReportVersion | None:
        with Session(self.engine) as session:
            model = session.get(ReportVersionModel, version_id)
        return report_version_from_model(model) if model else None

    def save_version(self, report: Report, version: ReportVersion) -> Report:
        with Session(self.engine) as session:
            model = session.get(ReportModel, report.id)
            if model is None:
                raise LookupError("Report was not found.")
            model.current_version_id = report.current_version_id
            model.updated_at = utc_naive(report.updated_at)
            session.add(self._version_model(version))
            session.commit()
        return report

    def refresh_daily(
        self,
        report: Report,
        version: ReportVersion,
        snapshot: DailyIntelligenceSnapshot,
    ) -> Report:
        with Session(self.engine) as session:
            model = session.get(ReportModel, report.id)
            snapshot_model = session.get(DailyIntelligenceSnapshotModel, snapshot.id)
            if model is None or snapshot_model is None:
                raise LookupError("Daily report or snapshot was not found.")
            model.current_version_id = report.current_version_id
            model.updated_at = utc_naive(report.updated_at)
            snapshot_model.structured_data_json = snapshot.structured_data_json
            snapshot_model.content_digest = snapshot.content_digest
            snapshot_model.status = snapshot.status.value
            snapshot_model.approved_by = snapshot.approved_by
            snapshot_model.approved_at = None
            session.add(self._version_model(version))
            session.commit()
        return report

    def approve(
        self,
        report: Report,
        snapshot: DailyIntelligenceSnapshot | None,
    ) -> Report:
        with Session(self.engine) as session:
            model = session.get(ReportModel, report.id)
            if model is None:
                raise LookupError("Report was not found.")
            model.status = report.status.value
            model.approved_by = report.approved_by
            model.approved_at = utc_naive(report.approved_at) if report.approved_at else None
            model.updated_at = utc_naive(report.updated_at)
            if snapshot:
                snapshot_model = session.get(DailyIntelligenceSnapshotModel, snapshot.id)
                if snapshot_model is None:
                    raise LookupError("Daily snapshot was not found.")
                snapshot_model.status = snapshot.status.value
                snapshot_model.approved_by = snapshot.approved_by
                snapshot_model.approved_at = (
                    utc_naive(snapshot.approved_at) if snapshot.approved_at else None
                )
            session.commit()
        return report

    def get_daily_snapshot(
        self,
        workspace_id: str,
        covered_date: date,
    ) -> DailyIntelligenceSnapshot | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(DailyIntelligenceSnapshotModel).where(
                    DailyIntelligenceSnapshotModel.workspace_id == workspace_id,
                    DailyIntelligenceSnapshotModel.covered_date == covered_date,
                )
            )
        return daily_snapshot_from_model(model) if model else None

    def list_daily_snapshots(
        self,
        workspace_id: str,
        start: date,
        end: date,
    ) -> list[DailyIntelligenceSnapshot]:
        with Session(self.engine) as session:
            models = session.scalars(
                select(DailyIntelligenceSnapshotModel)
                .where(
                    DailyIntelligenceSnapshotModel.workspace_id == workspace_id,
                    DailyIntelligenceSnapshotModel.covered_date >= start,
                    DailyIntelligenceSnapshotModel.covered_date <= end,
                )
                .order_by(DailyIntelligenceSnapshotModel.covered_date)
            ).all()
        return [daily_snapshot_from_model(model) for model in models]

    @staticmethod
    def _report_model(item: Report) -> ReportModel:
        return ReportModel(
            id=item.id,
            workspace_id=item.workspace_id,
            title=item.title,
            report_period=item.report_period.value,
            input_mode=item.input_mode,
            period_start=item.period_start,
            period_end=item.period_end,
            status=item.status.value,
            current_version_id=item.current_version_id,
            input_snapshot_ids_json=json.dumps(item.input_snapshot_ids),
            input_snapshot_dates_json=json.dumps([value.isoformat() for value in item.input_snapshot_dates]),
            approved_by=item.approved_by,
            approved_at=utc_naive(item.approved_at) if item.approved_at else None,
            created_at=utc_naive(item.created_at),
            updated_at=utc_naive(item.updated_at),
        )

    @staticmethod
    def _version_model(item: ReportVersion) -> ReportVersionModel:
        return ReportVersionModel(
            id=item.id,
            report_id=item.report_id,
            version=item.version,
            markdown=item.markdown,
            content_digest=item.content_digest,
            change_source=item.change_source,
            created_by=item.created_by,
            created_at=utc_naive(item.created_at),
        )

    @staticmethod
    def _snapshot_model(item: DailyIntelligenceSnapshot) -> DailyIntelligenceSnapshotModel:
        return DailyIntelligenceSnapshotModel(
            id=item.id,
            workspace_id=item.workspace_id,
            covered_date=item.covered_date,
            timezone=item.timezone,
            structured_data_json=item.structured_data_json,
            content_digest=item.content_digest,
            status=item.status.value,
            approved_by=item.approved_by,
            approved_at=utc_naive(item.approved_at) if item.approved_at else None,
            created_at=utc_naive(item.created_at),
        )
    DocumentModel,
    ExternalSignalModel,
    SourceModel,
