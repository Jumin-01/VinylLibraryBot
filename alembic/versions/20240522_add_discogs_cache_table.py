"""add discogs cache table

Revision ID: 20240522_add_discogs_cache_table
Revises: 20240521_add_vinyl_indexes
Create Date: 2024-05-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20240522_add_discogs_cache_table'
down_revision: Union[str, None] = '20240521_add_vinyl_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('discogs_cache',
    sa.Column('discogs_id', sa.Integer(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('cached_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('discogs_id')
    )


def downgrade() -> None:
    op.drop_table('discogs_cache')