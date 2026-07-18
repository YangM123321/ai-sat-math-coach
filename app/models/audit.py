"""Security audit event schema (Phase 1.5 PR 5) -- append-only trail.

`audit_events` never stores a password, password hash, raw JWT, or raw
refresh token -- there is no column shaped to hold one, and
`AuditService.record` (app/services/audit_service.py) has no parameter
for one either. `actor_user_id`/`target_user_id` use ON DELETE SET NULL
(not CASCADE): deleting a user must never delete their audit history.
See docs/security/THREAT_MODEL.md (T16) for the rationale.
"""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.diagnostic import nid


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "category IN ('authentication', 'authorization', 'administrative')",
            name="ck_audit_events_category",
        ),
        CheckConstraint(
            "outcome IN ('success', 'failure', 'denied')",
            name="ck_audit_events_outcome",
        ),
        Index("ix_audit_events_created_at", "created_at"),
        Index("ix_audit_events_event_name", "event_name"),
        Index("ix_audit_events_actor_user_id", "actor_user_id"),
        Index("ix_audit_events_target_user_id", "target_user_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: nid("aud"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    target_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
