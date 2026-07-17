"""Create Level 3 personalized learning tables.

Revision ID: 0003_level3
Revises: 0002_level2
"""
from alembic import op
import sqlalchemy as sa
revision="0003_level3"
down_revision="0002_level2"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("learning_plans",
        sa.Column("id",sa.String(32),primary_key=True), sa.Column("student_id",sa.String(128),nullable=False),
        sa.Column("version",sa.Integer(),nullable=False), sa.Column("status",sa.String(24),nullable=False),
        sa.Column("start_date",sa.Date(),nullable=False), sa.Column("end_date",sa.Date(),nullable=False),
        sa.Column("target_score",sa.Integer()), sa.Column("exam_date",sa.Date()), sa.Column("daily_minutes",sa.Integer(),nullable=False),
        sa.Column("algorithm_version",sa.String(64),nullable=False), sa.Column("profile_snapshot",sa.JSON(),nullable=False),
        sa.Column("generation_metadata",sa.JSON(),nullable=False), sa.Column("superseded_by_id",sa.String(32),sa.ForeignKey("learning_plans.id")),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("student_id","version",name="uq_learning_plan_student_version"))
    op.create_index("ix_learning_plans_student_id","learning_plans",["student_id"])
    op.create_index("ix_learning_plans_status","learning_plans",["status"])
    op.create_table("learning_activities",
        sa.Column("id",sa.String(32),primary_key=True), sa.Column("plan_id",sa.String(32),sa.ForeignKey("learning_plans.id",ondelete="CASCADE"),nullable=False),
        sa.Column("skill_id",sa.String(32),sa.ForeignKey("skills.id",ondelete="CASCADE"),nullable=False), sa.Column("scheduled_date",sa.Date(),nullable=False),
        sa.Column("sequence",sa.Integer(),nullable=False), sa.Column("activity_type",sa.String(32),nullable=False), sa.Column("difficulty",sa.String(16),nullable=False),
        sa.Column("estimated_minutes",sa.Integer(),nullable=False), sa.Column("question_count",sa.Integer(),nullable=False), sa.Column("rationale",sa.Text(),nullable=False),
        sa.Column("priority_score",sa.Float(),nullable=False), sa.Column("status",sa.String(24),nullable=False), sa.Column("completed_questions",sa.Integer(),nullable=False),
        sa.Column("correct_questions",sa.Integer(),nullable=False), sa.Column("started_at",sa.DateTime(timezone=True)), sa.Column("completed_at",sa.DateTime(timezone=True)),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_learning_activities_plan_id","learning_activities",["plan_id"])
    op.create_index("ix_learning_activities_skill_id","learning_activities",["skill_id"])
    op.create_index("ix_learning_activities_scheduled_date","learning_activities",["scheduled_date"])
    op.create_index("ix_learning_activities_status","learning_activities",["status"])

def downgrade():
    op.drop_table("learning_activities")
    op.drop_table("learning_plans")
