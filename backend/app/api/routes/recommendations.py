from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Header, Query, Response, status
from pydantic import BaseModel, Field, model_validator

from app.core.auth import User, get_current_user
from app.core.errors import api_error
from app.core.recommendations import (
    DecisionType,
    GenerationResult,
    InvalidAdjustmentError,
    PlanningEngine,
    ProcurementRecommendation,
    RecommendationDecision,
    RecommendationVersionConflictError,
)
from app.core.stores import (
    agent_service,
    catalog_store,
    internal_data_store,
    monitoring_store,
    recommendation_store,
)

router = APIRouter(prefix="/api/v1/procurement-recommendations", tags=["recommendations"])


class Pagination(BaseModel):
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class CalculationResponse(BaseModel):
    availableQty: float
    demandQty: float
    openSupplyQty: float
    safetyStockQty: float
    consumptionDailyQty: float
    leadTimeDays: int
    projectedBalanceQty: float


class AlgorithmResponse(BaseModel):
    key: str
    version: str


class RecommendationResponse(BaseModel):
    id: str
    materialId: str
    asOfDate: date
    horizonEnd: date
    recommendedOrderDate: date
    latestOrderDate: date
    recommendedQty: float
    unit: str
    riskLevel: str
    reasonCodes: list[str]
    calculation: CalculationResponse
    explanation: str
    inputDigest: str
    algorithm: AlgorithmResponse
    evidenceRefs: list[str]
    externalSignalIds: list[str]
    status: str
    version: int
    createdAt: datetime
    updatedAt: datetime


class RecommendationListResponse(BaseModel):
    data: list[RecommendationResponse]
    pagination: Pagination


class GenerateRequest(BaseModel):
    asOfDate: date
    horizonDays: int = Field(default=30, ge=1, le=365)


class GenerateResponse(BaseModel):
    recommendations: list[RecommendationResponse]
    skipped: list[dict[str, str]]
    replayed: bool


class DecideRequest(BaseModel):
    decision: DecisionType
    adjustedOrderDate: date | None = None
    adjustedQty: float | None = Field(default=None, ge=0)
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_adjustment(self) -> "DecideRequest":
        if self.decision == DecisionType.ADJUST and self.adjustedOrderDate is None and self.adjustedQty is None:
            raise ValueError("An adjusted date or quantity is required for ADJUST.")
        if self.decision != DecisionType.ADJUST and (
            self.adjustedOrderDate is not None or self.adjustedQty is not None
        ):
            raise ValueError("Adjusted values are only valid for ADJUST.")
        return self


class DecisionResponse(BaseModel):
    id: str
    recommendationId: str
    decision: str
    adjustedOrderDate: date | None
    adjustedQty: float | None
    reason: str
    actorId: str
    createdAt: datetime


class DecisionResultResponse(BaseModel):
    recommendation: RecommendationResponse
    decision: DecisionResponse


class DecisionListResponse(BaseModel):
    data: list[DecisionResponse]


def get_planning_engine() -> PlanningEngine:
    return PlanningEngine(
        catalog_store,
        internal_data_store,
        monitoring_store,
        recommendation_store,
        agent_service,
    )


def recommendation_response(item: ProcurementRecommendation) -> RecommendationResponse:
    calculation = item.calculation
    return RecommendationResponse(
        id=item.id,
        materialId=item.material_id,
        asOfDate=item.as_of_date,
        horizonEnd=item.horizon_end,
        recommendedOrderDate=item.recommended_order_date,
        latestOrderDate=item.latest_order_date,
        recommendedQty=item.recommended_qty,
        unit=item.unit,
        riskLevel=item.risk_level.value,
        reasonCodes=list(item.reason_codes),
        calculation=CalculationResponse(
            availableQty=calculation.available_qty,
            demandQty=calculation.demand_qty,
            openSupplyQty=calculation.open_supply_qty,
            safetyStockQty=calculation.safety_stock_qty,
            consumptionDailyQty=calculation.consumption_daily_qty,
            leadTimeDays=calculation.lead_time_days,
            projectedBalanceQty=calculation.projected_balance_qty,
        ),
        explanation=item.explanation,
        inputDigest=item.input_digest,
        algorithm=AlgorithmResponse(key=item.algorithm_key, version=item.algorithm_version),
        evidenceRefs=list(item.evidence_refs),
        externalSignalIds=list(item.external_signal_ids),
        status=item.status.value,
        version=item.version,
        createdAt=item.created_at,
        updatedAt=item.updated_at,
    )


