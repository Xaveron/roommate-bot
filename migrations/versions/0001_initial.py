"""initial schema: rooms, members, categories, queues, duties

Revision ID: 0001
Revises:
Create Date: 2026-09-25 22:43:06.469616
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('rooms',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('chat_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('language', sa.String(length=8), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('quiet_hours_start', sa.Time(), nullable=True),
    sa.Column('quiet_hours_end', sa.Time(), nullable=True),
    sa.Column('created_by', sa.BigInteger(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rooms')),
    sa.UniqueConstraint('chat_id', name=op.f('uq_rooms_chat_id'))
    )
    op.create_table('categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('emoji', sa.String(length=16), nullable=False),
    sa.Column('reminder_time', sa.Time(), nullable=False),
    sa.Column('reminder_days', sa.String(length=7), nullable=False),
    sa.Column('queue_mode', sa.String(length=16), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('last_reminded_on', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], name=op.f('fk_categories_room_id_rooms'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_categories'))
    )
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_categories_room_id'), ['room_id'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('first_name', sa.String(length=128), nullable=False),
    sa.Column('last_name', sa.String(length=128), nullable=True),
    sa.Column('username', sa.String(length=64), nullable=True),
    sa.Column('language_code', sa.String(length=16), nullable=True),
    sa.Column('dm_available', sa.Boolean(), nullable=False),
    sa.Column('active_room_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['active_room_id'], ['rooms.id'], name=op.f('fk_users_active_room_id_rooms'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_table('members',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=False),
    sa.Column('telegram_user_id', sa.BigInteger(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('away_until', sa.Date(), nullable=True),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], name=op.f('fk_members_room_id_rooms'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['telegram_user_id'], ['users.id'], name=op.f('fk_members_telegram_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_members')),
    sa.UniqueConstraint('room_id', 'telegram_user_id', name=op.f('uq_members_room_id_telegram_user_id'))
    )
    with op.batch_alter_table('members', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_members_room_id'), ['room_id'], unique=False)

    op.create_table('assignments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('member_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('for_date', sa.Date(), nullable=False),
    sa.Column('remind_on', sa.Date(), nullable=True),
    sa.Column('last_reminded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reminders_sent', sa.Integer(), nullable=False),
    sa.Column('message_chat_id', sa.BigInteger(), nullable=True),
    sa.Column('message_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], name=op.f('fk_assignments_category_id_categories'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], name=op.f('fk_assignments_member_id_members'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_assignments'))
    )
    with op.batch_alter_table('assignments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assignments_member_id'), ['member_id'], unique=False)
        batch_op.create_index('uq_assignments_open_category', ['category_id'], unique=True, sqlite_where=sa.text("status IN ('pending', 'accepted', 'snoozed')"), postgresql_where=sa.text("status IN ('pending', 'accepted', 'snoozed')"))

    op.create_table('queue_states',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('member_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('skip_debt', sa.Integer(), nullable=False),
    sa.Column('credit', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], name=op.f('fk_queue_states_category_id_categories'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], name=op.f('fk_queue_states_member_id_members'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_queue_states')),
    sa.UniqueConstraint('category_id', 'member_id', name=op.f('uq_queue_states_category_id_member_id'))
    )
    with op.batch_alter_table('queue_states', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_queue_states_category_id'), ['category_id'], unique=False)

    op.create_table('duties',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('member_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('assignment_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], name=op.f('fk_duties_assignment_id_assignments'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], name=op.f('fk_duties_category_id_categories'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], name=op.f('fk_duties_member_id_members'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_duties'))
    )
    with op.batch_alter_table('duties', schema=None) as batch_op:
        batch_op.create_index('ix_duties_category_id_created_at', ['category_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_duties_member_id'), ['member_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('duties', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_duties_member_id'))
        batch_op.drop_index('ix_duties_category_id_created_at')

    op.drop_table('duties')
    with op.batch_alter_table('queue_states', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_queue_states_category_id'))

    op.drop_table('queue_states')
    with op.batch_alter_table('assignments', schema=None) as batch_op:
        batch_op.drop_index('uq_assignments_open_category', sqlite_where=sa.text("status IN ('pending', 'accepted', 'snoozed')"), postgresql_where=sa.text("status IN ('pending', 'accepted', 'snoozed')"))
        batch_op.drop_index(batch_op.f('ix_assignments_member_id'))

    op.drop_table('assignments')
    with op.batch_alter_table('members', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_members_room_id'))

    op.drop_table('members')
    op.drop_table('users')
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_categories_room_id'))

    op.drop_table('categories')
    op.drop_table('rooms')
