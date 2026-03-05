"""add_premium_and_last_active

Revision ID: 84d2a1b3c4e5
Revises: 
Create Date: 2026-03-05 18:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '84d2a1b3c4e5'
down_revision: Union[str, None] = "20260304_prices"  # TODO: Вставте сюди ID останньої міграції
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Для SQLite зміна таблиць має обмеження. Використання "batch mode" вирішує цю проблему.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_premium', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('last_active_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('last_active_at')
        batch_op.drop_column('is_premium')