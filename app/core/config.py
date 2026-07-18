from enum import Enum
from functools import lru_cache
from typing import Annotated
from urllib.parse import parse_qs, urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_INSECURE_SECRET_TOKENS = {
    "changeme", "change-me", "change_me", "secret", "password",
    "insecure", "test", "example", "your-secret-key",
    "development", "dev",
}
_MIN_SECRET_KEY_LENGTH = 32
_MIN_API_KEY_LENGTH = 16

# libpq's own `sslmode` values that guarantee an encrypted connection.
# ("disable"/"allow"/"prefer" are intentionally excluded: "prefer" attempts
# TLS but silently falls back to plaintext, so it doesn't count as explicit.)
_STRICT_SSLMODE_VALUES = {"require", "verify-ca", "verify-full"}

# Other drivers/managed providers (e.g. asyncpg-style DSNs, some cloud
# Postgres offerings) express the same intent with a plain boolean-ish
# parameter instead of `sslmode`. Recognize those too, so this check stays
# portable across drivers rather than being locked to one param name.
_GENERIC_TLS_PARAM_NAMES = {"ssl", "tls", "encrypt"}
_AFFIRMATIVE_TLS_VALUES = {"1", "true", "yes", "on", "require"}


def _is_insecure_secret(value: str) -> bool:
    """True if blank, or containing a known placeholder token anywhere
    (substring, not just exact match) -- catches padding tricks like
    "changeme" repeated to satisfy a minimum-length check."""
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(token in lowered for token in _INSECURE_SECRET_TOKENS)


class Environment(str, Enum):
    """Deployment environment. Only `production` triggers strict startup
    validation below; staging is intentionally not enforced in this baseline
    (see docs/README) and behaves like development/test."""
    development = "development"
    test = "test"
    staging = "staging"
    production = "production"


def _split_csv(value):
    """Allow comma-separated env values (CORS_ALLOWED_ORIGINS=a,b) in addition
    to an already-parsed list, instead of requiring JSON-array syntax."""
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""
    app_name: str = "AI SAT Math Coach"
    environment: Environment = Environment.development
    log_level: str = "INFO"
    debug: bool = False
    database_url: str = "sqlite:///./sat_coach.db"
    diagnostic_provider: str = "rule_based"
    human_review_threshold: float = Field(0.60, ge=0, le=1)
    max_image_bytes: int = Field(5_242_880, ge=1)
    require_api_key: bool = False
    api_key: str | None = None
    secret_key: str | None = None
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    trusted_hosts: Annotated[list[str], NoDecode] = Field(default_factory=list)
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_allowed_origins", "trusted_hosts", mode="before")
    @classmethod
    def _parse_csv_list(cls, value):
        return _split_csv(value)

    @model_validator(mode="after")
    def _refuse_insecure_production_startup(self) -> "Settings":
        if self.environment is not Environment.production:
            return self

        problems: list[str] = []

        secret_key = (self.secret_key or "")
        if len(secret_key.strip()) < _MIN_SECRET_KEY_LENGTH or _is_insecure_secret(secret_key):
            problems.append(
                f"SECRET_KEY must be set to a random value of at least {_MIN_SECRET_KEY_LENGTH} "
                "characters (missing, too short, or a known placeholder)."
            )

        problems.extend(self._database_tls_problems())

        if not self.cors_allowed_origins or "*" in self.cors_allowed_origins:
            problems.append(
                "CORS_ALLOWED_ORIGINS must list one or more explicit origins; it is empty "
                "or contains a wildcard '*'."
            )

        if not self.trusted_hosts or "*" in self.trusted_hosts:
            problems.append(
                "TRUSTED_HOSTS must list one or more explicit hostnames; it is empty or "
                "contains a wildcard '*'."
            )

        if self.debug:
            problems.append("DEBUG must be false in production.")

        if self.require_api_key:
            api_key = (self.api_key or "")
            if len(api_key.strip()) < _MIN_API_KEY_LENGTH or _is_insecure_secret(api_key):
                problems.append(
                    f"API_KEY must be set to a value of at least {_MIN_API_KEY_LENGTH} characters "
                    "(missing, too short, or a known placeholder) because REQUIRE_API_KEY is true."
                )

        if problems:
            joined = "\n  - ".join(problems)
            raise ValueError(
                "Refusing to start with ENVIRONMENT=production due to insecure configuration:"
                f"\n  - {joined}"
            )
        return self

    def _database_tls_problems(self) -> list[str]:
        url = self.database_url.strip()
        if url.lower().startswith("sqlite"):
            return ["DATABASE_URL must not be SQLite in production; a TLS-capable server database is required."]

        if self._database_url_requests_tls(url):
            return []
        return [
            "DATABASE_URL must explicitly enable an encrypted connection -- e.g. "
            "'?sslmode=require' (or 'verify-ca'/'verify-full'), or an equivalent "
            "driver-supported TLS option such as 'ssl=true'; none was found."
        ]

    @staticmethod
    def _database_url_requests_tls(url: str) -> bool:
        """True if the connection string explicitly asks for an encrypted
        connection, via `sslmode` or an equivalent driver-supported TLS
        parameter. Deliberately param-name-agnostic (rather than hardcoding
        every provider's dialect) so legitimate managed-database deployments
        that use a different driver aren't unnecessarily rejected."""
        query = {key.lower(): values for key, values in parse_qs(urlparse(url).query).items()}

        sslmode = next(iter(query.get("sslmode", [])), None)
        if sslmode and sslmode.lower() in _STRICT_SSLMODE_VALUES:
            return True

        for param_name in _GENERIC_TLS_PARAM_NAMES:
            value = next(iter(query.get(param_name, [])), None)
            if value and value.lower() in _AFFIRMATIVE_TLS_VALUES:
                return True

        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
