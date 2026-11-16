from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. All values overridable via environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./openbunk.db"
    CORS_ORIGINS: str = "http://localhost:5173"
    ENVIRONMENT: str = "development"
    RATE_LIMIT_PER_MINUTE: int = 20

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.DATABASE_URL.startswith("sqlite"):
        # fail fast: a production deployment must not silently run on a local file database
        raise RuntimeError(
            "ENVIRONMENT=production requires a non-SQLite DATABASE_URL (e.g. postgresql+psycopg://…)"
        )
    return settings
