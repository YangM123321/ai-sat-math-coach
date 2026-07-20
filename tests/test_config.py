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
    "RATE_LIMIT_API_ENABLED": "true",
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
        ({"RATE_LIMIT_API_ENABLED": "false"}, "RATE_LIMIT_API_ENABLED"),
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


# --- General API rate limiting (Phase 1.5 PR 14) ---------------------------


def test_rate_limit_api_defaults():
    settings = _settings(ENVIRONMENT="development")
    assert settings.rate_limit_api_enabled is False
    assert settings.rate_limit_api_perimeter_max_attempts == 300
    assert settings.rate_limit_api_perimeter_window_seconds == 300
    assert settings.rate_limit_api_read_max_attempts == 120
    assert settings.rate_limit_api_read_window_seconds == 60
    assert settings.rate_limit_api_write_max_attempts == 30
    assert settings.rate_limit_api_write_window_seconds == 60
    assert settings.rate_limit_api_expensive_max_attempts == 20
    assert settings.rate_limit_api_expensive_window_seconds == 60
    assert settings.rate_limit_api_admin_max_attempts == 60
    assert settings.rate_limit_api_admin_window_seconds == 60
    assert settings.rate_limit_max_stored_keys == 50_000


@pytest.mark.parametrize(
    "field",
    [
        "RATE_LIMIT_API_PERIMETER_MAX_ATTEMPTS",
        "RATE_LIMIT_API_PERIMETER_WINDOW_SECONDS",
        "RATE_LIMIT_API_READ_MAX_ATTEMPTS",
        "RATE_LIMIT_API_READ_WINDOW_SECONDS",
        "RATE_LIMIT_API_WRITE_MAX_ATTEMPTS",
        "RATE_LIMIT_API_WRITE_WINDOW_SECONDS",
        "RATE_LIMIT_API_EXPENSIVE_MAX_ATTEMPTS",
        "RATE_LIMIT_API_EXPENSIVE_WINDOW_SECONDS",
        "RATE_LIMIT_API_ADMIN_MAX_ATTEMPTS",
        "RATE_LIMIT_API_ADMIN_WINDOW_SECONDS",
    ],
)
@pytest.mark.parametrize("bad_value", ["0", "-1"])
def test_rate_limit_api_tier_fields_reject_zero_and_negative(field, bad_value):
    with env_vars(ENVIRONMENT="development", **{field: bad_value}):
        get_settings.cache_clear()
        with pytest.raises(ValueError):
            Settings()


@pytest.mark.parametrize("bad_value", ["0", "-1", "999"])
def test_rate_limit_max_stored_keys_rejects_below_floor(bad_value):
    with env_vars(ENVIRONMENT="development", RATE_LIMIT_MAX_STORED_KEYS=bad_value):
        get_settings.cache_clear()
        with pytest.raises(ValueError):
            Settings()


def test_rate_limit_max_stored_keys_accepts_the_floor():
    settings = _settings(ENVIRONMENT="development", RATE_LIMIT_MAX_STORED_KEYS="1000")
    assert settings.rate_limit_max_stored_keys == 1000


def test_rate_limit_api_enabled_is_independent_from_rate_limit_enabled():
    """Disabling one must leave the other's setting value intact --
    the two flags are read from entirely separate env vars."""
    both_off = _settings(ENVIRONMENT="development", RATE_LIMIT_ENABLED="false", RATE_LIMIT_API_ENABLED="false")
    assert both_off.rate_limit_enabled is False
    assert both_off.rate_limit_api_enabled is False

    only_pr6 = _settings(ENVIRONMENT="development", RATE_LIMIT_ENABLED="true", RATE_LIMIT_API_ENABLED="false")
    assert only_pr6.rate_limit_enabled is True
    assert only_pr6.rate_limit_api_enabled is False

    only_pr14 = _settings(ENVIRONMENT="development", RATE_LIMIT_ENABLED="false", RATE_LIMIT_API_ENABLED="true")
    assert only_pr14.rate_limit_enabled is False
    assert only_pr14.rate_limit_api_enabled is True


def test_production_requires_rate_limit_api_enabled_independently_of_rate_limit_enabled():
    """RATE_LIMIT_ENABLED=true alone must not satisfy the new
    RATE_LIMIT_API_ENABLED requirement, and vice versa -- both production
    checks below run to completion."""
    env = {**VALID_PRODUCTION_ENV, "RATE_LIMIT_ENABLED": "true", "RATE_LIMIT_API_ENABLED": "false"}
    with env_vars(**env):
        get_settings.cache_clear()
        with pytest.raises(ValueError) as exc_info:
            Settings()
    assert "RATE_LIMIT_API_ENABLED" in str(exc_info.value)
    assert "RATE_LIMIT_ENABLED must be true" not in str(exc_info.value)

    env = {**VALID_PRODUCTION_ENV, "RATE_LIMIT_ENABLED": "false", "RATE_LIMIT_API_ENABLED": "true"}
    with env_vars(**env):
        get_settings.cache_clear()
        with pytest.raises(ValueError) as exc_info:
            Settings()
    assert "RATE_LIMIT_ENABLED must be true" in str(exc_info.value)


def test_csv_list_fields_trim_whitespace_and_ignore_blank_entries():
    settings = _settings(
        ENVIRONMENT="development",
        CORS_ALLOWED_ORIGINS=" https://a.example.com ,, https://b.example.com,",
        TRUSTED_HOSTS="a.example.com , b.example.com",
    )
    assert settings.cors_allowed_origins == ["https://a.example.com", "https://b.example.com"]
    assert settings.trusted_hosts == ["a.example.com", "b.example.com"]
