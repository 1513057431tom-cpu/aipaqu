from __future__ import annotations

import csv
import hashlib
import io
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, TypeVar
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile, status
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.core.auth import User, get_current_user
from app.core.catalog import Material, catalog_store
from app.core.errors import api_error
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
    internal_data_store,
)

router = APIRouter(prefix="/api/v1", tags=["internal-data"])

MAX_CSV_BYTES = 5 * 1024 * 1024
ALLOWED_CSV_MEDIA_TYPES = {"text/csv", "application/vnd.ms-excel"}
T = TypeVar("T")

REQUIRED_HEADERS = {
    InternalDataType.INVENTORY: {
        "materialExternalCode",
        "locationCode",
        "snapshotAt",
        "onHandQty",
        "availableQty",
        "unit",
        "sourceRecordRef",
    },
    InternalDataType.CONSUMPTION: {
        "materialExternalCode",
        "bucketDate",
        "actualQty",
        "unit",
        "sourceRecordRef",
    },
    InternalDataType.DEMAND: {
        "materialExternalCode",
        "requiredAt",
        "requiredQty",
        "unit",
        "sourceType",
        "sourceRecordRef",
    },
    InternalDataType.OPEN_SUPPLY: {
        "materialExternalCode",
        "orderNo",
        "orderLineNo",
        "orderedQty",
        "receivedQty",
        "openQty",
        "unit",
        "expectedAt",
        "status",
        "sourceRecordRef",
    },
}


class Pagination(BaseModel):
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class MaterialReference(BaseModel):
    id: str
    externalCode: str
    name: str
    baseUnit: str


class ImportRowErrorResponse(BaseModel):
    row: int
    code: str
    message: str


class InternalImportResultResponse(BaseModel):
    jobId: str
    dataType: InternalDataType
    sourceSystem: SourceSystem
    status: str
    fileName: str
    totalRows: int
    createdRows: int
    failedRows: int
    errors: list[ImportRowErrorResponse]
    replayed: bool


class InternalRowBase(BaseModel):
    materialExternalCode: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=32)
    sourceRecordRef: str = Field(min_length=1, max_length=240)

    @field_validator("materialExternalCode", "unit", "sourceRecordRef")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be blank.")
        return stripped


class InventoryImportRow(InternalRowBase):
    locationCode: str = Field(min_length=1, max_length=80)
    snapshotAt: datetime
    onHandQty: float = Field(ge=0, allow_inf_nan=False)
    availableQty: float = Field(ge=0, allow_inf_nan=False)
    reservedQty: float = Field(default=0, ge=0, allow_inf_nan=False)
    qualityHoldQty: float = Field(default=0, ge=0, allow_inf_nan=False)

    @field_validator("locationCode")
    @classmethod
    def strip_location(cls, value: str) -> str:
        return value.strip()

    @field_validator("snapshotAt")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("snapshotAt must include a timezone offset.")
        return value

    @model_validator(mode="after")
    def quantities_are_consistent(self) -> "InventoryImportRow":
        if self.availableQty > self.onHandQty:
            raise ValueError("availableQty must not exceed onHandQty.")
        if self.reservedQty + self.qualityHoldQty > self.onHandQty:
            raise ValueError("reservedQty and qualityHoldQty exceed onHandQty.")
        return self


class ConsumptionImportRow(InternalRowBase):
    bucketDate: date
    actualQty: float = Field(ge=0, allow_inf_nan=False)
    plannedQty: float = Field(default=0, ge=0, allow_inf_nan=False)


class DemandImportRow(InternalRowBase):
    requiredAt: datetime
    requiredQty: float = Field(gt=0, allow_inf_nan=False)
    sourceType: str = Field(min_length=1, max_length=80)

    @field_validator("requiredAt")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("requiredAt must include a timezone offset.")
        return value


