from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.diagnostic import nid


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("code", name="uq_skills_code"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: nid("skill"))
    code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("skills.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    parent: Mapped["Skill | None"] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list["Skill"]] = relationship(back_populates="parent")


class SkillRelationship(Base):
    __tablename__ = "skill_relationships"
    __table_args__ = (
        UniqueConstraint("source_skill_id", "target_skill_id", "relationship_type", name="uq_skill_relationship"),
        CheckConstraint("weight > 0 AND weight <= 1", name="ck_skill_relationship_weight"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: nid("rel"))
    source_skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    target_skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    source_skill: Mapped[Skill] = relationship(foreign_keys=[source_skill_id])
    target_skill: Mapped[Skill] = relationship(foreign_keys=[target_skill_id])


class StudentSkillMastery(Base):
    __tablename__ = "student_skill_mastery"
    __table_args__ = (
        UniqueConstraint("student_id", "skill_id", name="uq_student_skill_mastery"),
        CheckConstraint("mastery_score >= 0 AND mastery_score <= 1", name="ck_mastery_score"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_mastery_confidence"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: nid("mastery"))
    student_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    skill: Mapped[Skill] = relationship()


class MasteryEvent(Base):
    __tablename__ = "mastery_events"
    __table_args__ = (UniqueConstraint("evidence_type", "source_id", "skill_id", name="uq_mastery_event_source"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: nid("evt"))
    student_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_weight: Mapped[float] = mapped_column(Float, nullable=False)
    previous_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_delta: Mapped[float] = mapped_column(Float, nullable=False)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    skill: Mapped[Skill] = relationship()
