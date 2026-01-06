"""Add recursive groups support

Revision ID: 2750ebe4971c
Revises: 16fef1ee2380
Create Date: 2026-01-05 11:09:55.595839

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2750ebe4971c'
down_revision: Union[str, Sequence[str], None] = '16fef1ee2380'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create user_groups table with hierarchical support
    op.create_table(
        'user_groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), unique=True, nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('parent_group_id', sa.Integer(), sa.ForeignKey('user_groups.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
    )
    op.create_index('ix_user_groups_parent_group_id', 'user_groups', ['parent_group_id'])
    
    # Create user_group_members association table
    op.create_table(
        'user_group_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('user_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('added_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('ix_user_group_members_user_id', 'user_group_members', ['user_id'])
    op.create_index('ix_user_group_members_group_id', 'user_group_members', ['group_id'])
    op.create_unique_constraint('uq_user_group_members', 'user_group_members', ['user_id', 'group_id'])
    
    # Add parent_group_id to server_groups for hierarchical server groups
    op.add_column('server_groups', sa.Column('parent_group_id', sa.Integer(), sa.ForeignKey('server_groups.id', ondelete='SET NULL')))
    op.create_index('ix_server_groups_parent_group_id', 'server_groups', ['parent_group_id'])
    
    # Add user_group_id to access_policies to support group-based access
    op.add_column('access_policies', sa.Column('user_group_id', sa.Integer(), sa.ForeignKey('user_groups.id', ondelete='CASCADE')))
    op.create_index('ix_access_policies_user_group_id', 'access_policies', ['user_group_id'])
    
    # Add port_forwarding_allowed flag to users
    op.add_column('users', sa.Column('port_forwarding_allowed', sa.Boolean(), server_default='false', nullable=False))
    
    # Add port_forwarding_allowed flag to user_groups
    op.add_column('user_groups', sa.Column('port_forwarding_allowed', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove port_forwarding_allowed from user_groups
    op.drop_column('user_groups', 'port_forwarding_allowed')
    
    # Remove port_forwarding_allowed from users
    op.drop_column('users', 'port_forwarding_allowed')
    
    # Remove user_group_id from access_policies
    op.drop_index('ix_access_policies_user_group_id', 'access_policies')
    op.drop_column('access_policies', 'user_group_id')
    
    # Remove parent_group_id from server_groups
    op.drop_index('ix_server_groups_parent_group_id', 'server_groups')
    op.drop_column('server_groups', 'parent_group_id')
    
    # Drop user_group_members table
    op.drop_index('ix_user_group_members_group_id', 'user_group_members')
    op.drop_index('ix_user_group_members_user_id', 'user_group_members')
    op.drop_table('user_group_members')
    
    # Drop user_groups table
    op.drop_index('ix_user_groups_parent_group_id', 'user_groups')
    op.drop_table('user_groups')