class OpenSupplyImportRow(InternalRowBase):
    orderNo: str = Field(min_length=1, max_length=120)
    orderLineNo: str = Field(min_length=1, max_length=80)
    orderedQty: float = Field(gt=0, allow_inf_nan=False)
    receivedQty: float = Field(ge=0, allow_inf_nan=False)
    openQty: float = Field(ge=0, allow_inf_nan=False)
    expectedAt: datetime
    status: str = Field(min_length=1, max_length=40)

    @field_validator("expectedAt")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expectedAt must include a timezone offset.")
        return value

    @model_validator(mode="after")
    def quantities_are_consistent(self) -> "OpenSupplyImportRow":
        if self.receivedQty > self.orderedQty or self.openQty > self.orderedQty:
            raise ValueError("receivedQty and openQty must not exceed orderedQty.")
        return self


class InventorySnapshotResponse(BaseModel):
    id: str
    material: MaterialReference
    locationCode: str
    snapshotAt: datetime
    onHandQty: float
    availableQty: float
    reservedQty: float
    qualityHoldQty: float
    unit: str
    sourceSystem: SourceSystem
    sourceRecordRef: str
    syncJobId: str


class ConsumptionSnapshotResponse(BaseModel):
    id: str
    material: MaterialReference
    bucketDate: date
    actualQty: float
    plannedQty: float
    unit: str
    sourceSystem: SourceSystem
    sourceRecordRef: str
    syncJobId: str


class MaterialDemandResponse(BaseModel):
    id: str
    material: MaterialReference
    requiredAt: datetime
    requiredQty: float
    unit: str
    sourceType: str
    sourceSystem: SourceSystem
    sourceRecordRef: str
    syncJobId: str


class OpenSupplySnapshotResponse(BaseModel):
    id: str
    material: MaterialReference
    orderNo: str
    orderLineNo: str
    orderedQty: float
    receivedQty: float
    openQty: float
    unit: str
    expectedAt: datetime
    status: str
    sourceSystem: SourceSystem
    sourceRecordRef: str
    syncJobId: str


class InventorySnapshotListResponse(BaseModel):
    data: list[InventorySnapshotResponse]
    pagination: Pagination


class ConsumptionSnapshotListResponse(BaseModel):
    data: list[ConsumptionSnapshotResponse]
    pagination: Pagination


class MaterialDemandListResponse(BaseModel):
    data: list[MaterialDemandResponse]
    pagination: Pagination


class OpenSupplySnapshotListResponse(BaseModel):
    data: list[OpenSupplySnapshotResponse]
    pagination: Pagination


class UnitMappingRequiredError(ValueError):
    pass


def material_reference(material: Material) -> MaterialReference:
    return MaterialReference(
        id=material.id,
        externalCode=material.external_code,
        name=material.name,
        baseUnit=material.base_unit,
    )


def paginate(items: list[T], page: int, page_size: int) -> tuple[list[T], Pagination]:
    total_items = len(items)
    total_pages = (total_items + page_size - 1) // page_size
    start = (page - 1) * page_size
    return items[start : start + page_size], Pagination(
        page=page,
        pageSize=page_size,
        totalItems=total_items,
        totalPages=total_pages,
    )


def parse_csv(content: bytes) -> tuple[csv.DictReader, str]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_CSV_ENCODING",
            "CSV files must use UTF-8 encoding.",
        ) from exc
    return csv.DictReader(io.StringIO(text, newline="")), text


