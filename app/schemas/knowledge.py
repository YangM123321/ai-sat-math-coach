from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.schemas.diagnostic import Domain


class RelationshipType(str, Enum):
    prerequisite_of = "prerequisite_of"
    part_of = "part_of"
    related_to = "related_to"


class MasteryStatus(str, Enum):
    not_started = "not_started"
    emerging = "emerging"
    developing = "developing"
    proficient = "proficient"
    mastered = "mastered"


class EvidenceType(str, Enum):
    diagnostic_attempt = "diagnostic_attempt"
    practice_attempt = "practice_attempt"
    teacher_override = "teacher_override"
    import_event = "import_event"


class SkillCreate(BaseModel):
    code: str = Field(min_length=2, max_length=128, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=2, max_length=160)
    domain: Domain
    description: str | None = Field(default=None, max_length=2000)
    parent_code: str | None = Field(default=None, max_length=128)
    active: bool = True


class SkillResponse(SkillCreate):
    id: str
    created_at: datetime


class RelationshipCreate(BaseModel):
    source_skill_code: str
    target_skill_code: str
    relationship_type: RelationshipType
    weight: float = Field(default=1.0, gt=0.0, le=1.0)

    @model_validator(mode="after")
    def reject_self_reference(self):
        if self.source_skill_code == self.target_skill_code:
            raise ValueError("A skill cannot have a relationship to itself")
        return self


class RelationshipResponse(RelationshipCreate):
    id: str
    created_at: datetime


class MasteryEvidenceInput(BaseModel):
    student_id: str = Field(min_length=1, max_length=128)
    skill_code: str = Field(min_length=2, max_length=128)
    evidence_type: EvidenceType
    source_id: str = Field(min_length=1, max_length=128)
    is_correct: bool
    diagnostic_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    difficulty: str = Field(default="medium", pattern=r"^(easy|medium|hard)$")
    error_category: str | None = None
    occurred_at: datetime | None = None


class MasteryEventResponse(BaseModel):
    event_id: str
    student_id: str
    skill_code: str
    previous_score: float
    score_delta: float
    new_score: float
    evidence_weight: float
    created_at: datetime


class SkillMasteryResponse(BaseModel):
    skill_code: str
    skill_name: str
    domain: Domain
    mastery_score: float = Field(ge=0.0, le=1.0)
    status: MasteryStatus
    confidence: float = Field(ge=0.0, le=1.0)
    attempt_count: int
    correct_count: int
    last_evidence_at: datetime | None
    updated_at: datetime


class KnowledgeProfileResponse(BaseModel):
    student_id: str
    overall_mastery: float
    strongest_skills: list[SkillMasteryResponse]
    weakest_skills: list[SkillMasteryResponse]
    skills: list[SkillMasteryResponse]
    generated_at: datetime


class KnowledgeGraphNode(BaseModel):
    code: str
    name: str
    domain: Domain
    mastery_score: float | None = None
    status: MasteryStatus | None = None


class KnowledgeGraphEdge(BaseModel):
    source: str
    target: str
    relationship_type: RelationshipType
    weight: float


class KnowledgeGraphResponse(BaseModel):
    student_id: str
    nodes: list[KnowledgeGraphNode]
    edges: list[KnowledgeGraphEdge]
