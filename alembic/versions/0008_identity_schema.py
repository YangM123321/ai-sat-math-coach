"""Create Phase 1.5 identity schema: users and refresh_tokens.

Revision ID: 0008_identity_schema
Revises: 0007_reconcile_diagnostic_schema

Adds the database identity foundation for future authentication and
authorization PRs (Phase 1.5 PR 2B). This migration is schema-only: no
registration, login, JWT issuance, password-hashing service, or route
authorization exists yet. See docs/security/THREAT_MODEL.md for the
threat model this schema is designed against, and app/models/user.py
for field-level rationale.

Design notes
------------
- `email` has a single, case-sensitive UNIQUE constraint (uq_users_email).
  This model/migration performs no normalization (no lowercasing or
  trimming) -- that is authentication/service-layer behavior for a
  later PR, not schema.
- `role` is a plain String constrained by a CHECK constraint, not a
  native PostgreSQL ENUM -- consistent with this codebase's existing
  constrained-value pattern (see ck_mastery_score /
  ck_skill_relationship_weight in 0002_level2_knowledge_model.py) and
  avoiding the CREATE TYPE / DROP TYPE bookkeeping a native enum would
  add to this migration's downgrade path.
- Two temporal CHECK constraints on refresh_tokens guard against
  genuinely impossible states: a token cannot expire at or before its
  own creation, and cannot be revoked before it was created. A
  constraint comparing `revoked_at` directly against `expires_at` was
  considered and deliberately omitted: revoking a token either before or
  after its natural expiry is a legitimate, meaningful state (e.g. an
  incident-response revocation of an already-expired token), so no
  ordering between those two columns alone is actually impossible.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_identity_schema"
down_revision = "0007_reconcile_diagnostic_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="student"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("role IN ('student', 'teacher', 'admin')", name="ck_users_role"),
    )
    op.create_index("ix_users_created_at", "users", ["created_at"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("replaced_by_id", sa.String(32), sa.ForeignKey("refresh_tokens.id")),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        sa.CheckConstraint("expires_at > created_at", name="ck_refresh_tokens_expires_after_created"),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_refresh_tokens_revoked_after_created",
        ),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])


def downgrade():
    op.drop_table("refresh_tokens")
    op.drop_table("users")
