from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.diagnostic import nid

class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: nid("eval"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    component: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    system_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    thresholds: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class EvaluationCaseResult(Base):
    __tablename__ = "evaluation_case_results"
    __table_args__ = (UniqueConstraint("run_id", "case_id", name="uq_evaluation_case_run"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: nid("case"))
    run_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    expected: Mapped[dict] = mapped_column(JSON, nullable=False)
    actual: Mapped[dict] = mapped_column(JSON, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class QualityMetricSnapshot(Base):
    __tablename__ = "quality_metric_snapshots"
    __table_args__ = (UniqueConstraint("component", "metric_name", "period_start", "period_end", name="uq_quality_metric_period"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: nid("metric"))
    component: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    numerator: Mapped[int | None] = mapped_column(Integer, nullable=True)
    denominator: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_start: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    period_end: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class ImprovementExperiment(Base):
    __tablename__ = "improvement_experiments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: nid("exp"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    component: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    control_version: Mapped[str] = mapped_column(String(64), nullable=False)
    treatment_version: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_metric: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", index=True)
    allocation_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    guardrails: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
