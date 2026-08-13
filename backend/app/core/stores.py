from __future__ import annotations

from app.core.catalog import InMemoryCatalogStore
from app.core.config import get_settings
from app.core.internal_data import InMemoryInternalDataStore


def build_stores():
    settings = get_settings()
    if settings.storage_backend.casefold() != "mysql":
        return InMemoryCatalogStore(), InMemoryInternalDataStore()

    from app.persistence.database import get_database_engine, initialize_database
    from app.persistence.stores import SqlAlchemyCatalogStore, SqlAlchemyInternalDataStore

    engine = get_database_engine()
    if settings.auto_create_schema and settings.app_env != "production":
        initialize_database(engine)
    return SqlAlchemyCatalogStore(engine), SqlAlchemyInternalDataStore(engine)


catalog_store, internal_data_store = build_stores()
