from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.diagnostic import nid

class DashboardAccessGrant(Base):
    __tablename__='dashboard_access_grants'
    __table_args__=(UniqueConstraint('viewer_id','student_id','role',name='uq_dashboard_access_grant'),)
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=lambda:nid('grant'))
    viewer_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    student_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    role:Mapped[str]=mapped_column(String(24),nullable=False,index=True)
    active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    created_by:Mapped[str]=mapped_column(String(128),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc))
    revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class ProgressSnapshot(Base):
    __tablename__='progress_snapshots'
    __table_args__=(UniqueConstraint('student_id','snapshot_date',name='uq_progress_snapshot_student_date'),)
    id:Mapped[str]=mapped_column(String(32),primary_key=True,default=lambda:nid('snap'))
    student_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    snapshot_date:Mapped[str]=mapped_column(String(10),nullable=False,index=True)
    overall_mastery:Mapped[float]=mapped_column(Float,nullable=False)
    mastery_confidence:Mapped[float]=mapped_column(Float,nullable=False)
    diagnostic_accuracy:Mapped[float|None]=mapped_column(Float,nullable=True)
    plan_completion_rate:Mapped[float|None]=mapped_column(Float,nullable=True)
    tutor_sessions_completed:Mapped[int]=mapped_column(nullable=False,default=0)
    weak_skills:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    strengths:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    generated_by:Mapped[str]=mapped_column(String(64),nullable=False,default='dashboard-v1.0')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc))
