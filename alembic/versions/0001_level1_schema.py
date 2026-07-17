"""Create Level 1 diagnostic tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_level1"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "student_attempts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("student_id", sa.String(128), nullable=False),
        sa.Column("question_id", sa.String(128)),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("answer_choices", sa.JSON()),
        sa.Column("official_explanation", sa.Text()),
        sa.Column("declared_domain", sa.String(64)),
        sa.Column("declared_skill", sa.String(128)),
        sa.Column("declared_subskill", sa.String(128)),
        sa.Column("difficulty", sa.String(16)),
        sa.Column("student_answer", sa.Text(), nullable=False),
        sa.Column("work_text", sa.Text()),
        sa.Column("student_confidence", sa.Integer()),
        sa.Column("time_spent_seconds", sa.Integer()),
        sa.Column("deterministic_correct", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_student_attempts_student_id", "student_attempts", ["student_id"])
    op.create_table(
        "diagnostic_results",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("attempt_id", sa.String(32), sa.ForeignKey("student_attempts.id"), nullable=False, unique=True),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("skill", sa.String(128), nullable=False),
        sa.Column("subskill", sa.String(128)),
        sa.Column("error_category", sa.String(64), nullable=False),
        sa.Column("error_subcategory", sa.String(64), nullable=False),
        sa.Column("affected_skill", sa.String(128), nullable=False),
        sa.Column("error_step", sa.Integer()),
        sa.Column("observed_evidence", sa.JSON(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("alternative_diagnoses", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("confidence_breakdown", sa.JSON(), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column("review_reason", sa.Text()),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("raw_model_output", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_diagnostic_results_attempt_id", "diagnostic_results", ["attempt_id"])
    op.create_table(
        "diagnostic_feedback",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("diagnostic_id", sa.String(32), sa.ForeignKey("diagnostic_results.id"), nullable=False),
        sa.Column("reviewer_id", sa.String(128), nullable=False),
        sa.Column("reviewer_type", sa.String(32), nullable=False),
        sa.Column("is_accurate", sa.Boolean(), nullable=False),
        sa.Column("corrected_error_category", sa.String(64)),
        sa.Column("corrected_error_subcategory", sa.String(64)),
        sa.Column("feedback_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_diagnostic_feedback_diagnostic_id", "diagnostic_feedback", ["diagnostic_id"])

def downgrade():
    op.drop_table("diagnostic_feedback")
    op.drop_table("diagnostic_results")
    op.drop_table("student_attempts")
