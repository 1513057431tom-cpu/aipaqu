from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import Enum
from itertools import count
from threading import RLock


class InternalDataType(str, Enum):
    INVENTORY = "INVENTORY"
    CONSUMPTION = "CONSUMPTION"
    DEMAND = "DEMAND"
    OPEN_SUPPLY = "OPEN_SUPPLY"


class SourceSystem(str, Enum):
    ERP = "ERP"
    MES = "MES"
    WMS = "WMS"
    DATABASE = "DATABASE"
    FILE = "FILE"
    OTHER = "OTHER"


class DuplicateSourceRecordError(ValueError):
    pass


@dataclass(frozen=True)
class InventorySnapshot:
    id: str
    workspace_id: str
    material_id: str
    location_code: str
    snapshot_at: datetime
    on_hand_qty: float
    available_qty: float
    reserved_qty: float
    quality_hold_qty: float
    unit: str
    source_system: SourceSystem
    source_record_ref: str
    sync_job_id: str


@dataclass(frozen=True)
class ConsumptionSnapshot:
    id: str
    workspace_id: str
    material_id: str
    bucket_date: date
    actual_qty: float
    planned_qty: float
    unit: str
    source_system: SourceSystem
    source_record_ref: str
    sync_job_id: str


@dataclass(frozen=True)
class MaterialDemand:
    id: str
    workspace_id: str
    material_id: str
    required_at: datetime
    required_qty: float
    unit: str
    source_type: str
    source_system: SourceSystem
    source_record_ref: str
    sync_job_id: str


@dataclass(frozen=True)
class OpenSupplySnapshot:
    id: str
    workspace_id: str
    material_id: str
    order_no: str
    order_line_no: str
    ordered_qty: float
    received_qty: float
    open_qty: float
    unit: str
    expected_at: datetime
    status: str
    source_system: SourceSystem
    source_record_ref: str
    sync_job_id: str


@dataclass(frozen=True)
class ImportErrorRecord:
    row: int
    code: str
    message: str


@dataclass(frozen=True)
class InternalImportResult:
    job_id: str
    workspace_id: str
    idempotency_key: str
    content_digest: str
    data_type: InternalDataType
    source_system: SourceSystem
    status: str
    file_name: str
    total_rows: int
    created_rows: int
    failed_rows: int
    errors: tuple[ImportErrorRecord, ...]
    replayed: bool = False


InternalRecord = (
    InventorySnapshot | ConsumptionSnapshot | MaterialDemand | OpenSupplySnapshot
)


class InMemoryInternalDataStore:
    def __init__(self) -> None:
        self._record_sequence = count(1)
        self._inventory: list[InventorySnapshot] = []
        self._consumption: list[ConsumptionSnapshot] = []
        self._demands: list[MaterialDemand] = []
        self._open_supply: list[OpenSupplySnapshot] = []
        self._imports: dict[tuple[str, str], InternalImportResult] = {}
        self._source_records: set[tuple[str, InternalDataType, SourceSystem, str]] = set()
        self._lock = RLock()

    def next_id(self, prefix: str) -> str:
        with self._lock:
            return f"{prefix}_{next(self._record_sequence)}"

    def add_record(
        self,
        data_type: InternalDataType,
        record: InternalRecord,
    ) -> None:
        source_key = (
            record.workspace_id,
            data_type,
            record.source_system,
            record.source_record_ref.casefold(),
        )
        with self._lock:
            if source_key in self._source_records:
                raise DuplicateSourceRecordError("Source record has already been imported.")
            target = {
                InternalDataType.INVENTORY: self._inventory,
                InternalDataType.CONSUMPTION: self._consumption,
                InternalDataType.DEMAND: self._demands,
                InternalDataType.OPEN_SUPPLY: self._open_supply,
            }[data_type]
            target.append(record)
            self._source_records.add(source_key)

    def get_import(self, workspace_id: str, idempotency_key: str) -> InternalImportResult | None:
        with self._lock:
            result = self._imports.get((workspace_id, idempotency_key))
            return replace(result, replayed=True) if result else None

    def save_import(self, result: InternalImportResult) -> None:
        with self._lock:
            self._imports[(result.workspace_id, result.idempotency_key)] = result

    def list_inventory(self, workspace_id: str) -> list[InventorySnapshot]:
        with self._lock:
            records = [item for item in self._inventory if item.workspace_id == workspace_id]
        return sorted(records, key=lambda item: (item.snapshot_at, item.id), reverse=True)

    def list_consumption(self, workspace_id: str) -> list[ConsumptionSnapshot]:
        with self._lock:
            records = [item for item in self._consumption if item.workspace_id == workspace_id]
        return sorted(records, key=lambda item: (item.bucket_date, item.id), reverse=True)

    def list_demands(self, workspace_id: str) -> list[MaterialDemand]:
        with self._lock:
            records = [item for item in self._demands if item.workspace_id == workspace_id]
        return sorted(records, key=lambda item: (item.required_at, item.id))

    def list_open_supply(self, workspace_id: str) -> list[OpenSupplySnapshot]:
        with self._lock:
            records = [item for item in self._open_supply if item.workspace_id == workspace_id]
        return sorted(records, key=lambda item: (item.expected_at, item.id))


internal_data_store = InMemoryInternalDataStore()
