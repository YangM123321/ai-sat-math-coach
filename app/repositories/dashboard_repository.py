from datetime import date
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from app.models.dashboard import DashboardAccessGrant, ProgressSnapshot
from app.models.diagnostic import DiagnosticResult, StudentAttempt
from app.models.knowledge import StudentSkillMastery
from app.models.learning import LearningActivity, LearningPlan
from app.models.tutor import TutorSession

class DashboardRepository:
    def __init__(self,db): self.db=db
    def save_grant(self,item):
        existing=self.db.scalar(select(DashboardAccessGrant).where(DashboardAccessGrant.viewer_id==item.viewer_id,DashboardAccessGrant.student_id==item.student_id,DashboardAccessGrant.role==item.role))
        if existing:
            existing.active=True; existing.revoked_at=None; existing.created_by=item.created_by; self.db.commit(); self.db.refresh(existing); return existing
        self.db.add(item); self.db.commit(); self.db.refresh(item); return item
    def grants(self,viewer_id,role=None):
        q=select(DashboardAccessGrant).where(DashboardAccessGrant.viewer_id==viewer_id,DashboardAccessGrant.active.is_(True))
        if role:q=q.where(DashboardAccessGrant.role==role)
        return list(self.db.scalars(q.order_by(DashboardAccessGrant.student_id)).all())
    def has_access(self,viewer_id,student_id,role):
        return self.db.scalar(select(DashboardAccessGrant.id).where(DashboardAccessGrant.viewer_id==viewer_id,DashboardAccessGrant.student_id==student_id,DashboardAccessGrant.role==role,DashboardAccessGrant.active.is_(True))) is not None
    def masteries(self,student_id):
        return list(self.db.scalars(select(StudentSkillMastery).options(selectinload(StudentSkillMastery.skill)).where(StudentSkillMastery.student_id==student_id)).all())
    def diagnostic_counts(self,student_id):
        total=self.db.scalar(select(func.count(DiagnosticResult.id)).join(StudentAttempt).where(StudentAttempt.student_id==student_id)) or 0
        correct=self.db.scalar(select(func.count(DiagnosticResult.id)).join(StudentAttempt).where(StudentAttempt.student_id==student_id,StudentAttempt.deterministic_correct.is_(True))) or 0
        return total,correct
    def active_plan(self,student_id):
        return self.db.scalar(select(LearningPlan).options(selectinload(LearningPlan.activities)).where(LearningPlan.student_id==student_id,LearningPlan.status=='active').order_by(LearningPlan.version.desc()))
    def completed_tutor_sessions(self,student_id):
        return self.db.scalar(select(func.count(TutorSession.id)).where(TutorSession.student_id==student_id,TutorSession.status=='completed')) or 0
    def save_snapshot(self,item):
        existing=self.db.scalar(select(ProgressSnapshot).where(ProgressSnapshot.student_id==item.student_id,ProgressSnapshot.snapshot_date==item.snapshot_date))
        if existing:
            for name in ['overall_mastery','mastery_confidence','diagnostic_accuracy','plan_completion_rate','tutor_sessions_completed','weak_skills','strengths']:
                setattr(existing,name,getattr(item,name))
            self.db.commit(); self.db.refresh(existing); return existing
        self.db.add(item); self.db.commit(); self.db.refresh(item); return item
    def snapshots(self,student_id,limit):
        q=select(ProgressSnapshot).where(ProgressSnapshot.student_id==student_id).order_by(ProgressSnapshot.snapshot_date.desc()).limit(limit)
        return list(reversed(list(self.db.scalars(q).all())))