def build_record(
    *,
    data_type: InternalDataType,
    row: dict[str, str],
    workspace_id: str,
    source_system: SourceSystem,
    sync_job_id: str,
) -> tuple[InternalDataType, Any]:
    material = catalog_store.get_material_by_external_code(
        workspace_id,
        row.get("materialExternalCode", ""),
    )
    if material is None:
        raise LookupError("Material external code is not mapped.")
    source_unit = row.get("unit", "").strip()
    if source_unit.casefold() != material.base_unit.casefold():
        raise UnitMappingRequiredError("Source unit is not mapped to the material base unit.")

    if data_type == InternalDataType.INVENTORY:
        payload = InventoryImportRow.model_validate(row)
        return data_type, InventorySnapshot(
            id=internal_data_store.next_id("inv"),
            workspace_id=workspace_id,
            material_id=material.id,
            location_code=payload.locationCode,
            snapshot_at=payload.snapshotAt,
            on_hand_qty=payload.onHandQty,
            available_qty=payload.availableQty,
            reserved_qty=payload.reservedQty,
            quality_hold_qty=payload.qualityHoldQty,
            unit=payload.unit,
            source_system=source_system,
            source_record_ref=payload.sourceRecordRef,
            sync_job_id=sync_job_id,
        )
    if data_type == InternalDataType.CONSUMPTION:
        payload = ConsumptionImportRow.model_validate(row)
        return data_type, ConsumptionSnapshot(
            id=internal_data_store.next_id("con"),
            workspace_id=workspace_id,
            material_id=material.id,
            bucket_date=payload.bucketDate,
            actual_qty=payload.actualQty,
            planned_qty=payload.plannedQty,
            unit=payload.unit,
            source_system=source_system,
            source_record_ref=payload.sourceRecordRef,
            sync_job_id=sync_job_id,
        )
    if data_type == InternalDataType.DEMAND:
        payload = DemandImportRow.model_validate(row)
        return data_type, MaterialDemand(
            id=internal_data_store.next_id("dem"),
            workspace_id=workspace_id,
            material_id=material.id,
            required_at=payload.requiredAt,
            required_qty=payload.requiredQty,
            unit=payload.unit,
            source_type=payload.sourceType.strip(),
            source_system=source_system,
            source_record_ref=payload.sourceRecordRef,
            sync_job_id=sync_job_id,
        )
    payload = OpenSupplyImportRow.model_validate(row)
    return data_type, OpenSupplySnapshot(
        id=internal_data_store.next_id("sup"),
        workspace_id=workspace_id,
        material_id=material.id,
        order_no=payload.orderNo.strip(),
        order_line_no=payload.orderLineNo.strip(),
        ordered_qty=payload.orderedQty,
        received_qty=payload.receivedQty,
        open_qty=payload.openQty,
        unit=payload.unit,
        expected_at=payload.expectedAt,
        status=payload.status.strip().upper(),
        source_system=source_system,
        source_record_ref=payload.sourceRecordRef,
        sync_job_id=sync_job_id,
    )


def import_result_response(result: InternalImportResult) -> InternalImportResultResponse:
    return InternalImportResultResponse(
        jobId=result.job_id,
        dataType=result.data_type,
        sourceSystem=result.source_system,
        status=result.status,
        fileName=result.file_name,
        totalRows=result.total_rows,
        createdRows=result.created_rows,
        failedRows=result.failed_rows,
        errors=[
            ImportRowErrorResponse(row=item.row, code=item.code, message=item.message)
            for item in result.errors
        ],
        replayed=result.replayed,
    )


