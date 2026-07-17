from sqlalchemy import func, select
from app.models.knowledge import Skill
from app.models.tutor import TutorFeedback, TutorMessage, TutorSession

class TutorRepository:
    def __init__(self,db): self.db=db
    def skill_by_code(self,code): return self.db.scalar(select(Skill).where(Skill.code==code,Skill.active.is_(True)))
    def save_session(self,session,messages):
        self.db.add(session); self.db.add_all(messages); self.db.commit(); self.db.refresh(session); return session
    def get_session(self,session_id): return self.db.get(TutorSession,session_id)
    def next_sequence(self,session_id):
        value=self.db.scalar(select(func.max(TutorMessage.sequence)).where(TutorMessage.session_id==session_id)); return (value or 0)+1
    def save_messages(self,session,messages):
        self.db.add_all(messages); self.db.commit(); self.db.refresh(session); return session
    def save_feedback(self,feedback): self.db.add(feedback); self.db.commit(); self.db.refresh(feedback); return feedback
