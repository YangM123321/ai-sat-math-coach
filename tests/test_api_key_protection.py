import os

import pytest

from app.core.config import get_settings

TEST_API_KEY = "test-secret-key"

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
