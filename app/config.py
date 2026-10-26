"""РќР°СЃС‚СЂРѕР№РєРё РїСЂРёР»РѕР¶РµРЅРёСЏ. Р—РЅР°С‡РµРЅРёСЏ Р±РµСЂСѓС‚СЃСЏ РёР· РїРµСЂРµРјРµРЅРЅС‹С… РѕРєСЂСѓР¶РµРЅРёСЏ Рё С„Р°Р№Р»Р° .env."""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8-sig", extra="ignore"
    )

    app_name: str = "AutoMarket Korea API"
    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./automarket.db"
    cors_origins: str = ""
    admin_api_key: str = ""

    local_feed_path: str = ""

    licensed_feed_url: str = ""
    licensed_feed_api_key: str = ""
    licensed_feed_auth_header: str = "Authorization"
    licensed_feed_auth_scheme: str = "Bearer"

    carapis_api_key: str = ""
    auto_load_target: int = 100
    auto_load_interval: int = 600
    auto_load_batch_size: int = 20

    http_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    http_max_attempts: int = Field(default=4, ge=1, le=10)
    http_backoff_seconds: float = Field(default=1.0, ge=0, le=60)

    mark_missing_as_removed: bool = False

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        value = value.strip().upper()
        return value if value in _LOG_LEVELS else "INFO"

    @property
    def sqlalchemy_url(self) -> str:
        """РџСЂРёРІРѕРґРёС‚ Р°РґСЂРµСЃР° РІРёРґР° postgres:// Рє С„РѕСЂРјР°С‚Сѓ SQLAlchemy + psycopg 3."""
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
