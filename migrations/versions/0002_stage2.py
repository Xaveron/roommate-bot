"""stage 2: repeat reminders, reviews, absences

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25 23:32:43.654705
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('absences',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('member_id', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], name=op.f('fk_absences_member_id_members'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_absences'))
    )
    with op.batch_alter_table('absences', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_absences_member_id'), ['member_id'], unique=False)

    op.create_table('duty_votes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('duty_id', sa.Integer(), nullable=False),
    sa.Column('member_id', sa.Integer(), nullable=False),
    sa.Column('vote', sa.String(length=8), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['duty_id'], ['duties.id'], name=op.f('fk_duty_votes_duty_id_duties'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], name=op.f('fk_duty_votes_member_id_members'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_duty_votes')),
    sa.UniqueConstraint('duty_id', 'member_id', name=op.f('uq_duty_votes_duty_id_member_id'))
    )
    with op.batch_alter_table('duty_votes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_duty_votes_duty_id'), ['duty_id'], unique=False)

    with op.batch_alter_table('duties', schema=None) as batch_op:
        batch_op.add_column(sa.Column('review', sa.String(length=16), server_default='open', nullable=False))

    with op.batch_alter_table('rooms', schema=None) as batch_op:
        batch_op.add_column(sa.Column('repeat_after_hours', sa.Integer(), server_default=sa.text('3'), nullable=False))



def downgrade() -> None:
    with op.batch_alter_table('rooms', schema=None) as batch_op:
        batch_op.drop_column('repeat_after_hours')

    with op.batch_alter_table('duties', schema=None) as batch_op:
        batch_op.drop_column('review')

    with op.batch_alter_table('duty_votes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_duty_votes_duty_id'))

    op.drop_table('duty_votes')
    with op.batch_alter_table('absences', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_absences_member_id'))

    op.drop_table('absences')