@router.post(
    "/internal-data/imports",
    response_model=InternalImportResultResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_internal_data(
    data_type: InternalDataType = Form(alias="dataType"),
    source_system: SourceSystem = Form(alias="sourceSystem"),
    file: UploadFile = File(),
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)] = "",
    user: User = Depends(get_current_user),
) -> InternalImportResultResponse:
    if not idempotency_key:
        raise api_error(
            status.HTTP_400_BAD_REQUEST,
            "IDEMPOTENCY_KEY_REQUIRED",
            "Idempotency-Key header is required.",
        )
    file_name = Path(file.filename or "").name
    if Path(file_name).suffix.casefold() != ".csv" or file.content_type not in ALLOWED_CSV_MEDIA_TYPES:
        raise api_error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "UNSUPPORTED_IMPORT_TYPE",
            "Only CSV files are supported for internal data imports.",
        )
    content = await file.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        raise api_error(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "IMPORT_FILE_TOO_LARGE",
            "CSV import file exceeds the 5 MB limit.",
        )
    content_digest = hashlib.sha256(content).hexdigest()
    replay = internal_data_store.get_import(user.workspace_id, idempotency_key)
    if replay:
        if (
            replay.content_digest != content_digest
            or replay.data_type != data_type
            or replay.source_system != source_system
        ):
            raise api_error(
                status.HTTP_409_CONFLICT,
                "IDEMPOTENCY_KEY_CONFLICT",
                "Idempotency key was already used for different content.",
            )
        return import_result_response(replay)

    reader, _ = parse_csv(content)
    missing_headers = sorted(REQUIRED_HEADERS[data_type] - set(reader.fieldnames or []))
    if missing_headers:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "CSV_HEADERS_MISSING",
            "CSV file is missing required headers.",
            {"missingHeaders": missing_headers},
        )

    job_id = f"sync_{uuid4().hex}"
    total_rows = 0
    created_rows = 0
    errors: list[ImportErrorRecord] = []
    for row_number, source_row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in source_row.values()):
            continue
        total_rows += 1
        cleaned_row = {
            key: value.strip()
            for key, value in source_row.items()
            if key is not None and value is not None and value.strip()
        }
        try:
            record_type, record = build_record(
                data_type=data_type,
                row=cleaned_row,
                workspace_id=user.workspace_id,
                source_system=source_system,
                sync_job_id=job_id,
            )
            internal_data_store.add_record(record_type, record)
            created_rows += 1
        except LookupError:
            errors.append(
                ImportErrorRecord(
                    row=row_number,
                    code="MATERIAL_NOT_MAPPED",
                    message="Material external code is not mapped.",
                )
            )
        except UnitMappingRequiredError:
            errors.append(
                ImportErrorRecord(
                    row=row_number,
                    code="UNIT_MAPPING_REQUIRED",
                    message="Source unit is not mapped to the material base unit.",
                )
            )
        except ValidationError as exc:
            errors.append(
                ImportErrorRecord(
                    row=row_number,
                    code="VALIDATION_ERROR",
                    message=exc.errors(include_url=False)[0]["msg"],
                )
            )
        except DuplicateSourceRecordError:
            errors.append(
                ImportErrorRecord(
                    row=row_number,
                    code="DUPLICATE_SOURCE_RECORD",
                    message="Source record has already been imported.",
                )
            )

    if total_rows == 0:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "CSV_HAS_NO_DATA_ROWS",
            "CSV file does not contain any data rows.",
        )
    result_status = "SUCCEEDED"
    if errors:
        result_status = "SUCCEEDED_WITH_ERRORS" if created_rows else "FAILED"
    result = InternalImportResult(
        job_id=job_id,
        workspace_id=user.workspace_id,
        idempotency_key=idempotency_key,
        content_digest=content_digest,
        data_type=data_type,
        source_system=source_system,
        status=result_status,
        file_name=file_name,
        total_rows=total_rows,
        created_rows=created_rows,
        failed_rows=len(errors),
        errors=tuple(errors),
    )
    internal_data_store.save_import(result)
    return import_result_response(result)


def filter_by_material(
    records: list[T],
    *,
    material_id: str | None,
    material_external_code: str | None,
    workspace_id: str,
) -> list[T]:
    target_id = material_id
    if material_external_code:
        material = catalog_store.get_material_by_external_code(
            workspace_id,
            material_external_code,
        )
        target_id = material.id if material else "__not_found__"
    if not target_id:
        return records
    return [record for record in records if getattr(record, "material_id") == target_id]


def resolve_material(workspace_id: str, material_id: str) -> Material:
    material = catalog_store.get_material(workspace_id, material_id)
    if material is None:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "MATERIAL_REFERENCE_INVALID",
            "Snapshot references an unavailable material.",
        )
    return material


