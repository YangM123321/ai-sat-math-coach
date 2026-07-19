import os
from contextlib import contextmanager

import pytest

from app.core.config import Environment, Settings, get_settings

VALID_PRODUCTION_ENV = {
    "ENVIRONMENT": "production",
    "SECRET_KEY": "a" * 32,
    "DATABASE_URL": "postgresql+psycopg://user:pass@host:5432/db?sslmode=require",
    "CORS_ALLOWED_ORIGINS": "https://app.example.com",
    "TRUSTED_HOSTS": "api.example.com",
    "DEBUG": "false",
    "REQUIRE_API_KEY": "false",
    "API_KEY": "",
    "RATE_LIMIT_ENABLED": "true",
}


@contextmanager
def env_vars(**overrides):
    """Set the given environment variables for the duration of the block,
    clearing the cached Settings singleton before and after, and restoring
    every prior value (or absence) exactly. Mirrors the pattern already used
    by tests/test_api_key_protection.py::enable_api_key.
    """
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update({key: str(value) for key, value in overrides.items()})
    get_settings.cache_clear()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def _settings(**overrides) -> Settings:
    with env_vars(**overrides):
        return get_settings()


def test_development_boots_with_no_extra_env_vars():
    settings = _settings(ENVIRONMENT="development")
    assert settings.environment is Environment.development
    assert settings.secret_key is None
    assert settings.cors_allowed_origins == []
    assert settings.trusted_hosts == []
    assert settings.debug is False


def test_test_environment_boots_with_no_extra_env_vars():
    settings = _settings(ENVIRONMENT="test")
    assert settings.environment is Environment.test


def test_staging_is_not_enforced_by_production_validation():
    """Staging intentionally gets none of the production startup checks in
    this baseline (see README `Configuration` section)."""
    settings = _settings(
        ENVIRONMENT="staging",
        SECRET_KEY="",
        CORS_ALLOWED_ORIGINS="",
        TRUSTED_HOSTS="",
        DEBUG="true",
    )
    assert settings.environment is Environment.staging


def test_production_boots_when_fully_configured():
    settings = _settings(**VALID_PRODUCTION_ENV)
    assert settings.environment is Environment.production
    assert settings.cors_allowed_origins == ["https://app.example.com"]
    assert settings.trusted_hosts == ["api.example.com"]


@pytest.mark.parametrize(
    "override,expected_message",
    [
        ({"SECRET_KEY": ""}, "SECRET_KEY"),
        ({"SECRET_KEY": "short"}, "SECRET_KEY"),
        ({"SECRET_KEY": "changeme" * 5}, "SECRET_KEY"),
        ({"DATABASE_URL": "sqlite:///./prod.db"}, "DATABASE_URL"),
        (
            {"DATABASE_URL": "postgresql+psycopg://user:pass@host:5432/db"},
            "DATABASE_URL",
        ),
        (
            {"DATABASE_URL": "postgresql+psycopg://user:pass@host:5432/db?sslmode=disable"},
            "DATABASE_URL",
        ),
        (
            {"DATABASE_URL": "postgresql+psycopg://user:pass@host:5432/db?sslmode=prefer"},
            "DATABASE_URL",
        ),
        (
            {"DATABASE_URL": "postgresql+psycopg://user:pass@host:5432/db?ssl=false"},
            "DATABASE_URL",
        ),
        ({"CORS_ALLOWED_ORIGINS": ""}, "CORS_ALLOWED_ORIGINS"),
        ({"CORS_ALLOWED_ORIGINS": "*"}, "CORS_ALLOWED_ORIGINS"),
        ({"CORS_ALLOWED_ORIGINS": "https://a.example.com,*"}, "CORS_ALLOWED_ORIGINS"),
        ({"TRUSTED_HOSTS": ""}, "TRUSTED_HOSTS"),
        ({"TRUSTED_HOSTS": "*"}, "TRUSTED_HOSTS"),
        ({"DEBUG": "true"}, "DEBUG"),
        ({"RATE_LIMIT_ENABLED": "false"}, "RATE_LIMIT_ENABLED"),
    ],
)
def test_production_refuses_individual_violations(override, expected_message):
    env = {**VALID_PRODUCTION_ENV, **override}
    with env_vars(**env):
        get_settings.cache_clear()
        with pytest.raises(ValueError) as exc_info:
            Settings()
    assert expected_message in str(exc_info.value)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://user:pass@host:5432/db?sslmode=require",
        "postgresql+psycopg://user:pass@host:5432/db?sslmode=verify-ca",
        "postgresql+psycopg://user:pass@host:5432/db?sslmode=verify-full",
        "postgresql+psycopg://user:pass@host:5432/db?ssl=true",
        "postgresql+psycopg://user:pass@host:5432/db?tls=1",
        "postgresql+psycopg://user:pass@host:5432/db?encrypt=yes",
        # sslmode is case-insensitive and may appear alongside other params.
        "postgresql+psycopg://user:pass@host:5432/db?connect_timeout=10&sslmode=VERIFY-FULL",
    ],
)
def test_production_accepts_portable_tls_indicators(database_url):
    """The TLS check is param-name-agnostic so legitimate managed-database
    deployments using a different driver's TLS flag aren't rejected just for
    not spelling it `sslmode`."""
    settings = _settings(**{**VALID_PRODUCTION_ENV, "DATABASE_URL": database_url})
    assert settings.database_url == database_url


def test_production_requires_api_key_when_required_flag_is_set():
    env = {**VALID_PRODUCTION_ENV, "REQUIRE_API_KEY": "true", "API_KEY": ""}
    with env_vars(**env):
        get_settings.cache_clear()
        with pytest.raises(ValueError) as exc_info:
            Settings()
    assert "API_KEY" in str(exc_info.value)


def test_production_rejects_placeholder_api_key_when_required():
    env = {**VALID_PRODUCTION_ENV, "REQUIRE_API_KEY": "true", "API_KEY": "changeme"}
    with env_vars(**env):
        get_settings.cache_clear()
        with pytest.raises(ValueError) as exc_info:
            Settings()
    assert "API_KEY" in str(exc_info.value)


def test_production_accepts_strong_api_key_when_required():
    env = {**VALID_PRODUCTION_ENV, "REQUIRE_API_KEY": "true", "API_KEY": "a-sufficiently-long-random-key"}
    settings = _settings(**env)
    assert settings.require_api_key is True


def test_production_does_not_require_api_key_when_flag_is_false():
    env = {**VALID_PRODUCTION_ENV, "REQUIRE_API_KEY": "false", "API_KEY": ""}
    settings = _settings(**env)
    assert settings.require_api_key is False


def test_production_reports_multiple_violations_together():
    env = {
        **VALID_PRODUCTION_ENV,
        "SECRET_KEY": "",
        "CORS_ALLOWED_ORIGINS": "",
        "DEBUG": "true",
    }
    with env_vars(**env):
        get_settings.cache_clear()
        with pytest.raises(ValueError) as exc_info:
            Settings()
    message = str(exc_info.value)
    assert "SECRET_KEY" in message
    assert "CORS_ALLOWED_ORIGINS" in message
    assert "DEBUG" in message


def test_csv_list_fields_trim_whitespace_and_ignore_blank_entries():
    settings = _settings(
        ENVIRONMENT="development",
        CORS_ALLOWED_ORIGINS=" https://a.example.com ,, https://b.example.com,",
        TRUSTED_HOSTS="a.example.com , b.example.com",
    )
    assert settings.cors_allowed_origins == ["https://a.example.com", "https://b.example.com"]
    assert settings.trusted_hosts == ["a.example.com", "b.example.com"]
