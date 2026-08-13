from __future__ import annotations

import csv
import io
from dataclasses import replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.core.auth import User, get_current_user
from app.core.catalog import (
    CatalogStatus,
    DuplicateCatalogCodeError,
    DuplicateMaterialGroupCodeError,
    Material,
    MaterialGroup,
    Supplier,
)
from app.core.errors import api_error
from app.core.stores import catalog_store

router = APIRouter(prefix="/api/v1", tags=["catalog"])

MAX_CSV_BYTES = 5 * 1024 * 1024
ALLOWED_CSV_MEDIA_TYPES = {"text/csv", "application/vnd.ms-excel"}
T = TypeVar("T")


class CatalogEntityType(str, Enum):
    MATERIAL = "MATERIAL"
    SUPPLIER = "SUPPLIER"


class Pagination(BaseModel):
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class CreateMaterialRequest(BaseModel):
    externalCode: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    specification: str = Field(default="", max_length=500)
    category: str = Field(default="", max_length=120)
    baseUnit: str = Field(min_length=1, max_length=32)
    safetyStockQty: float = Field(default=0, ge=0, allow_inf_nan=False)
    leadTimeDays: int = Field(default=0, ge=0, le=3650)
    groupId: str | None = Field(default=None, max_length=64)

    @field_validator("externalCode", "name", "baseUnit")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be blank.")
        return stripped

    @field_validator("specification", "category")
    @classmethod
    def strip_optional_text(cls, value: str) -> str:
        return value.strip()


class UpdateMaterialRequest(BaseModel):
    externalCode: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    specification: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=120)
    baseUnit: str | None = Field(default=None, min_length=1, max_length=32)
    safetyStockQty: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    leadTimeDays: int | None = Field(default=None, ge=0, le=3650)
    groupId: str | None = Field(default=None, max_length=64)

    @field_validator("externalCode", "name", "baseUnit")
    @classmethod
    def strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be blank.")
        return stripped

    @field_validator("specification", "category")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> "UpdateMaterialRequest":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        nullable_fields = {"groupId"}
        if any(
            getattr(self, field_name) is None
            for field_name in self.model_fields_set
            if field_name not in nullable_fields
        ):
            raise ValueError("Updated fields must not be null.")
        return self


class MaterialResponse(BaseModel):
    id: str
    workspaceId: str
    externalCode: str
    name: str
    specification: str
    category: str
    baseUnit: str
    safetyStockQty: float
    leadTimeDays: int
    groupId: str | None
    status: str
    createdAt: datetime
    updatedAt: datetime


class MaterialListResponse(BaseModel):
    data: list[MaterialResponse]
    pagination: Pagination


class CreateMaterialGroupRequest(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    parentId: str | None = Field(default=None, max_length=64)
    sortOrder: int = Field(default=0, ge=0, le=1_000_000)

    @field_validator("code", "name")
    @classmethod
    def strip_group_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be blank.")
        return stripped


class MaterialGroupResponse(BaseModel):
    id: str
    workspaceId: str
    code: str
    name: str
    parentId: str | None
    sortOrder: int
    materialCount: int
    createdAt: datetime
    updatedAt: datetime


class MaterialGroupListResponse(BaseModel):
    data: list[MaterialGroupResponse]


class CreateSupplierRequest(BaseModel):
    externalCode: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    website: AnyHttpUrl | None = None
    country: str = Field(default="", max_length=64)

    @field_validator("externalCode", "name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be blank.")
        return stripped

    @field_validator("country")
    @classmethod
    def strip_country(cls, value: str) -> str:
        return value.strip()


class SupplierResponse(BaseModel):
    id: str
    workspaceId: str
    externalCode: str
    name: str
    website: str | None
    country: str
    status: str
    createdAt: datetime
    updatedAt: datetime


class SupplierListResponse(BaseModel):
    data: list[SupplierResponse]
    pagination: Pagination


class ImportRowError(BaseModel):
    row: int
    code: str
    message: str


class ImportResultResponse(BaseModel):
    jobId: str
    entityType: CatalogEntityType
    status: str
    fileName: str
    totalRows: int
    createdRows: int
    failedRows: int
    errors: list[ImportRowError]


def material_to_response(material: Material) -> MaterialResponse:
    return MaterialResponse(
        id=material.id,
        workspaceId=material.workspace_id,
        externalCode=material.external_code,
        name=material.name,
        specification=material.specification,
        category=material.category,
        baseUnit=material.base_unit,
        safetyStockQty=material.safety_stock_qty,
        leadTimeDays=material.lead_time_days,
        groupId=material.group_id,
        status=material.status.value,
        createdAt=material.created_at,
        updatedAt=material.updated_at,
    )


def material_group_to_response(group: MaterialGroup, material_count: int) -> MaterialGroupResponse:
    return MaterialGroupResponse(
        id=group.id,
        workspaceId=group.workspace_id,
        code=group.code,
        name=group.name,
        parentId=group.parent_id,
        sortOrder=group.sort_order,
        materialCount=material_count,
        createdAt=group.created_at,
        updatedAt=group.updated_at,
    )


def supplier_to_response(supplier: Supplier) -> SupplierResponse:
    return SupplierResponse(
        id=supplier.id,
        workspaceId=supplier.workspace_id,
        externalCode=supplier.external_code,
        name=supplier.name,
        website=supplier.website,
        country=supplier.country,
        status=supplier.status.value,
        createdAt=supplier.created_at,
        updatedAt=supplier.updated_at,
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


def create_material(payload: CreateMaterialRequest, user: User) -> Material:
    try:
        return catalog_store.create_material(
            workspace_id=user.workspace_id,
            external_code=payload.externalCode,
            name=payload.name,
            specification=payload.specification,
            category=payload.category,
            base_unit=payload.baseUnit,
            safety_stock_qty=payload.safetyStockQty,
            lead_time_days=payload.leadTimeDays,
            group_id=payload.groupId,
        )
    except LookupError as exc:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "MATERIAL_GROUP_NOT_FOUND",
            "Material group was not found.",
            {"groupId": payload.groupId},
        ) from exc
    except DuplicateCatalogCodeError as exc:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "MATERIAL_CODE_CONFLICT",
            "A material with this external code already exists.",
            {"externalCode": payload.externalCode},
        ) from exc


