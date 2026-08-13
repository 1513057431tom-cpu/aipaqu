from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from itertools import count
from threading import RLock


class CatalogStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class DuplicateCatalogCodeError(ValueError):
    pass


class DuplicateMaterialGroupCodeError(ValueError):
    pass


@dataclass(frozen=True)
class Material:
    id: str
    workspace_id: str
    external_code: str
    name: str
    specification: str
    category: str
    base_unit: str
    safety_stock_qty: float
    lead_time_days: int
    group_id: str | None
    status: CatalogStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Supplier:
    id: str
    workspace_id: str
    external_code: str
    name: str
    website: str | None
    country: str
    status: CatalogStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MaterialGroup:
    id: str
    workspace_id: str
    code: str
    name: str
    parent_id: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class InMemoryCatalogStore:
    def __init__(self) -> None:
        self._material_sequence = count(1)
        self._supplier_sequence = count(1)
        self._group_sequence = count(1)
        self._materials: dict[str, Material] = {}
        self._suppliers: dict[str, Supplier] = {}
        self._groups: dict[str, MaterialGroup] = {}
        self._lock = RLock()

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
        with self._lock:
            self._ensure_material_code_available(workspace_id, external_code)
            self._ensure_group_exists(workspace_id, group_id)
            now = datetime.now(timezone.utc)
            material = Material(
                id=f"mat_{next(self._material_sequence)}",
                workspace_id=workspace_id,
                external_code=external_code,
                name=name,
                specification=specification,
                category=category,
                base_unit=base_unit,
                safety_stock_qty=safety_stock_qty,
                lead_time_days=lead_time_days,
                group_id=group_id,
                status=CatalogStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            self._materials[material.id] = material
            return material

    def list_materials(
        self,
        workspace_id: str,
        *,
        query: str = "",
        category: str | None = None,
        group_id: str | None = None,
        status: CatalogStatus | None = None,
    ) -> list[Material]:
        normalized_query = query.casefold()
        with self._lock:
            materials = [
                material
                for material in self._materials.values()
                if material.workspace_id == workspace_id
                and (status is None or material.status == status)
                and (category is None or material.category == category)
                and (group_id is None or material.group_id == group_id)
                and (
                    not normalized_query
                    or normalized_query in material.external_code.casefold()
                    or normalized_query in material.name.casefold()
                    or normalized_query in material.specification.casefold()
                )
            ]
        return sorted(materials, key=lambda item: (item.external_code.casefold(), item.id))

    def get_material(self, workspace_id: str, material_id: str) -> Material | None:
        with self._lock:
            material = self._materials.get(material_id)
            if material is None or material.workspace_id != workspace_id:
                return None
            return material

    def get_material_by_external_code(
        self,
        workspace_id: str,
        external_code: str,
    ) -> Material | None:
        normalized_code = external_code.casefold()
        with self._lock:
            return next(
                (
                    material
                    for material in self._materials.values()
                    if material.workspace_id == workspace_id
                    and material.external_code.casefold() == normalized_code
                ),
                None,
            )

    def update_material(self, material: Material) -> Material:
        with self._lock:
            existing = self._materials.get(material.id)
            if existing is None or existing.workspace_id != material.workspace_id:
                raise LookupError("Material was not found.")
            self._ensure_material_code_available(
                material.workspace_id,
                material.external_code,
                exclude_id=material.id,
            )
            self._ensure_group_exists(material.workspace_id, material.group_id)
            self._materials[material.id] = material
            return material

    def create_material_group(
        self,
        *,
        workspace_id: str,
        code: str,
        name: str,
        parent_id: str | None,
        sort_order: int,
    ) -> MaterialGroup:
        with self._lock:
            self._ensure_group_code_available(workspace_id, code)
            self._ensure_group_exists(workspace_id, parent_id)
            now = datetime.now(timezone.utc)
            group = MaterialGroup(
                id=f"grp_{next(self._group_sequence)}",
                workspace_id=workspace_id,
                code=code,
                name=name,
                parent_id=parent_id,
                sort_order=sort_order,
                created_at=now,
                updated_at=now,
            )
            self._groups[group.id] = group
            return group

    def list_material_groups(self, workspace_id: str) -> list[MaterialGroup]:
        with self._lock:
            groups = [group for group in self._groups.values() if group.workspace_id == workspace_id]
        return sorted(groups, key=lambda item: (item.sort_order, item.name.casefold(), item.id))

    def get_material_group(self, workspace_id: str, group_id: str) -> MaterialGroup | None:
        with self._lock:
            group = self._groups.get(group_id)
            if group is None or group.workspace_id != workspace_id:
                return None
            return group

    def count_materials_by_group(self, workspace_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        with self._lock:
            for material in self._materials.values():
                if material.workspace_id == workspace_id and material.group_id:
                    counts[material.group_id] = counts.get(material.group_id, 0) + 1
        return counts

    def create_supplier(
        self,
        *,
        workspace_id: str,
        external_code: str,
        name: str,
        website: str | None,
        country: str,
    ) -> Supplier:
        with self._lock:
            self._ensure_supplier_code_available(workspace_id, external_code)
            now = datetime.now(timezone.utc)
            supplier = Supplier(
                id=f"sup_{next(self._supplier_sequence)}",
                workspace_id=workspace_id,
                external_code=external_code,
                name=name,
                website=website,
                country=country,
                status=CatalogStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            self._suppliers[supplier.id] = supplier
            return supplier

    def list_suppliers(
        self,
        workspace_id: str,
        *,
        query: str = "",
        status: CatalogStatus | None = None,
    ) -> list[Supplier]:
        normalized_query = query.casefold()
        with self._lock:
            suppliers = [
                supplier
                for supplier in self._suppliers.values()
                if supplier.workspace_id == workspace_id
                and (status is None or supplier.status == status)
                and (
                    not normalized_query
                    or normalized_query in supplier.external_code.casefold()
                    or normalized_query in supplier.name.casefold()
                )
            ]
        return sorted(suppliers, key=lambda item: (item.external_code.casefold(), item.id))

    def _ensure_material_code_available(
        self,
        workspace_id: str,
        external_code: str,
        exclude_id: str | None = None,
    ) -> None:
        normalized_code = external_code.casefold()
        if any(
            material.workspace_id == workspace_id
            and material.id != exclude_id
            and material.external_code.casefold() == normalized_code
            for material in self._materials.values()
        ):
            raise DuplicateCatalogCodeError("Material external code already exists.")

    def _ensure_supplier_code_available(self, workspace_id: str, external_code: str) -> None:
        normalized_code = external_code.casefold()
        if any(
            supplier.workspace_id == workspace_id
            and supplier.external_code.casefold() == normalized_code
            for supplier in self._suppliers.values()
        ):
            raise DuplicateCatalogCodeError("Supplier external code already exists.")

    def _ensure_group_exists(self, workspace_id: str, group_id: str | None) -> None:
        if group_id is None:
            return
        group = self._groups.get(group_id)
        if group is None or group.workspace_id != workspace_id:
            raise LookupError("Material group was not found.")

    def _ensure_group_code_available(self, workspace_id: str, code: str) -> None:
        normalized_code = code.casefold()
        if any(
            group.workspace_id == workspace_id and group.code.casefold() == normalized_code
            for group in self._groups.values()
        ):
            raise DuplicateMaterialGroupCodeError("Material group code already exists.")
