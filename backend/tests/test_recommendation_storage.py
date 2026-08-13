from dataclasses import replace
from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.recommendations import (
    DecisionType,
    ProcurementRecommendation,
    RecommendationCalculation,
    RecommendationDecision,
    RecommendationStatus,
    RecommendationVersionConflictError,
    RiskLevel,
)
from app.persistence.models import Base
from app.persistence.stores import SqlAlchemyRecommendationStore


def test_recommendation_and_decision_survive_repository_recreation() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    recommendation = ProcurementRecommendation(
        id="rec-db-1",
        workspace_id="storage-test",
        material_id="material-db-1",
        as_of_date=date(2026, 8, 13),
        horizon_end=date(2026, 9, 12),
        recommended_order_date=date(2026, 8, 13),
        latest_order_date=date(2026, 8, 13),
        recommended_qty=600,
        unit="kg",
        risk_level=RiskLevel.HIGH,
        reason_codes=("PROJECTED_SHORTAGE",),
        calculation=RecommendationCalculation(200, 1000, 300, 100, 0, 7, -500),
        explanation="Deterministic calculation",
        input_digest="sha256:storage-test",
        algorithm_key="deterministic-reorder-point",
        algorithm_version="1.0.0",
        evidence_refs=("inv-1", "dem-1", "supply-1"),
        external_signal_ids=(),
        status=RecommendationStatus.PROPOSED,
        version=1,
        created_at=now,
        updated_at=now,
    )
    decision = RecommendationDecision(
        id="decision-db-1",
        recommendation_id=recommendation.id,
        decision=DecisionType.APPROVE,
        adjusted_order_date=None,
        adjusted_qty=None,
        reason="Reviewed",
        actor_id="user-1",
        created_at=now,
    )
    store = SqlAlchemyRecommendationStore(engine)
    store.save(recommendation)
    approved = replace(
        recommendation,
        status=RecommendationStatus.APPROVED,
        version=2,
    )
    store.decide(approved, decision, expected_version=1)

    recreated = SqlAlchemyRecommendationStore(engine)
    assert recreated.get("storage-test", recommendation.id) == approved
    assert recreated.list_decisions(recommendation.id) == [decision]
    try:
        recreated.decide(approved, decision, expected_version=1)
    except RecommendationVersionConflictError:
        pass
    else:
        raise AssertionError("Expected stale recommendation version to be rejected.")