@router.get("/inventory-snapshots", response_model=InventorySnapshotListResponse)
def list_inventory_snapshots(
    material_id: str | None = Query(default=None, alias="materialId"),
    material_external_code: str | None = Query(default=None, alias="materialExternalCode"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
) -> InventorySnapshotListResponse:
    records = filter_by_material(
        internal_data_store.list_inventory(user.workspace_id),
        material_id=material_id,
        material_external_code=material_external_code,
        workspace_id=user.workspace_id,
    )
    page_items, pagination = paginate(records, page, page_size)
    return InventorySnapshotListResponse(
        data=[
            InventorySnapshotResponse(
                id=item.id,
                material=material_reference(resolve_material(user.workspace_id, item.material_id)),
                locationCode=item.location_code,
                snapshotAt=item.snapshot_at,
                onHandQty=item.on_hand_qty,
                availableQty=item.available_qty,
                reservedQty=item.reserved_qty,
                qualityHoldQty=item.quality_hold_qty,
                unit=item.unit,
                sourceSystem=item.source_system,
                sourceRecordRef=item.source_record_ref,
                syncJobId=item.sync_job_id,
            )
            for item in page_items
        ],
        pagination=pagination,
    )


@router.get("/consumption-snapshots", response_model=ConsumptionSnapshotListResponse)
def list_consumption_snapshots(
    material_id: str | None = Query(default=None, alias="materialId"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
) -> ConsumptionSnapshotListResponse:
    records = filter_by_material(
        internal_data_store.list_consumption(user.workspace_id),
        material_id=material_id,
        material_external_code=None,
        workspace_id=user.workspace_id,
    )
    page_items, pagination = paginate(records, page, page_size)
    return ConsumptionSnapshotListResponse(
        data=[
            ConsumptionSnapshotResponse(
                id=item.id,
                material=material_reference(resolve_material(user.workspace_id, item.material_id)),
                bucketDate=item.bucket_date,
                actualQty=item.actual_qty,
                plannedQty=item.planned_qty,
                unit=item.unit,
                sourceSystem=item.source_system,
                sourceRecordRef=item.source_record_ref,
                syncJobId=item.sync_job_id,
            )
            for item in page_items
        ],
        pagination=pagination,
    )


@router.get("/material-demands", response_model=MaterialDemandListResponse)
def list_material_demands(
    material_id: str | None = Query(default=None, alias="materialId"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
) -> MaterialDemandListResponse:
    records = filter_by_material(
        internal_data_store.list_demands(user.workspace_id),
        material_id=material_id,
        material_external_code=None,
        workspace_id=user.workspace_id,
    )
    page_items, pagination = paginate(records, page, page_size)
    return MaterialDemandListResponse(
        data=[
            MaterialDemandResponse(
                id=item.id,
                material=material_reference(resolve_material(user.workspace_id, item.material_id)),
                requiredAt=item.required_at,
                requiredQty=item.required_qty,
                unit=item.unit,
                sourceType=item.source_type,
                sourceSystem=item.source_system,
                sourceRecordRef=item.source_record_ref,
                syncJobId=item.sync_job_id,
            )
            for item in page_items
        ],
        pagination=pagination,
    )


@router.get("/open-supply-snapshots", response_model=OpenSupplySnapshotListResponse)
def list_open_supply_snapshots(
    material_id: str | None = Query(default=None, alias="materialId"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
) -> OpenSupplySnapshotListResponse:
    records = filter_by_material(
        internal_data_store.list_open_supply(user.workspace_id),
        material_id=material_id,
        material_external_code=None,
        workspace_id=user.workspace_id,
    )
    page_items, pagination = paginate(records, page, page_size)
    return OpenSupplySnapshotListResponse(
        data=[
            OpenSupplySnapshotResponse(
                id=item.id,
                material=material_reference(resolve_material(user.workspace_id, item.material_id)),
                orderNo=item.order_no,
                orderLineNo=item.order_line_no,
                orderedQty=item.ordered_qty,
                receivedQty=item.received_qty,
                openQty=item.open_qty,
                unit=item.unit,
                expectedAt=item.expected_at,
                status=item.status,
                sourceSystem=item.source_system,
                sourceRecordRef=item.source_record_ref,
                syncJobId=item.sync_job_id,
            )
            for item in page_items
        ],
        pagination=pagination,
    )
