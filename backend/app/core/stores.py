from __future__ import annotations

from app.core.catalog import InMemoryCatalogStore
from app.core.config import get_settings
from app.core.internal_data import InMemoryInternalDataStore
from app.core.monitoring import InMemoryMonitoringStore
from app.core.recommendations import InMemoryRecommendationStore


def build_stores():
    settings = get_settings()
    if settings.storage_backend.casefold() != "mysql":
        return (
            InMemoryCatalogStore(),
            InMemoryInternalDataStore(),
            InMemoryMonitoringStore(),
            InMemoryRecommendationStore(),
        )

    from app.persistence.database import get_database_engine, initialize_database
    from app.persistence.stores import (
        SqlAlchemyCatalogStore,
        SqlAlchemyInternalDataStore,
        SqlAlchemyMonitoringStore,
        SqlAlchemyRecommendationStore,
    )

    engine = get_database_engine()
    if settings.auto_create_schema and settings.app_env != "production":
        initialize_database(engine)
    return (
        SqlAlchemyCatalogStore(engine),
        SqlAlchemyInternalDataStore(engine),
        SqlAlchemyMonitoringStore(engine),
        SqlAlchemyRecommendationStore(engine),
    )


catalog_store, internal_data_store, monitoring_store, recommendation_store = build_stores()
