from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Aipaqu API"
    app_version: str = "0.1.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_timezone: str = Field(default="Asia/Shanghai", alias="APP_TIMEZONE")

    mysql_host: str = Field(default="localhost", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    elasticsearch_url: str = Field(
        default="http://localhost:9200",
        alias="ELASTICSEARCH_URL",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

