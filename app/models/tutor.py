from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.diagnostic import nid

class TutorSession(Base):
    __tablename__='tutor_sessions'
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=lambda:nid('tut'))
    student_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    skill_id:Mapped[str]=mapped_column(ForeignKey('skills.id',ondelete='RESTRICT'),nullable=False,index=True)
    learning_activity_id:Mapped[str|None]=mapped_column(ForeignKey('learning_activities.id',ondelete='SET NULL'),nullable=True,index=True)
    status:Mapped[str]=mapped_column(String(24),nullable=False,default='active',index=True)
    problem_text:Mapped[str]=mapped_column(Text,nullable=False)
    correct_answer:Mapped[str|None]=mapped_column(Text,nullable=True)
    student_answer:Mapped[str|None]=mapped_column(Text,nullable=True)
    student_work:Mapped[str|None]=mapped_column(Text,nullable=True)
    current_step:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    max_hints:Mapped[int]=mapped_column(Integer,nullable=False,default=3)
    hints_used:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    provider:Mapped[str]=mapped_column(String(64),nullable=False)
    policy_version:Mapped[str]=mapped_column(String(64),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    skill=relationship('Skill')
    messages:Mapped[list['TutorMessage']]=relationship(back_populates='session',cascade='all, delete-orphan',order_by='TutorMessage.sequence')
    feedback:Mapped[list['TutorFeedback']]=relationship(back_populates='session',cascade='all, delete-orphan')

class TutorMessage(Base):
    __tablename__='tutor_messages'
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=lambda:nid('msg'))
    session_id:Mapped[str]=mapped_column(ForeignKey('tutor_sessions.id',ondelete='CASCADE'),nullable=False,index=True)
    role:Mapped[str]=mapped_column(String(16),nullable=False)
    content:Mapped[str]=mapped_column(Text,nullable=False)
    strategy:Mapped[str|None]=mapped_column(String(24),nullable=True)
    sequence:Mapped[int]=mapped_column(Integer,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
    session:Mapped[TutorSession]=relationship(back_populates='messages')

class TutorFeedback(Base):
    __tablename__='tutor_feedback'
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=lambda:nid('tfb'))
    session_id:Mapped[str]=mapped_column(ForeignKey('tutor_sessions.id',ondelete='CASCADE'),nullable=False,index=True)
    helpful:Mapped[bool]=mapped_column(Boolean,nullable=False)
    rating:Mapped[int|None]=mapped_column(Integer,nullable=True)
    comment:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
    session:Mapped[TutorSession]=relationship(back_populates='feedback')
