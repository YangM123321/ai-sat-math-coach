import os
import re

import pytest

from app.core.config import get_settings
from app.main import app

TEST_API_KEY = "test-secret-key"

# Paths intentionally exempt from API-key protection. Any route in the app's
# live OpenAPI schema that is neither under /api/v1 nor listed here fails
# test_every_declared_route_is_protected_or_explicitly_public below.
PUBLIC_PATHS = {"/health", "/ready"}

# One representative endpoint per protected router.
PROTECTED_ENDPOINTS = [
    ("GET", "/api/v1/students/stu_check/diagnostics"),
    ("GET", "/api/v1/skills"),
    ("GET", "/api/v1/students/stu_check/active-learning-plan"),
    ("GET", "/api/v1/tutor/sessions/sess_missing"),
    ("GET", "/api/v1/dashboard/viewers/viewer_check/overview"),
    ("GET", "/api/v1/evaluation/runs"),
]


@pytest.fixture
def enable_api_key():
    """Turn on REQUIRE_API_KEY for the duration of a test, restoring prior state after."""
    prev_require = os.environ.get("REQUIRE_API_KEY")
    prev_key = os.environ.get("API_KEY")
    os.environ["REQUIRE_API_KEY"] = "true"
    os.environ["API_KEY"] = TEST_API_KEY
    get_settings.cache_clear()
    try:
        yield TEST_API_KEY
    finally:
        if prev_require is None:
            os.environ.pop("REQUIRE_API_KEY", None)
        else:
            os.environ["REQUIRE_API_KEY"] = prev_require
        if prev_key is None:
            os.environ.pop("API_KEY", None)
        else:
            os.environ["API_KEY"] = prev_key
        get_settings.cache_clear()


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_protected_endpoint_rejects_missing_api_key(client, enable_api_key, method, path):
    r = client.request(method, path)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_API_KEY"


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_protected_endpoint_rejects_incorrect_api_key(client, enable_api_key, method, path):
    r = client.request(method, path, headers={"x-api-key": "wrong-key"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_API_KEY"


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_protected_endpoint_accepts_correct_api_key(client, enable_api_key, method, path):
    r = client.request(method, path, headers={"x-api-key": enable_api_key})
    assert r.status_code != 401


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_protected_endpoint_accessible_when_protection_disabled(client, method, path):
    assert get_settings().require_api_key is False
    r = client.request(method, path)
    assert r.status_code != 401


def test_health_is_public_when_protection_disabled(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_health_is_public_when_protection_enabled(client, enable_api_key):
    r = client.get("/health")
    assert r.status_code == 200


def _concrete_path(openapi_path: str) -> str:
    """Replace OpenAPI {param} placeholders with a harmless dummy segment."""
    return re.sub(r"\{[^}]+\}", "dummy", openapi_path)


def test_every_declared_route_is_protected_or_explicitly_public(client, enable_api_key):
    """
    Guards against the original bug class: a future router registered without
    API-key protection. Walks the app's live OpenAPI schema (not hardcoded
    paths) so it catches any route regardless of how it was wired up.
    """
    paths = app.openapi()["paths"]
    checked = 0
    for path, operations in paths.items():
        if path in PUBLIC_PATHS:
            continue
        assert path.startswith("/api/v1"), (
            f"{path} is neither under /api/v1 nor in PUBLIC_PATHS. "
            "Either register it under the protected_api_router in app/main.py "
            "or explicitly allowlist it as public in PUBLIC_PATHS."
        )
        concrete_path = _concrete_path(path)
        for method in operations:
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            r = client.request(method.upper(), concrete_path)
            assert r.status_code == 401, (
                f"{method.upper()} {path} is not protected by require_api_key "
                f"(expected 401, got {r.status_code})"
            )
            checked += 1
    assert checked > 0, "no /api/v1 routes were found - route discovery may be broken"


def test_public_paths_remain_public_when_protection_enabled(client, enable_api_key):
    for path in PUBLIC_PATHS:
        r = client.get(path)
        assert r.status_code != 401
