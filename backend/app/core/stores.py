from __future__ import annotations

from app.core.catalog import InMemoryCatalogStore
from app.core.agents import AgentService, InMemoryAgentRunStore, MaterialMonitoringWorkflow
from app.core.config import get_settings
from app.core.internal_data import InMemoryInternalDataStore
from app.core.monitoring import InMemoryMonitoringStore
from app.core.recommendations import InMemoryRecommendationStore
from app.core.reports import InMemoryReportStore


def build_stores():
    settings = get_settings()
    if settings.storage_backend.casefold() != "mysql":
        return (
            InMemoryCatalogStore(),
            InMemoryInternalDataStore(),
            InMemoryMonitoringStore(),
            InMemoryRecommendationStore(),
            InMemoryReportStore(),
        )

    from app.persistence.database import get_database_engine, initialize_database
    from app.persistence.stores import (
        SqlAlchemyCatalogStore,
        SqlAlchemyInternalDataStore,
        SqlAlchemyMonitoringStore,
        SqlAlchemyRecommendationStore,
        SqlAlchemyReportStore,
    )

    engine = get_database_engine()
    if settings.auto_create_schema and settings.app_env != "production":
        initialize_database(engine)
    return (
        SqlAlchemyCatalogStore(engine),
        SqlAlchemyInternalDataStore(engine),
        SqlAlchemyMonitoringStore(engine),
        SqlAlchemyRecommendationStore(engine),
        SqlAlchemyReportStore(engine),
    )


catalog_store, internal_data_store, monitoring_store, recommendation_store, report_store = build_stores()


def build_agent_service() -> AgentService:
    settings = get_settings()
    if settings.storage_backend.casefold() == "mysql":
        from app.persistence.agent_store import SqlAlchemyAgentRunStore
        from app.persistence.database import get_database_engine

        run_store = SqlAlchemyAgentRunStore(get_database_engine())
    else:
        run_store = InMemoryAgentRunStore()
    api_key = settings.deepseek_api_key.get_secret_value() if settings.deepseek_api_key else None
    workflow = MaterialMonitoringWorkflow(
        api_key=api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
    return AgentService(run_store, workflow)


agent_service = build_agent_service()