def create_supplier(payload: CreateSupplierRequest, user: User) -> Supplier:
    try:
        return catalog_store.create_supplier(
            workspace_id=user.workspace_id,
            external_code=payload.externalCode,
            name=payload.name,
            website=str(payload.website) if payload.website else None,
            country=payload.country,
        )
    except DuplicateCatalogCodeError as exc:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "SUPPLIER_CODE_CONFLICT",
            "A supplier with this external code already exists.",
            {"externalCode": payload.externalCode},
        ) from exc


@router.get("/materials", response_model=MaterialListResponse)
def list_materials(
    q: str = Query(default="", max_length=200),
    category: str | None = Query(default=None, max_length=120),
    group_id: str | None = Query(default=None, alias="groupId", max_length=64),
    item_status: CatalogStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
) -> MaterialListResponse:
    materials = catalog_store.list_materials(
        user.workspace_id,
        query=q.strip(),
        category=category.strip() if category else None,
        group_id=group_id,
        status=item_status,
    )
    page_items, pagination = paginate(materials, page, page_size)
    return MaterialListResponse(
        data=[material_to_response(material) for material in page_items],
        pagination=pagination,
    )


@router.post(
    "/materials",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_material(
    payload: CreateMaterialRequest,
    user: User = Depends(get_current_user),
) -> MaterialResponse:
    return material_to_response(create_material(payload, user))


@router.patch("/materials/{material_id}", response_model=MaterialResponse)
def patch_material(
    material_id: str,
    payload: UpdateMaterialRequest,
    user: User = Depends(get_current_user),
) -> MaterialResponse:
    existing = catalog_store.get_material(user.workspace_id, material_id)
    if existing is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "MATERIAL_NOT_FOUND",
            "Material was not found.",
        )
    fields = payload.model_dump(exclude_unset=True)
    field_names = {
        "externalCode": "external_code",
        "name": "name",
        "specification": "specification",
        "category": "category",
        "baseUnit": "base_unit",
        "safetyStockQty": "safety_stock_qty",
        "leadTimeDays": "lead_time_days",
        "groupId": "group_id",
    }
    changes = {field_names[key]: value for key, value in fields.items()}
    updated = replace(existing, **changes, updated_at=datetime.now(timezone.utc))
    try:
        return material_to_response(catalog_store.update_material(updated))
    except DuplicateCatalogCodeError as exc:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "MATERIAL_CODE_CONFLICT",
            "A material with this external code already exists.",
            {"externalCode": updated.external_code},
        ) from exc
    except LookupError as exc:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "MATERIAL_GROUP_NOT_FOUND",
            "Material group was not found.",
            {"groupId": updated.group_id},
        ) from exc


@router.get("/material-groups", response_model=MaterialGroupListResponse)
def list_material_groups(user: User = Depends(get_current_user)) -> MaterialGroupListResponse:
    groups = catalog_store.list_material_groups(user.workspace_id)
    counts = catalog_store.count_materials_by_group(user.workspace_id)
    return MaterialGroupListResponse(
        data=[material_group_to_response(group, counts.get(group.id, 0)) for group in groups]
    )


