from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import String,Text,Integer,Boolean,Float,JSON,DateTime,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column,relationship
from app.db.base import Base

def nid(p): return f'{p}_{uuid4().hex[:16]}'
class StudentAttempt(Base):
    __tablename__='student_attempts'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:nid('att'))
    student_id:Mapped[str]=mapped_column(String,index=True)
    question_text:Mapped[str]=mapped_column(Text); correct_answer:Mapped[str]=mapped_column(Text); student_answer:Mapped[str]=mapped_column(Text)
    question_data:Mapped[dict]=mapped_column(JSON); work_text:Mapped[str|None]=mapped_column(Text,nullable=True)
    student_confidence:Mapped[int|None]=mapped_column(Integer,nullable=True); time_spent_seconds:Mapped[int|None]=mapped_column(Integer,nullable=True)
    deterministic_correct:Mapped[bool]=mapped_column(Boolean); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    diagnostic:Mapped['DiagnosticResult|None']=relationship(back_populates='attempt',uselist=False,cascade='all,delete-orphan')
class DiagnosticResult(Base):
    __tablename__='diagnostic_results'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:nid('diag'))
    attempt_id:Mapped[str]=mapped_column(ForeignKey('student_attempts.id'),unique=True,index=True)
    payload:Mapped[dict]=mapped_column(JSON); confidence:Mapped[float]=mapped_column(Float); confidence_breakdown:Mapped[dict]=mapped_column(JSON)
    requires_human_review:Mapped[bool]=mapped_column(Boolean); review_reason:Mapped[str|None]=mapped_column(Text,nullable=True)
    provider:Mapped[str]=mapped_column(String); prompt_version:Mapped[str]=mapped_column(String); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    attempt:Mapped[StudentAttempt]=relationship(back_populates='diagnostic')
class DiagnosticFeedback(Base):
    __tablename__='diagnostic_feedback'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:nid('fb'))
    diagnostic_id:Mapped[str]=mapped_column(ForeignKey('diagnostic_results.id'),index=True)
    data:Mapped[dict]=mapped_column(JSON); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
