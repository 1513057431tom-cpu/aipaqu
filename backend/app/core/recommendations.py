from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from threading import RLock
from typing import Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.core.catalog import CatalogStatus, Material
from app.core.monitoring import ReviewStatus

ALGORITHM_KEY = "deterministic-reorder-point"
ALGORITHM_VERSION = "1.0.0"
BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")


class RecommendationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ADJUSTED = "ADJUSTED"
    REJECTED = "REJECTED"


class RiskLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DecisionType(str, Enum):
    APPROVE = "APPROVE"
    ADJUST = "ADJUST"
    REJECT = "REJECT"


class RecommendationVersionConflictError(ValueError):
    pass


class InvalidAdjustmentError(ValueError):
    pass


@dataclass(frozen=True)
class RecommendationCalculation:
    available_qty: float
    demand_qty: float
    open_supply_qty: float
    safety_stock_qty: float
    consumption_daily_qty: float
    lead_time_days: int
    projected_balance_qty: float


@dataclass(frozen=True)
class ProcurementRecommendation:
    id: str
    workspace_id: str
    material_id: str
    as_of_date: date
    horizon_end: date
    recommended_order_date: date
    latest_order_date: date
    recommended_qty: float
    unit: str
    risk_level: RiskLevel
    reason_codes: tuple[str, ...]
    calculation: RecommendationCalculation
    explanation: str
    input_digest: str
    algorithm_key: str
    algorithm_version: str
    evidence_refs: tuple[str, ...]
    external_signal_ids: tuple[str, ...]
    status: RecommendationStatus
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RecommendationDecision:
    id: str
    recommendation_id: str
    decision: DecisionType
    adjusted_order_date: date | None
    adjusted_qty: float | None
    reason: str
    actor_id: str
    created_at: datetime


@dataclass(frozen=True)
class GenerationResult:
    recommendations: list[ProcurementRecommendation]
    skipped: list[dict[str, str]]
    replayed: bool


class RecommendationStore(Protocol):
    def find_by_digest(
        self,
        workspace_id: str,
        material_id: str,
        input_digest: str,
    ) -> ProcurementRecommendation | None: ...

    def save(self, recommendation: ProcurementRecommendation) -> ProcurementRecommendation: ...
    def list(self, workspace_id: str) -> list[ProcurementRecommendation]: ...
    def get(self, workspace_id: str, recommendation_id: str) -> ProcurementRecommendation | None: ...
    def list_decisions(self, recommendation_id: str) -> list[RecommendationDecision]: ...
    def decide(
        self,
        recommendation: ProcurementRecommendation,
        decision: RecommendationDecision,
        expected_version: int,
    ) -> ProcurementRecommendation: ...


