from sqlalchemy import select
from app.models.diagnostic import StudentAttempt,DiagnosticResult,DiagnosticFeedback
class Repository:
    def __init__(self,db): self.db=db
    def create_attempt(self,r,correct):
        a=StudentAttempt(student_id=r.student_id,question_text=r.question.question_text,correct_answer=r.question.correct_answer,student_answer=r.student_answer,question_data=r.question.model_dump(mode='json'),work_text=r.work_text,student_confidence=r.student_confidence,time_spent_seconds=r.time_spent_seconds,deterministic_correct=correct); self.db.add(a); self.db.flush(); return a
    def create_result(self,**kw):
        x=DiagnosticResult(**kw); self.db.add(x); self.db.commit(); self.db.refresh(x); return x
    def get(self,i): return self.db.get(DiagnosticResult,i)
    def list_student(self,sid,limit,offset):
        q=select(DiagnosticResult).join(StudentAttempt).where(StudentAttempt.student_id==sid).order_by(DiagnosticResult.created_at.desc()); all_=list(self.db.scalars(q).all()); return all_[offset:offset+limit],len(all_)
    def feedback(self,did,r):
        x=DiagnosticFeedback(diagnostic_id=did,data=r.model_dump(mode='json')); self.db.add(x); self.db.commit(); self.db.refresh(x); return x
