from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.knowledge import MasteryEvent, Skill, SkillRelationship, StudentSkillMastery


class KnowledgeRepository:
    def __init__(self, db):
        self.db = db

    def get_skill_by_code(self, code: str) -> Skill | None:
        return self.db.scalar(select(Skill).where(Skill.code == code))

    def create_skill(self, *, code, name, domain, description, parent_id, active):
        skill = Skill(code=code, name=name, domain=domain, description=description, parent_id=parent_id, active=active)
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        return skill

    def list_skills(self, active_only: bool = True):
        query = select(Skill).order_by(Skill.domain, Skill.code)
        if active_only:
            query = query.where(Skill.active.is_(True))
        return list(self.db.scalars(query).all())

    def create_relationship(self, source: Skill, target: Skill, relationship_type: str, weight: float):
        relationship = SkillRelationship(
            source_skill_id=source.id,
            target_skill_id=target.id,
            relationship_type=relationship_type,
            weight=weight,
        )
        self.db.add(relationship)
        self.db.commit()
        self.db.refresh(relationship)
        return relationship

    def list_relationships(self):
        return list(self.db.scalars(select(SkillRelationship)).all())

    def get_mastery(self, student_id: str, skill_id: str):
        return self.db.scalar(
            select(StudentSkillMastery).where(
                StudentSkillMastery.student_id == student_id,
                StudentSkillMastery.skill_id == skill_id,
            )
        )

    def get_event(self, evidence_type: str, source_id: str, skill_id: str):
        return self.db.scalar(
            select(MasteryEvent).where(
                MasteryEvent.evidence_type == evidence_type,
                MasteryEvent.source_id == source_id,
                MasteryEvent.skill_id == skill_id,
            )
        )

    def save_evidence(self, mastery: StudentSkillMastery, event: MasteryEvent):
        self.db.add(mastery)
        self.db.add(event)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return None
        self.db.refresh(mastery)
        self.db.refresh(event)
        return event

    def list_student_masteries(self, student_id: str):
        query = (
            select(StudentSkillMastery)
            .join(Skill)
            .where(StudentSkillMastery.student_id == student_id)
            .order_by(StudentSkillMastery.mastery_score.asc())
        )
        return list(self.db.scalars(query).all())

    def mastery_count(self, student_id: str) -> int:
        return self.db.scalar(
            select(func.count()).select_from(StudentSkillMastery).where(StudentSkillMastery.student_id == student_id)
        ) or 0
