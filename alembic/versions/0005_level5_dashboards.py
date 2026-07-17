"""level5 teacher parent dashboards
Revision ID: 0005_level5_dashboards
Revises: 0004_level4_ai_tutor
"""
from alembic import op
import sqlalchemy as sa
revision='0005_level5_dashboards'; down_revision='0004_level4_ai_tutor'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('dashboard_access_grants',sa.Column('id',sa.String(32),primary_key=True),sa.Column('viewer_id',sa.String(128),nullable=False),sa.Column('student_id',sa.String(128),nullable=False),sa.Column('role',sa.String(24),nullable=False),sa.Column('active',sa.Boolean(),nullable=False),sa.Column('created_by',sa.String(128),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('revoked_at',sa.DateTime(timezone=True)),sa.UniqueConstraint('viewer_id','student_id','role',name='uq_dashboard_access_grant'))
    for name,col in [('ix_dashboard_access_grants_viewer_id','viewer_id'),('ix_dashboard_access_grants_student_id','student_id'),('ix_dashboard_access_grants_role','role')]:op.create_index(name,'dashboard_access_grants',[col])
    op.create_table('progress_snapshots',sa.Column('id',sa.String(32),primary_key=True),sa.Column('student_id',sa.String(128),nullable=False),sa.Column('snapshot_date',sa.String(10),nullable=False),sa.Column('overall_mastery',sa.Float(),nullable=False),sa.Column('mastery_confidence',sa.Float(),nullable=False),sa.Column('diagnostic_accuracy',sa.Float()),sa.Column('plan_completion_rate',sa.Float()),sa.Column('tutor_sessions_completed',sa.Integer(),nullable=False),sa.Column('weak_skills',sa.JSON(),nullable=False),sa.Column('strengths',sa.JSON(),nullable=False),sa.Column('generated_by',sa.String(64),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('student_id','snapshot_date',name='uq_progress_snapshot_student_date'))
    op.create_index('ix_progress_snapshots_student_id','progress_snapshots',['student_id']);op.create_index('ix_progress_snapshots_snapshot_date','progress_snapshots',['snapshot_date'])
def downgrade():
    op.drop_index('ix_progress_snapshots_snapshot_date',table_name='progress_snapshots');op.drop_index('ix_progress_snapshots_student_id',table_name='progress_snapshots');op.drop_table('progress_snapshots')
    for name in ['ix_dashboard_access_grants_role','ix_dashboard_access_grants_student_id','ix_dashboard_access_grants_viewer_id']:op.drop_index(name,table_name='dashboard_access_grants')
    op.drop_table('dashboard_access_grants')
