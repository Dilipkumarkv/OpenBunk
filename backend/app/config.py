import re
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_PASSWORDS = {"postgres", "password", "changeme", "openbunk", "admin", "secret", "123456"}


class Settings(BaseSettings):
    """Runtime configuration. All values overridable via environment variables.

    ENVIRONMENT is deliberately mandatory: a deployment must state what it is so
    the production guards below cannot be skipped by omission.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str
    DATABASE_URL: str = "sqlite:///./openbunk.db"
    CORS_ORIGINS: str = "http://localhost:5173"
    RATE_LIMIT_PER_MINUTE: int = 20
    OPENBUNK_SEED_PIN: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT.lower() == "test"


def _database_password(url: str) -> str | None:
    try:
        parts = urlsplit(url.replace("postgresql+psycopg://", "postgresql://", 1))
    except ValueError:
        return None
    return parts.password


def _validate(settings: Settings) -> Settings:
    environment = settings.ENVIRONMENT.lower()
    if environment not in {"development", "test", "staging", "production"}:
        raise RuntimeError("ENVIRONMENT must be one of development, test, staging, production")

    if settings.is_production and settings.DATABASE_URL.startswith("sqlite"):
        raise RuntimeError(
            "ENVIRONMENT=production requires a non-SQLite DATABASE_URL (e.g. postgresql+psycopg://…)"
        )

    if settings.is_production:
        origins = settings.cors_origin_list
        if not origins or any(o == "*" or not o.startswith("https://") for o in origins):
            raise RuntimeError(
                "ENVIRONMENT=production requires explicit https CORS origins (wildcards are rejected)"
            )
        password = _database_password(settings.DATABASE_URL)
        if not password or len(password) < 12 or password.lower() in _WEAK_PASSWORDS:
            raise RuntimeError(
                "ENVIRONMENT=production requires a database password of at least 12 characters "
                "(not a common default)"
            )
        seed_pin = settings.OPENBUNK_SEED_PIN
        if seed_pin is not None:
            if not re.fullmatch(r"\d{6,}", seed_pin) or seed_pin.lower() in _WEAK_PASSWORDS:
                raise RuntimeError(
                    "OPENBUNK_SEED_PIN must be at least 6 digits and not a demo default in production"
                )
    return settings


@lru_cache
def get_settings() -> Settings:
    return _validate(Settings())