def decision_response(item: RecommendationDecision) -> DecisionResponse:
    return DecisionResponse(
        id=item.id,
        recommendationId=item.recommendation_id,
        decision=item.decision.value,
        adjustedOrderDate=item.adjusted_order_date,
        adjustedQty=item.adjusted_qty,
        reason=item.reason,
        actorId=item.actor_id,
        createdAt=item.created_at,
    )


@router.post("/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_recommendations(
    payload: GenerateRequest,
    response: Response,
    user: User = Depends(get_current_user),
    engine: PlanningEngine = Depends(get_planning_engine),
) -> GenerateResponse:
    result: GenerationResult = engine.generate(
        user.workspace_id,
        payload.asOfDate,
        payload.horizonDays,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return GenerateResponse(
        recommendations=[recommendation_response(item) for item in result.recommendations],
        skipped=result.skipped,
        replayed=result.replayed,
    )


@router.get("", response_model=RecommendationListResponse)
def list_recommendations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
) -> RecommendationListResponse:
    risk_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    records = sorted(
        recommendation_store.list(user.workspace_id),
        key=lambda item: (
            risk_rank[item.risk_level.value],
            item.latest_order_date,
            item.id,
        ),
    )
    start = (page - 1) * page_size
    total = len(records)
    return RecommendationListResponse(
        data=[recommendation_response(item) for item in records[start : start + page_size]],
        pagination=Pagination(
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=(total + page_size - 1) // page_size if total else 0,
        ),
    )


@router.get("/{recommendation_id}", response_model=RecommendationResponse)
def get_recommendation(
    recommendation_id: str,
    user: User = Depends(get_current_user),
) -> RecommendationResponse:
    item = recommendation_store.get(user.workspace_id, recommendation_id)
    if item is None:
        raise api_error(404, "RECOMMENDATION_NOT_FOUND", "Recommendation was not found.")
    return recommendation_response(item)


@router.get("/{recommendation_id}/decisions", response_model=DecisionListResponse)
def list_recommendation_decisions(
    recommendation_id: str,
    user: User = Depends(get_current_user),
) -> DecisionListResponse:
    item = recommendation_store.get(user.workspace_id, recommendation_id)
    if item is None:
        raise api_error(404, "RECOMMENDATION_NOT_FOUND", "Recommendation was not found.")
    return DecisionListResponse(
        data=[
            decision_response(decision)
            for decision in recommendation_store.list_decisions(recommendation_id)
        ]
    )


@router.post(
    "/{recommendation_id}/decisions",
    response_model=DecisionResultResponse,
    status_code=status.HTTP_201_CREATED,
)
def decide_recommendation(
    recommendation_id: str,
    payload: DecideRequest,
    if_match: str = Header(alias="If-Match"),
    user: User = Depends(get_current_user),
    engine: PlanningEngine = Depends(get_planning_engine),
) -> DecisionResultResponse:
    try:
        expected_version = int(if_match.strip().strip('"'))
        if expected_version < 1:
            raise ValueError
    except ValueError as exc:
        raise api_error(422, "VERSION_INVALID", "If-Match must contain a positive version.") from exc
    try:
        recommendation, decision = engine.decide(
            user.workspace_id,
            recommendation_id,
            payload.decision,
            user.id,
            payload.reason.strip(),
            expected_version,
            payload.adjustedOrderDate,
            payload.adjustedQty,
        )
    except LookupError as exc:
        raise api_error(404, "RECOMMENDATION_NOT_FOUND", "Recommendation was not found.") from exc
    except InvalidAdjustmentError as exc:
        raise api_error(422, "ADJUSTMENT_UNCHANGED", str(exc)) from exc
    except RecommendationVersionConflictError as exc:
        raise api_error(409, "VERSION_CONFLICT", str(exc)) from exc
    return DecisionResultResponse(
        recommendation=recommendation_response(recommendation),
        decision=decision_response(decision),
    )
