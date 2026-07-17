"""level6 evaluation and improvement loop
Revision ID: 0006_level6_evaluation_loop
Revises: 0005_level5_dashboards
"""
from alembic import op
import sqlalchemy as sa
revision="0006_level6_evaluation_loop"; down_revision="0005_level5_dashboards"; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("evaluation_runs",
        sa.Column("id",sa.String(32),primary_key=True),sa.Column("name",sa.String(160),nullable=False),
        sa.Column("component",sa.String(64),nullable=False),sa.Column("dataset_version",sa.String(64),nullable=False),
        sa.Column("system_version",sa.String(64),nullable=False),sa.Column("status",sa.String(24),nullable=False),
        sa.Column("total_cases",sa.Integer(),nullable=False),sa.Column("passed_cases",sa.Integer(),nullable=False),
        sa.Column("metrics",sa.JSON(),nullable=False),sa.Column("thresholds",sa.JSON(),nullable=False),
        sa.Column("notes",sa.Text()),sa.Column("started_at",sa.DateTime(timezone=True)),
        sa.Column("completed_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_evaluation_runs_component","evaluation_runs",["component"]); op.create_index("ix_evaluation_runs_status","evaluation_runs",["status"])
    op.create_table("evaluation_case_results",
        sa.Column("id",sa.String(32),primary_key=True),sa.Column("run_id",sa.String(32),nullable=False),
        sa.Column("case_id",sa.String(128),nullable=False),sa.Column("expected",sa.JSON(),nullable=False),
        sa.Column("actual",sa.JSON(),nullable=False),sa.Column("passed",sa.Boolean(),nullable=False),
        sa.Column("score",sa.Float()),sa.Column("failure_reason",sa.Text()),sa.Column("latency_ms",sa.Integer()),
        sa.Column("cost_usd",sa.Float()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("run_id","case_id",name="uq_evaluation_case_run"))
    op.create_index("ix_evaluation_case_results_run_id","evaluation_case_results",["run_id"])
    op.create_table("quality_metric_snapshots",
        sa.Column("id",sa.String(32),primary_key=True),sa.Column("component",sa.String(64),nullable=False),
        sa.Column("metric_name",sa.String(128),nullable=False),sa.Column("metric_value",sa.Float(),nullable=False),
        sa.Column("numerator",sa.Integer()),sa.Column("denominator",sa.Integer()),sa.Column("period_start",sa.String(10),nullable=False),
        sa.Column("period_end",sa.String(10),nullable=False),sa.Column("metadata_json",sa.JSON(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("component","metric_name","period_start","period_end",name="uq_quality_metric_period"))
    for n,c in [("ix_quality_metric_snapshots_component","component"),("ix_quality_metric_snapshots_metric_name","metric_name"),("ix_quality_metric_snapshots_period_start","period_start"),("ix_quality_metric_snapshots_period_end","period_end")]: op.create_index(n,"quality_metric_snapshots",[c])
    op.create_table("improvement_experiments",
        sa.Column("id",sa.String(32),primary_key=True),sa.Column("name",sa.String(160),nullable=False),
        sa.Column("component",sa.String(64),nullable=False),sa.Column("hypothesis",sa.Text(),nullable=False),
        sa.Column("control_version",sa.String(64),nullable=False),sa.Column("treatment_version",sa.String(64),nullable=False),
        sa.Column("primary_metric",sa.String(128),nullable=False),sa.Column("status",sa.String(24),nullable=False),
        sa.Column("allocation_percent",sa.Integer(),nullable=False),sa.Column("guardrails",sa.JSON(),nullable=False),
        sa.Column("result",sa.JSON(),nullable=False),sa.Column("decision",sa.String(24)),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("completed_at",sa.DateTime(timezone=True)))
    op.create_index("ix_improvement_experiments_component","improvement_experiments",["component"]); op.create_index("ix_improvement_experiments_status","improvement_experiments",["status"])

def downgrade():
    op.drop_index("ix_improvement_experiments_status",table_name="improvement_experiments"); op.drop_index("ix_improvement_experiments_component",table_name="improvement_experiments"); op.drop_table("improvement_experiments")
    for n in ["ix_quality_metric_snapshots_period_end","ix_quality_metric_snapshots_period_start","ix_quality_metric_snapshots_metric_name","ix_quality_metric_snapshots_component"]: op.drop_index(n,table_name="quality_metric_snapshots")
    op.drop_table("quality_metric_snapshots"); op.drop_index("ix_evaluation_case_results_run_id",table_name="evaluation_case_results"); op.drop_table("evaluation_case_results")
    op.drop_index("ix_evaluation_runs_status",table_name="evaluation_runs"); op.drop_index("ix_evaluation_runs_component",table_name="evaluation_runs"); op.drop_table("evaluation_runs")
