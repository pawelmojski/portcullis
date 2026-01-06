"""Add policy schedules for time-based access control

Revision ID: 8f3c9a2e1d5b
Revises: 2750ebe4971c
Create Date: 2026-01-06 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8f3c9a2e1d5b'
down_revision = '2750ebe4971c'
branch_labels = None
depends_on = None


def upgrade():
    # Create policy_schedules table for recurring time-based access control
    op.create_table(
        'policy_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('policy_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=True, comment='Human-readable name for this schedule rule'),
        sa.Column('weekdays', postgresql.ARRAY(sa.Integer()), nullable=True, comment='0=Monday, 6=Sunday. NULL=all days'),
        sa.Column('time_start', sa.Time(), nullable=True, comment='Start time (HH:MM). NULL=00:00'),
        sa.Column('time_end', sa.Time(), nullable=True, comment='End time (HH:MM). NULL=23:59'),
        sa.Column('months', postgresql.ARRAY(sa.Integer()), nullable=True, comment='1-12. NULL=all months'),
        sa.Column('days_of_month', postgresql.ARRAY(sa.Integer()), nullable=True, comment='1-31. NULL=all days'),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Europe/Warsaw'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['policy_id'], ['access_policies.id'], ondelete='CASCADE')
    )
    
    op.create_index('idx_policy_schedules_policy_id', 'policy_schedules', ['policy_id'])
    
    # Add flag to access_policies to indicate if schedule checking is enabled
    op.add_column('access_policies', sa.Column('use_schedules', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    op.drop_column('access_policies', 'use_schedules')
    op.drop_index('idx_policy_schedules_policy_id', table_name='policy_schedules')
    op.drop_table('policy_schedules')
