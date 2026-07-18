"""Unit tests for the centralized AuthorizationService (Phase 1.5 PR 4).

Uses a minimal fake for the dashboard_repository collaborator instead of
a real DB session -- these tests are about the four ensure_* methods'
allow/deny logic in isolation, not persistence.
"""
import pytest

from app.core.exceptions import Forbidden
from app.services.authorization_service import AuthorizationService


class _FakeUser:
    def __init__(self, id, role):
        self.id = id
        self.role = role


class _FakeDashboardRepository:
    def __init__(self, grants=()):
        # grants: set of (viewer_id, student_id, role) tuples considered active
        self._grants = set(grants)

    def has_access(self, viewer_id, student_id, role):
        return (viewer_id, student_id, role) in self._grants


def _service(grants=()):
    return AuthorizationService(_FakeDashboardRepository(grants))


# --- ensure_student_read_access ---------------------------------------------

def test_read_access_allows_self():
    authz = _service()
    authz.ensure_student_read_access(_FakeUser("u1", "student"), "u1")


def test_read_access_denies_a_different_student():
    authz = _service()
    with pytest.raises(Forbidden):
        authz.ensure_student_read_access(_FakeUser("u1", "student"), "u2")


def test_read_access_allows_assigned_teacher():
    authz = _service(grants={("teacher1", "student1", "teacher")})
    authz.ensure_student_read_access(_FakeUser("teacher1", "teacher"), "student1")


def test_read_access_denies_unassigned_teacher():
    authz = _service(grants={("teacher1", "student1", "teacher")})
    with pytest.raises(Forbidden):
        authz.ensure_student_read_access(_FakeUser("teacher1", "teacher"), "student2")


def test_read_access_denies_teacher_role_claim_without_a_real_grant():
    authz = _service()
    with pytest.raises(Forbidden):
        authz.ensure_student_read_access(_FakeUser("teacher1", "teacher"), "student1")


def test_read_access_allows_admin_for_any_student():
    authz = _service()
    authz.ensure_student_read_access(_FakeUser("admin1", "admin"), "anyone")


# --- ensure_student_write_access ---------------------------------------------

def test_write_access_allows_self():
    authz = _service()
    authz.ensure_student_write_access(_FakeUser("u1", "student"), "u1")


def test_write_access_denies_a_different_student():
    authz = _service()
    with pytest.raises(Forbidden):
        authz.ensure_student_write_access(_FakeUser("u1", "student"), "u2")


def test_write_access_denies_assigned_teacher():
    """Policy for this PR: teachers are read-only, even with an active
    grant -- they may not create or modify student-owned records."""
    authz = _service(grants={("teacher1", "student1", "teacher")})
    with pytest.raises(Forbidden):
        authz.ensure_student_write_access(_FakeUser("teacher1", "teacher"), "student1")


def test_write_access_allows_admin():
    authz = _service()
    authz.ensure_student_write_access(_FakeUser("admin1", "admin"), "anyone")


# --- ensure_admin -------------------------------------------------------------

def test_ensure_admin_allows_admin():
    authz = _service()
    authz.ensure_admin(_FakeUser("admin1", "admin"))


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_ensure_admin_denies_non_admin(role):
    authz = _service()
    with pytest.raises(Forbidden):
        authz.ensure_admin(_FakeUser("u1", role))


# --- ensure_self ---------------------------------------------------------------

def test_ensure_self_allows_matching_id():
    authz = _service()
    authz.ensure_self(_FakeUser("u1", "teacher"), "u1")


def test_ensure_self_denies_mismatched_id():
    authz = _service()
    with pytest.raises(Forbidden):
        authz.ensure_self(_FakeUser("u1", "teacher"), "u2")


def test_ensure_self_allows_admin_regardless_of_id():
    authz = _service()
    authz.ensure_self(_FakeUser("admin1", "admin"), "someone-else")
