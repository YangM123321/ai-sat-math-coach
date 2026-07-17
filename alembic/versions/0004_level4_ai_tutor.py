"""level4 ai tutor
Revision ID: 0004_level4_ai_tutor
Revises: 0003_level3
"""
from alembic import op
import sqlalchemy as sa
revision='0004_level4_ai_tutor'; down_revision='0003_level3'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('tutor_sessions',
      sa.Column('id',sa.String(32),primary_key=True),sa.Column('student_id',sa.String(128),nullable=False),
      sa.Column('skill_id',sa.String(32),sa.ForeignKey('skills.id',ondelete='RESTRICT'),nullable=False),
      sa.Column('learning_activity_id',sa.String(32),sa.ForeignKey('learning_activities.id',ondelete='SET NULL')),
      sa.Column('status',sa.String(24),nullable=False),sa.Column('problem_text',sa.Text(),nullable=False),
      sa.Column('correct_answer',sa.Text()),sa.Column('student_answer',sa.Text()),sa.Column('student_work',sa.Text()),
      sa.Column('current_step',sa.Integer(),nullable=False),sa.Column('max_hints',sa.Integer(),nullable=False),
      sa.Column('hints_used',sa.Integer(),nullable=False),sa.Column('provider',sa.String(64),nullable=False),
      sa.Column('policy_version',sa.String(64),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
      sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.Column('completed_at',sa.DateTime(timezone=True)))
    op.create_index('ix_tutor_sessions_student_id','tutor_sessions',['student_id']); op.create_index('ix_tutor_sessions_status','tutor_sessions',['status'])
    op.create_table('tutor_messages',sa.Column('id',sa.String(32),primary_key=True),sa.Column('session_id',sa.String(32),sa.ForeignKey('tutor_sessions.id',ondelete='CASCADE'),nullable=False),sa.Column('role',sa.String(16),nullable=False),sa.Column('content',sa.Text(),nullable=False),sa.Column('strategy',sa.String(24)),sa.Column('sequence',sa.Integer(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_tutor_messages_session_id','tutor_messages',['session_id'])
    op.create_table('tutor_feedback',sa.Column('id',sa.String(32),primary_key=True),sa.Column('session_id',sa.String(32),sa.ForeignKey('tutor_sessions.id',ondelete='CASCADE'),nullable=False),sa.Column('helpful',sa.Boolean(),nullable=False),sa.Column('rating',sa.Integer()),sa.Column('comment',sa.Text()),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_tutor_feedback_session_id','tutor_feedback',['session_id'])
def downgrade():
    op.drop_index('ix_tutor_feedback_session_id',table_name='tutor_feedback'); op.drop_table('tutor_feedback')
    op.drop_index('ix_tutor_messages_session_id',table_name='tutor_messages'); op.drop_table('tutor_messages')
    op.drop_index('ix_tutor_sessions_status',table_name='tutor_sessions'); op.drop_index('ix_tutor_sessions_student_id',table_name='tutor_sessions'); op.drop_table('tutor_sessions')
