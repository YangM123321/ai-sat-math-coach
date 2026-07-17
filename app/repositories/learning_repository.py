from sqlalchemy import func, select
from app.models.knowledge import Skill, SkillRelationship, StudentSkillMastery
from app.models.learning import LearningActivity, LearningPlan

class LearningRepository:
    def __init__(self, db): self.db = db

    def list_skills(self):
        return list(self.db.scalars(select(Skill).where(Skill.active.is_(True)).order_by(Skill.code)).all())

    def list_masteries(self, student_id):
        return list(self.db.scalars(select(StudentSkillMastery).where(StudentSkillMastery.student_id == student_id)).all())

    def list_relationships(self):
        return list(self.db.scalars(select(SkillRelationship)).all())

    def active_plan(self, student_id):
        return self.db.scalar(select(LearningPlan).where(LearningPlan.student_id == student_id, LearningPlan.status == "active").order_by(LearningPlan.version.desc()))

    def next_version(self, student_id):
        current = self.db.scalar(select(func.max(LearningPlan.version)).where(LearningPlan.student_id == student_id))
        return (current or 0) + 1

    def save_plan(self, plan, activities, old_plan=None):
        if old_plan:
            old_plan.status = "superseded"
            old_plan.superseded_by_id = plan.id
        self.db.add(plan)
        self.db.add_all(activities)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def get_plan(self, plan_id): return self.db.get(LearningPlan, plan_id)
    def get_activity(self, activity_id): return self.db.get(LearningActivity, activity_id)

    def save_activity(self, activity):
        self.db.commit(); self.db.refresh(activity); return activity
