from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

class EvaluationComponent(str, Enum):
    diagnostic = "diagnostic"
    mastery = "mastery"
    learning_plan = "learning_plan"
    tutor = "tutor"
    dashboard = "dashboard"

class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class EvaluationCaseInput(BaseModel):
    case_id: str = Field(min_length=1, max_length=128)
    expected: dict
    actual: dict
    score: float | None = Field(default=None, ge=0, le=1)
    latency_ms: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)

class EvaluationRunCreate(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    component: EvaluationComponent
    dataset_version: str = Field(min_length=1, max_length=64)
    system_version: str = Field(min_length=1, max_length=64)
    thresholds: dict[str, float] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)
    cases: list[EvaluationCaseInput] = Field(min_length=1, max_length=10000)

class EvaluationCaseResponse(BaseModel):
    case_id: str
    passed: bool
    score: float | None
    failure_reason: str | None
    latency_ms: int | None
    cost_usd: float | None

class EvaluationRunResponse(BaseModel):
    id: str
    name: str
    component: EvaluationComponent
    dataset_version: str
    system_version: str
    status: RunStatus
    total_cases: int
    passed_cases: int
    metrics: dict[str, float]
    thresholds: dict[str, float]
    cases: list[EvaluationCaseResponse] = []
    created_at: datetime
    completed_at: datetime | None

class MetricSnapshotCreate(BaseModel):
    component: EvaluationComponent
    metric_name: str = Field(min_length=1, max_length=128)
    metric_value: float
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=1)
    period_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    period_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    metadata: dict = Field(default_factory=dict)

class MetricSnapshotResponse(BaseModel):
    id: str
    component: EvaluationComponent
    metric_name: str
    metric_value: float
    numerator: int | None
    denominator: int | None
    period_start: str
    period_end: str
    metadata: dict
    created_at: datetime

class ExperimentCreate(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    component: EvaluationComponent
    hypothesis: str = Field(min_length=10)
    control_version: str
    treatment_version: str
    primary_metric: str
    allocation_percent: int = Field(default=50, ge=1, le=99)
    guardrails: dict[str, float] = Field(default_factory=dict)

class ExperimentResultUpdate(BaseModel):
    control_metric: float
    treatment_metric: float
    sample_size_control: int = Field(ge=1)
    sample_size_treatment: int = Field(ge=1)
    guardrail_violations: list[str] = []
    notes: str | None = None

class ExperimentResponse(BaseModel):
    id: str
    name: str
    component: EvaluationComponent
    hypothesis: str
    control_version: str
    treatment_version: str
    primary_metric: str
    status: str
    allocation_percent: int
    guardrails: dict
    result: dict
    decision: str | None
    created_at: datetime
    completed_at: datetime | None