class InMemoryRecommendationStore:
    def __init__(self) -> None:
        self._recommendations: dict[str, ProcurementRecommendation] = {}
        self._decisions: dict[str, list[RecommendationDecision]] = {}
        self._lock = RLock()

    def find_by_digest(self, workspace_id: str, material_id: str, input_digest: str) -> ProcurementRecommendation | None:
        with self._lock:
            return next((
                item for item in self._recommendations.values()
                if item.workspace_id == workspace_id
                and item.material_id == material_id
                and item.input_digest == input_digest
            ), None)

    def save(self, recommendation: ProcurementRecommendation) -> ProcurementRecommendation:
        with self._lock:
            self._recommendations[recommendation.id] = recommendation
        return recommendation

    def list(self, workspace_id: str) -> list[ProcurementRecommendation]:
        with self._lock:
            records = [item for item in self._recommendations.values() if item.workspace_id == workspace_id]
        return sorted(records, key=lambda item: (item.risk_level.value, item.latest_order_date, item.id))

    def get(self, workspace_id: str, recommendation_id: str) -> ProcurementRecommendation | None:
        item = self._recommendations.get(recommendation_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_decisions(self, recommendation_id: str) -> list[RecommendationDecision]:
        return list(self._decisions.get(recommendation_id, []))

    def decide(self, recommendation: ProcurementRecommendation, decision: RecommendationDecision, expected_version: int) -> ProcurementRecommendation:
        with self._lock:
            current = self._recommendations.get(recommendation.id)
            if current is None or current.version != expected_version:
                raise RecommendationVersionConflictError("Recommendation version has changed.")
            self._recommendations[recommendation.id] = recommendation
            self._decisions.setdefault(recommendation.id, []).append(decision)
        return recommendation


def _business_date(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BUSINESS_TIMEZONE).date()


def _normalize_number(value: float) -> float:
    return round(value, 6)


class PlanningEngine:
    def __init__(
        self,
        catalog_store,
        internal_data_store,
        monitoring_store,
        recommendation_store: RecommendationStore,
        agent_service=None,
    ) -> None:
        self.catalog_store = catalog_store
        self.internal_data_store = internal_data_store
        self.monitoring_store = monitoring_store
        self.recommendation_store = recommendation_store
        self.agent_service = agent_service

    def generate(self, workspace_id: str, as_of_date: date, horizon_days: int) -> GenerationResult:
        horizon_end = as_of_date + timedelta(days=horizon_days)
        inventory = self.internal_data_store.list_inventory(workspace_id)
        consumption = self.internal_data_store.list_consumption(workspace_id)
        demands = self.internal_data_store.list_demands(workspace_id)
        supplies = self.internal_data_store.list_open_supply(workspace_id)
        signals = self.monitoring_store.list_signals(workspace_id)
        generated: list[ProcurementRecommendation] = []
        skipped: list[dict[str, str]] = []
        replayed_count = 0

        materials = self.catalog_store.list_materials(
            workspace_id,
            status=CatalogStatus.ACTIVE,
        )
        for material in materials:
            material_inventory = [
                item for item in inventory
                if item.material_id == material.id and _business_date(item.snapshot_at) <= as_of_date
            ]
            material_demands = [
                item for item in demands
                if item.material_id == material.id
                and as_of_date <= _business_date(item.required_at) <= horizon_end
            ]
            material_supplies = [
                item for item in supplies
                if item.material_id == material.id
                and as_of_date <= _business_date(item.expected_at) <= horizon_end
                and item.status.casefold() not in {"closed", "cancelled", "canceled"}
            ]
            material_consumption = [
                item for item in consumption
                if item.material_id == material.id
                and as_of_date - timedelta(days=29) <= item.bucket_date <= as_of_date
            ]
            relevant = material_inventory + material_demands + material_supplies + material_consumption
            if not relevant:
                continue
            if not material_inventory:
                skipped.append({"materialId": material.id, "reason": "INVENTORY_MISSING"})
                continue
            latest_inventory = self._latest_inventory_by_location(material_inventory)
            if any(
                _business_date(item.snapshot_at) < as_of_date - timedelta(days=7)
                for item in latest_inventory
            ):
                skipped.append({"materialId": material.id, "reason": "INVENTORY_STALE"})
                continue
            units = {item.unit.casefold() for item in relevant}
            if units != {material.base_unit.casefold()}:
                skipped.append({"materialId": material.id, "reason": "UNIT_CONFLICT"})
                continue
            available_qty = sum(item.available_qty for item in latest_inventory)
            demand_qty = sum(item.required_qty for item in material_demands)
            open_supply_qty = sum(item.open_qty for item in material_supplies)
            consumption_daily_qty = (
                sum(item.actual_qty for item in material_consumption) / len({item.bucket_date for item in material_consumption})
                if material_consumption else 0.0
            )
            forecast_consumption = consumption_daily_qty * horizon_days if not material_demands else 0.0
            effective_demand = max(demand_qty, forecast_consumption)
            minimum_balance, earliest_need = self._minimum_projected_balance(
                available_qty,
                material_demands,
                material_supplies,
                horizon_end,
                forecast_consumption,
                material.safety_stock_qty,
            )
            recommended_qty = max(0.0, material.safety_stock_qty - minimum_balance)
            if not math.isfinite(recommended_qty) or recommended_qty <= 0:
                continue
            latest_order_date = earliest_need - timedelta(days=material.lead_time_days)
            recommended_order_date = max(as_of_date, latest_order_date)
            confirmed_signals = [
                item for item in signals
                if item.material_id == material.id
                and item.review_status == ReviewStatus.CONFIRMED
                and _business_date(item.observed_at) <= as_of_date
            ]
            evidence_refs = tuple(
                [item.id for item in latest_inventory]
                + [item.id for item in material_demands]
                + [item.id for item in material_supplies]
                + [item.id for item in material_consumption]
                + [item.evidence_ref for item in confirmed_signals]
            )
            calculation = RecommendationCalculation(
                available_qty=_normalize_number(available_qty),
                demand_qty=_normalize_number(effective_demand),
                open_supply_qty=_normalize_number(open_supply_qty),
                safety_stock_qty=_normalize_number(material.safety_stock_qty),
                consumption_daily_qty=_normalize_number(consumption_daily_qty),
                lead_time_days=material.lead_time_days,
                projected_balance_qty=_normalize_number(minimum_balance),
            )
            input_digest = self._input_digest(
                material,
                as_of_date,
                horizon_end,
                calculation,
                evidence_refs,
            )
            existing = self.recommendation_store.find_by_digest(
                workspace_id,
                material.id,
                input_digest,
            )
            if existing:
                generated.append(existing)
                replayed_count += 1
                continue
            now = datetime.now(timezone.utc)
            risk_level = self._risk_level(as_of_date, latest_order_date)
            reason_codes = ["PROJECTED_SHORTAGE"]
            if latest_order_date <= as_of_date:
                reason_codes.append("ORDER_DUE")
            if confirmed_signals:
                reason_codes.append("CONFIRMED_EXTERNAL_SIGNAL")
            deterministic_explanation = (
                f"期间需求 {calculation.demand_qty:g} {material.base_unit}，可用库存 "
                f"{calculation.available_qty:g}，按期在途 {calculation.open_supply_qty:g}，"
                f"为保留安全库存 {calculation.safety_stock_qty:g}，建议补充 "
                f"{recommended_qty:g} {material.base_unit}。"
            )
            ai_explanation = self.agent_service.explain_procurement(
                workspace_id,
                {
                    "material": {
                        "id": material.id,
                        "code": material.external_code,
                        "name": material.name,
                        "specification": material.specification,
                    },
                    "rule_calculation": asdict(calculation),
                    "recommended_order_date": recommended_order_date,
                    "latest_order_date": latest_order_date,
                    "recommended_qty": recommended_qty,
                    "unit": material.base_unit,
                    "confirmed_external_intelligence": [
                        {
                            "id": item.id,
                            "summary": item.summary,
                            "rationale": item.analysis_rationale,
                            "confidence": item.confidence,
                            "evidence_ref": item.evidence_ref,
                        }
                        for item in confirmed_signals
                    ],
                    "instruction": "不得修改规则计算出的数量和日期，只解释依据、风险和假设。",
                },
            ) if self.agent_service is not None else None
            recommendation = ProcurementRecommendation(
                id=f"rec_{uuid4().hex}",
                workspace_id=workspace_id,
                material_id=material.id,
                as_of_date=as_of_date,
                horizon_end=horizon_end,
                recommended_order_date=recommended_order_date,
                latest_order_date=latest_order_date,
                recommended_qty=_normalize_number(recommended_qty),
                unit=material.base_unit,
                risk_level=risk_level,
                reason_codes=tuple(reason_codes),
                calculation=calculation,
                explanation=ai_explanation or deterministic_explanation,
                input_digest=input_digest,
                algorithm_key=ALGORITHM_KEY,
                algorithm_version=ALGORITHM_VERSION,
                evidence_refs=evidence_refs,
                external_signal_ids=tuple(item.id for item in confirmed_signals),
                status=RecommendationStatus.PROPOSED,
                version=1,
                created_at=now,
                updated_at=now,
            )
            generated.append(self.recommendation_store.save(recommendation))
        return GenerationResult(
            recommendations=generated,
            skipped=skipped,
            replayed=bool(generated) and replayed_count == len(generated),
        )

    def decide(
        self,
        workspace_id: str,
        recommendation_id: str,
        decision_type: DecisionType,
        actor_id: str,
        reason: str,
        expected_version: int,
        adjusted_order_date: date | None = None,
        adjusted_qty: float | None = None,
    ) -> tuple[ProcurementRecommendation, RecommendationDecision]:
        current = self.recommendation_store.get(workspace_id, recommendation_id)
        if current is None:
            raise LookupError("Recommendation was not found.")
        if decision_type == DecisionType.ADJUST and (
            adjusted_order_date in {None, current.recommended_order_date}
            and adjusted_qty in {None, current.recommended_qty}
        ):
            raise InvalidAdjustmentError("Adjusted date or quantity must change the recommendation.")
        status = {
            DecisionType.APPROVE: RecommendationStatus.APPROVED,
            DecisionType.ADJUST: RecommendationStatus.ADJUSTED,
            DecisionType.REJECT: RecommendationStatus.REJECTED,
        }[decision_type]
        now = datetime.now(timezone.utc)
        decision = RecommendationDecision(
            id=f"decision_{uuid4().hex}",
            recommendation_id=current.id,
            decision=decision_type,
            adjusted_order_date=adjusted_order_date,
            adjusted_qty=adjusted_qty,
            reason=reason,
            actor_id=actor_id,
            created_at=now,
        )
        updated = replace(
            current,
            status=status,
            version=current.version + 1,
            updated_at=now,
        )
        return self.recommendation_store.decide(updated, decision, expected_version), decision

    @staticmethod
    def _latest_inventory_by_location(records):
        latest = {}
        for item in records:
            current = latest.get(item.location_code)
            if current is None or (item.snapshot_at, item.id) > (current.snapshot_at, current.id):
                latest[item.location_code] = item
        return sorted(latest.values(), key=lambda item: item.location_code)

    @staticmethod
    def _minimum_projected_balance(
        available_qty: float,
        demands,
        supplies,
        horizon_end: date,
        forecast_consumption: float,
        safety_stock_qty: float,
    ) -> tuple[float, date]:
        events: list[tuple[date, int, float]] = [
            (_business_date(item.expected_at), 0, item.open_qty)
            for item in supplies
        ]
        events.extend(
            (_business_date(item.required_at), 1, -item.required_qty)
            for item in demands
        )
        if forecast_consumption > 0:
            events.append((horizon_end, 1, -forecast_consumption))
        balance = available_qty
        minimum_balance = balance
        minimum_date = horizon_end
        first_breach_date: date | None = None
        for event_date, _priority, quantity in sorted(events):
            balance += quantity
            if first_breach_date is None and balance < safety_stock_qty:
                first_breach_date = event_date
            if balance < minimum_balance:
                minimum_balance = balance
                minimum_date = event_date
        return minimum_balance, first_breach_date or minimum_date

    @staticmethod
    def _risk_level(as_of_date: date, latest_order_date: date) -> RiskLevel:
        days = (latest_order_date - as_of_date).days
        if days <= 3:
            return RiskLevel.HIGH
        if days <= 7:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _input_digest(material: Material, as_of_date: date, horizon_end: date, calculation: RecommendationCalculation, evidence_refs: tuple[str, ...]) -> str:
        payload = {
            "algorithm": [ALGORITHM_KEY, ALGORITHM_VERSION],
            "asOfDate": as_of_date.isoformat(),
            "calculation": asdict(calculation),
            "evidenceRefs": evidence_refs,
            "horizonEnd": horizon_end.isoformat(),
            "materialId": material.id,
            "unit": material.base_unit,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return f"sha256:{digest}"
