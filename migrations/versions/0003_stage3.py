"""stage 3: expenses, shopping list, achievements

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25 23:48:46.236171
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('achievements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('member_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('earned_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], name=op.f('fk_achievements_member_id_members'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_achievements')),
    sa.UniqueConstraint('member_id', 'code', name=op.f('uq_achievements_member_id_code'))
    )
    with op.batch_alter_table('achievements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_achievements_member_id'), ['member_id'], unique=False)

    op.create_table('shopping_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.String(length=128), nullable=False),
    sa.Column('added_by', sa.Integer(), nullable=True),
    sa.Column('bought_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('bought_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['added_by'], ['members.id'], name=op.f('fk_shopping_items_added_by_members'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['bought_by'], ['members.id'], name=op.f('fk_shopping_items_bought_by_members'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], name=op.f('fk_shopping_items_room_id_rooms'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_shopping_items'))
    )
    with op.batch_alter_table('shopping_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_shopping_items_room_id'), ['room_id'], unique=False)

    op.create_table('expenses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=False),
    sa.Column('payer_id', sa.Integer(), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(length=128), nullable=False),
    sa.Column('is_settlement', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('duty_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['duty_id'], ['duties.id'], name=op.f('fk_expenses_duty_id_duties'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['payer_id'], ['members.id'], name=op.f('fk_expenses_payer_id_members'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], name=op.f('fk_expenses_room_id_rooms'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_expenses'))
    )
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_expenses_room_id'), ['room_id'], unique=False)

    op.create_table('expense_shares',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('expense_id', sa.Integer(), nullable=False),
    sa.Column('member_id', sa.Integer(), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['expense_id'], ['expenses.id'], name=op.f('fk_expense_shares_expense_id_expenses'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], name=op.f('fk_expense_shares_member_id_members'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_expense_shares')),
    sa.UniqueConstraint('expense_id', 'member_id', name=op.f('uq_expense_shares_expense_id_member_id'))
    )
    with op.batch_alter_table('expense_shares', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_expense_shares_expense_id'), ['expense_id'], unique=False)

    # duties.amount (decimal, never filled by stage 1-2) becomes duties.amount_cents.
    with op.batch_alter_table('duties', schema=None) as batch_op:
        batch_op.add_column(sa.Column('amount_cents', sa.Integer(), nullable=True))
    op.execute(
        "UPDATE duties SET amount_cents = CAST(ROUND(amount * 100) AS INTEGER) "
        "WHERE amount IS NOT NULL"
    )
    with op.batch_alter_table('duties', schema=None) as batch_op:
        batch_op.drop_column('amount')

    with op.batch_alter_table('rooms', schema=None) as batch_op:
        batch_op.add_column(sa.Column('currency', sa.String(length=8), server_default='MDL', nullable=False))
        batch_op.add_column(sa.Column('weekly_summary', sa.Boolean(), server_default=sa.true(), nullable=False))
        batch_op.add_column(sa.Column('weekly_summary_sent_on', sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('rooms', schema=None) as batch_op:
        batch_op.drop_column('weekly_summary_sent_on')
        batch_op.drop_column('weekly_summary')
        batch_op.drop_column('currency')

    with op.batch_alter_table('duties', schema=None) as batch_op:
        batch_op.add_column(sa.Column('amount', sa.NUMERIC(precision=10, scale=2), nullable=True))
    op.execute("UPDATE duties SET amount = amount_cents / 100.0 WHERE amount_cents IS NOT NULL")
    with op.batch_alter_table('duties', schema=None) as batch_op:
        batch_op.drop_column('amount_cents')

    with op.batch_alter_table('expense_shares', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_expense_shares_expense_id'))

    op.drop_table('expense_shares')
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_expenses_room_id'))

    op.drop_table('expenses')
    with op.batch_alter_table('shopping_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_shopping_items_room_id'))

    op.drop_table('shopping_items')
    with op.batch_alter_table('achievements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_achievements_member_id'))

    op.drop_table('achievements')
