from __future__ import annotations

from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine

from app.core.config import Settings, get_settings


def create_mysql_engine(settings: Settings) -> Engine:
    url = URL.create(
        drivername="mysql+pymysql",
        username=settings.mysql_user,
        password=settings.mysql_password,
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_database,
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


@lru_cache
def get_database_engine() -> Engine:
    return create_mysql_engine(get_settings())


def initialize_database(engine: Engine | None = None) -> None:
    from app.persistence.models import Base

    Base.metadata.create_all(engine or get_database_engine())
