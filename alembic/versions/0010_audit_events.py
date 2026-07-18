"""Create Phase 1.5 audit_events table -- security audit logging.

Revision ID: 0010_audit_events
Revises: 0009_harden_grant_fks

Durable, queryable audit trail for authentication, authorization-denial,
and administrative events (Phase 1.5 PR 5). See
docs/security/THREAT_MODEL.md (T16) and app/models/audit.py for
field-level rationale, and app/services/audit_service.py for the write
path.

Design notes
------------
- `actor_user_id`/`target_user_id` use ON DELETE SET NULL, not CASCADE --
  deleting a user must never delete their audit history.
- `category`/`outcome` are plain Strings constrained by CHECK, matching
  this codebase's existing constrained-value pattern (see `role` on
  `users` in 0008_identity_schema.py) rather than a native enum.
- No update/delete surface is added anywhere for this table -- it is
  append-only by application convention (see AuditRepository).
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_audit_events"
down_revision = "0009_harden_grant_fks"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_name", sa.String(64), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(64)),
        sa.Column("actor_user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("target_user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("resource_type", sa.String(32)),
        sa.Column("resource_id", sa.String(64)),
        sa.Column("request_id", sa.String(64)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(256)),
        sa.Column("event_metadata", sa.JSON()),
        sa.CheckConstraint(
            "category IN ('authentication', 'authorization', 'administrative')",
            name="ck_audit_events_category",
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'failure', 'denied')",
            name="ck_audit_events_outcome",
        ),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_events_event_name", "audit_events", ["event_name"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_target_user_id", "audit_events", ["target_user_id"])


def downgrade():
    op.drop_table("audit_events")
