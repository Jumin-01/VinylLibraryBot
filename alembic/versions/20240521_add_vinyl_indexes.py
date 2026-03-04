"""add vinyl indexes

Revision ID: 20240521_add_vinyl_indexes
Revises: <PREVIOUS_REVISION_ID>
Create Date: 2024-05-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20240521_add_vinyl_indexes'
down_revision: Union[str, None] = 'analytics_init'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_vinyls_user_id_discogs_id', 'vinyls', ['user_id', 'discogs_id'], unique=False)
    op.create_index('ix_vinyls_user_id_is_wishlist', 'vinyls', ['user_id', 'is_wishlist'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_vinyls_user_id_is_wishlist', table_name='vinyls')
    op.drop_index('ix_vinyls_user_id_discogs_id', table_name='vinyls')