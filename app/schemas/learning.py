from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field, model_validator

class PlanStatus(str, Enum):
    active = "active"
    superseded = "superseded"
    completed = "completed"
    cancelled = "cancelled"

class ActivityStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    skipped = "skipped"

class ActivityType(str, Enum):
    concept_review = "concept_review"
    guided_practice = "guided_practice"
    independent_practice = "independent_practice"
    mixed_review = "mixed_review"
    checkpoint = "checkpoint"

class LearningPlanCreate(BaseModel):
    student_id: str = Field(min_length=1, max_length=128)
    start_date: date | None = None
    exam_date: date | None = None
    target_score: int | None = Field(default=None, ge=200, le=800)
    daily_minutes: int = Field(default=30, ge=10, le=180)
    duration_days: int = Field(default=7, ge=1, le=30)
    max_focus_skills: int = Field(default=4, ge=1, le=10)

    @model_validator(mode="after")
    def validate_exam_date(self):
        if self.start_date and self.exam_date and self.exam_date < self.start_date:
            raise ValueError("exam_date cannot be before start_date")
        return self

class LearningActivityResponse(BaseModel):
    id: str
    skill_code: str
    skill_name: str
    scheduled_date: date
    sequence: int
    activity_type: ActivityType
    difficulty: str
    estimated_minutes: int
    question_count: int
    rationale: str
    priority_score: float
    status: ActivityStatus
    completed_questions: int
    correct_questions: int

class LearningPlanResponse(BaseModel):
    id: str
    student_id: str
    version: int
    status: PlanStatus
    start_date: date
    end_date: date
    target_score: int | None
    exam_date: date | None
    daily_minutes: int
    algorithm_version: str
    focus_skills: list[str]
    activities: list[LearningActivityResponse]
    created_at: datetime

class LearningActivityUpdate(BaseModel):
    status: ActivityStatus
    completed_questions: int | None = Field(default=None, ge=0)
    correct_questions: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_counts(self):
        if self.completed_questions is not None and self.correct_questions is not None:
            if self.correct_questions > self.completed_questions:
                raise ValueError("correct_questions cannot exceed completed_questions")
        return self
