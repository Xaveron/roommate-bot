"""stage 5: Mini App actions (idempotency keys, announcement message of a duty)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-26 14:49:40.530151
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('api_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('status_code', sa.Integer(), nullable=False),
    sa.Column('response', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_api_requests')),
    sa.UniqueConstraint('user_id', 'key', name=op.f('uq_api_requests_user_id_key'))
    )
    with op.batch_alter_table('duties', schema=None) as batch_op:
        batch_op.add_column(sa.Column('message_chat_id', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('message_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('duties', schema=None) as batch_op:
        batch_op.drop_column('message_id')
        batch_op.drop_column('message_chat_id')

    op.drop_table('api_requests')
