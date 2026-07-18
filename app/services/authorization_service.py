"""Centralized route-level authorization (Phase 1.5 PR 4).

Every domain route derives its access decision from here -- never from a
caller-supplied student_id/viewer_id/role, always from the authenticated
`User` returned by app.api.dependencies.get_current_user (whose role and
is_active are themselves loaded fresh from the database on every
request) plus the trusted DashboardAccessGrant relationship.

Policy for this PR (simple, by explicit architecture-review decision):
- Students: full access (read and write) to their own records.
- Teachers: read-only access to students they have an active grant for.
  Teachers cannot create or modify student-owned records in this PR.
- Admins: full access everywhere.

See docs/security/THREAT_MODEL.md (T6/T7) for the vulnerabilities this
closes.
"""
from app.core.exceptions import Forbidden
from app.models.user import UserRole


class AuthorizationService:
    def __init__(self, dashboard_repository):
        self.dashboard_repository = dashboard_repository

    def ensure_student_read_access(self, current_user, student_id: str) -> None:
        """Self, an assigned teacher, or an admin may read this student's data."""
        if self._is_admin(current_user) or self._is_self(current_user, student_id):
            return
        if self._is_assigned_teacher(current_user, student_id):
            return
        raise Forbidden()

    def ensure_student_write_access(self, current_user, student_id: str) -> None:
        """Only the student themselves or an admin may create/modify this
        student's records. Teachers are deliberately excluded here, even
        with an active grant -- read-only for teachers in this PR."""
        if self._is_admin(current_user) or self._is_self(current_user, student_id):
            return
        raise Forbidden()

    def ensure_admin(self, current_user) -> None:
        if not self._is_admin(current_user):
            raise Forbidden()

    def ensure_self(self, current_user, target_user_id: str) -> None:
        """For 'my own X' routes (e.g. a viewer's own overview) keyed by a
        path-supplied id: the id must match the caller's own, or the
        caller must be an admin."""
        if self._is_admin(current_user) or self._is_self(current_user, target_user_id):
            return
        raise Forbidden()

    @staticmethod
    def _is_admin(current_user) -> bool:
        return current_user.role == UserRole.admin.value

    @staticmethod
    def _is_self(current_user, target_id: str) -> bool:
        return current_user.id == target_id

    def _is_assigned_teacher(self, current_user, student_id: str) -> bool:
        return current_user.role == UserRole.teacher.value and self.dashboard_repository.has_access(
            current_user.id, student_id, UserRole.teacher.value
        )
