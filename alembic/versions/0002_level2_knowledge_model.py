"""Create Level 2 student knowledge model tables.

Revision ID: 0002_level2
Revises: 0001_level1
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_level2"
down_revision = "0001_level1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "skills",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("code", sa.String(128), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("parent_id", sa.String(32), sa.ForeignKey("skills.id")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_skills_code"),
    )
    op.create_index("ix_skills_code", "skills", ["code"])
    op.create_index("ix_skills_domain", "skills", ["domain"])

    op.create_table(
        "skill_relationships",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("source_skill_id", sa.String(32), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_skill_id", sa.String(32), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("weight > 0 AND weight <= 1", name="ck_skill_relationship_weight"),
        sa.UniqueConstraint("source_skill_id", "target_skill_id", "relationship_type", name="uq_skill_relationship"),
    )
    op.create_index("ix_skill_relationships_source_skill_id", "skill_relationships", ["source_skill_id"])
    op.create_index("ix_skill_relationships_target_skill_id", "skill_relationships", ["target_skill_id"])

    op.create_table(
        "student_skill_mastery",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("student_id", sa.String(128), nullable=False),
        sa.Column("skill_id", sa.String(32), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mastery_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_evidence_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mastery_score >= 0 AND mastery_score <= 1", name="ck_mastery_score"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_mastery_confidence"),
        sa.UniqueConstraint("student_id", "skill_id", name="uq_student_skill_mastery"),
    )
    op.create_index("ix_student_skill_mastery_student_id", "student_skill_mastery", ["student_id"])
    op.create_index("ix_student_skill_mastery_skill_id", "student_skill_mastery", ["skill_id"])

    op.create_table(
        "mastery_events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("student_id", sa.String(128), nullable=False),
        sa.Column("skill_id", sa.String(32), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("error_category", sa.String(64)),
        sa.Column("difficulty", sa.String(16), nullable=False),
        sa.Column("evidence_weight", sa.Float(), nullable=False),
        sa.Column("previous_score", sa.Float(), nullable=False),
        sa.Column("score_delta", sa.Float(), nullable=False),
        sa.Column("new_score", sa.Float(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("evidence_type", "source_id", "skill_id", name="uq_mastery_event_source"),
    )
    op.create_index("ix_mastery_events_student_id", "mastery_events", ["student_id"])
    op.create_index("ix_mastery_events_skill_id", "mastery_events", ["skill_id"])
    op.create_index("ix_mastery_events_source_id", "mastery_events", ["source_id"])


def downgrade():
    op.drop_table("mastery_events")
    op.drop_table("student_skill_mastery")
    op.drop_table("skill_relationships")
    op.drop_table("skills")