@router.post(
    "/material-groups",
    response_model=MaterialGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_material_group(
    payload: CreateMaterialGroupRequest,
    user: User = Depends(get_current_user),
) -> MaterialGroupResponse:
    try:
        group = catalog_store.create_material_group(
            workspace_id=user.workspace_id,
            code=payload.code,
            name=payload.name,
            parent_id=payload.parentId,
            sort_order=payload.sortOrder,
        )
    except DuplicateMaterialGroupCodeError as exc:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "MATERIAL_GROUP_CODE_CONFLICT",
            "A material group with this code already exists.",
            {"code": payload.code},
        ) from exc
    except LookupError as exc:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "PARENT_MATERIAL_GROUP_NOT_FOUND",
            "Parent material group was not found.",
            {"parentId": payload.parentId},
        ) from exc
    return material_group_to_response(group, 0)


@router.get("/suppliers", response_model=SupplierListResponse)
def list_suppliers(
    q: str = Query(default="", max_length=200),
    item_status: CatalogStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
) -> SupplierListResponse:
    suppliers = catalog_store.list_suppliers(
        user.workspace_id,
        query=q.strip(),
        status=item_status,
    )
    page_items, pagination = paginate(suppliers, page, page_size)
    return SupplierListResponse(
        data=[supplier_to_response(supplier) for supplier in page_items],
        pagination=pagination,
    )


@router.post(
    "/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_supplier(
    payload: CreateSupplierRequest,
    user: User = Depends(get_current_user),
) -> SupplierResponse:
    return supplier_to_response(create_supplier(payload, user))


@router.post(
    "/imports",
    response_model=ImportResultResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_catalog_csv(
    entity_type: CatalogEntityType = Form(alias="entityType"),
    file: UploadFile = File(),
    user: User = Depends(get_current_user),
) -> ImportResultResponse:
    file_name = Path(file.filename or "").name
    if Path(file_name).suffix.casefold() != ".csv" or file.content_type not in ALLOWED_CSV_MEDIA_TYPES:
        raise api_error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "UNSUPPORTED_IMPORT_TYPE",
            "Only CSV files are supported for catalog imports.",
        )

    content = await file.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        raise api_error(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "IMPORT_FILE_TOO_LARGE",
            "CSV import file exceeds the 5 MB limit.",
        )
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_CSV_ENCODING",
            "CSV files must use UTF-8 encoding.",
        ) from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    required_headers = (
        {"externalCode", "name", "baseUnit"}
        if entity_type == CatalogEntityType.MATERIAL
        else {"externalCode", "name"}
    )
    actual_headers = set(reader.fieldnames or [])
    missing_headers = sorted(required_headers - actual_headers)
    if missing_headers:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "CSV_HEADERS_MISSING",
            "CSV file is missing required headers.",
            {"missingHeaders": missing_headers},
        )

    total_rows = 0
    created_rows = 0
    errors: list[ImportRowError] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        total_rows += 1
        cleaned_row = {
            key: value.strip()
            for key, value in row.items()
            if key is not None and value is not None and value.strip()
        }
        try:
            if entity_type == CatalogEntityType.MATERIAL:
                payload = CreateMaterialRequest.model_validate(cleaned_row)
                create_material(payload, user)
            else:
                supplier_payload = CreateSupplierRequest.model_validate(cleaned_row)
                create_supplier(supplier_payload, user)
            created_rows += 1
        except ValidationError as exc:
            errors.append(
                ImportRowError(
                    row=row_number,
                    code="VALIDATION_ERROR",
                    message=exc.errors(include_url=False)[0]["msg"],
                )
            )
        except HTTPException as exc:
            if exc.status_code != status.HTTP_409_CONFLICT:
                raise
            errors.append(
                ImportRowError(
                    row=row_number,
                    code="DUPLICATE_EXTERNAL_CODE",
                    message="The external code already exists.",
                )
            )

    if total_rows == 0:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "CSV_HAS_NO_DATA_ROWS",
            "CSV file does not contain any data rows.",
        )

    failed_rows = len(errors)
    result_status = "SUCCEEDED"
    if errors:
        result_status = "SUCCEEDED_WITH_ERRORS" if created_rows else "FAILED"
    return ImportResultResponse(
        jobId=f"imp_{uuid4().hex}",
        entityType=entity_type,
        status=result_status,
        fileName=file_name,
        totalRows=total_rows,
        createdRows=created_rows,
        failedRows=failed_rows,
        errors=errors,
    )
