"""Centralized security audit-event writer (Phase 1.5 PR 5).

`record()` has no parameter shaped to hold a password, password hash,
raw JWT, or raw refresh token -- callers cannot pass one in even by
accident. `metadata` is the one open field; by convention it holds only
a small, non-secret, per-event whitelist of extras (e.g. `revoked_count`,
`viewer_id`, `role`) -- never a request body or credential.

Fail-open by explicit architecture-review decision: a write failure here
must never block the authentication/authorization action it observes.
There is also no ambient per-request transaction tying an audit write to
the business write it accompanies (every repository in this codebase
commits immediately), so fail-closed could not actually undo anything
anyway. See docs/security/THREAT_MODEL.md (T16) for the full rationale.
"""
import logging

from app.middleware.request_context import get_request_context
from app.models.audit import AuditEvent

logger = logging.getLogger("sat_coach.audit_failure")


class AuditService:
    def __init__(self, repository):
        self.repository = repository

    def record(
        self,
        event_name: str,
        *,
        category: str,
        outcome: str,
        actor_user_id: str | None = None,
        target_user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        reason_code: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        context = get_request_context()
        event = AuditEvent(
            event_name=event_name,
            category=category,
            outcome=outcome,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            reason_code=reason_code,
            event_metadata=metadata,
            request_id=context["request_id"],
            ip_address=context["ip_address"],
            user_agent=context["user_agent"],
        )
        try:
            self.repository.save(event)
        except Exception:
            # Fail-open: never let an audit-write failure surface to the
            # caller or block the action it observes. Nothing logged here
            # can be a secret -- see module docstring.
            logger.error("audit_write_failed event_name=%s", event_name, exc_info=True)
