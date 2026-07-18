"""Harden dashboard_access_grants with real FKs to users (Phase 1.5 PR 4).

Revision ID: 0009_harden_dashboard_access_grant_fks
Revises: 0008_identity_schema

dashboard_access_grants is reused (beyond the dashboard feature) as the
one persisted teacher-to-student trust relationship for Phase 1.5 PR 4's
route-level authorization: AuthorizationService.ensure_student_read_access
checks it to decide whether an authenticated teacher may read a given
student's data. Before this migration, viewer_id/student_id were plain
strings with no guarantee they referenced real users at all. This
migration adds real foreign keys so the relationship is actually trusted,
not just conventionally named.

created_by is deliberately left as a plain string, not a FK: it is an
audit-trail field, not part of the trust check itself
(AuthorizationService never reads it), so cascading a grant's deletion
off the *creator's* account being deleted later would be the wrong
semantics.

No data migration is included: this assumes no pre-existing
dashboard_access_grants row references a viewer_id/student_id that isn't
a real users.id, which holds for all current dev/test data (no
production deployment exists yet -- see docs/security/THREAT_MODEL.md's
security assumptions). If this migration is ever run against a database
with pre-PR-2B grant rows, it will fail loudly (FK violation) rather than
silently orphan the relationship, which is the correct fail-closed
behavior here.
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_harden_dashboard_access_grant_fks"
down_revision = "0008_identity_schema"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("dashboard_access_grants") as batch_op:
        batch_op.create_foreign_key(
            "fk_dashboard_access_grants_viewer_id_users",
            "users",
            ["viewer_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_dashboard_access_grants_student_id_users",
            "users",
            ["student_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade():
    with op.batch_alter_table("dashboard_access_grants") as batch_op:
        batch_op.drop_constraint("fk_dashboard_access_grants_student_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_dashboard_access_grants_viewer_id_users", type_="foreignkey")
