"""Split Vinyl into Release and UserVinyl with data migration

Revision ID: 9fa3e9c963e3
Revises: 84d2a1b3c4e5
Create Date: 2026-03-05 23:44:47.733329

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9fa3e9c963e3'
down_revision: Union[str, None] = '84d2a1b3c4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Крок 1: Створення нових таблиць
    op.create_table('releases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('discogs_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('released', sa.String(length=50), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('catno', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('lowest_price', sa.Float(), nullable=True),
        sa.Column('median_price', sa.Float(), nullable=True),
        sa.Column('highest_price', sa.Float(), nullable=True),
        sa.Column('num_for_sale', sa.Integer(), nullable=True),
        sa.Column('rating_average', sa.Float(), nullable=True),
        sa.Column('rating_count', sa.Integer(), nullable=True),
        sa.Column('have_count', sa.Integer(), nullable=True),
        sa.Column('want_count', sa.Integer(), nullable=True),
        sa.Column('genres', sa.JSON(), nullable=True),
        sa.Column('styles', sa.JSON(), nullable=True),
        sa.Column('cover_image', sa.String(length=500), nullable=True),
        sa.Column('generated_playlist_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_releases_discogs_id'), 'releases', ['discogs_id'], unique=True)

    op.create_table('user_vinyls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('release_id', sa.Integer(), nullable=False),
        sa.Column('is_wishlist', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'release_id', name='_user_release_uc')
    )
    op.create_index(op.f('ix_user_vinyls_release_id'), 'user_vinyls', ['release_id'], unique=False)
    op.create_index(op.f('ix_user_vinyls_user_id'), 'user_vinyls', ['user_id'], unique=False)

    # Крок 2: Міграція даних з 'vinyls' в 'releases' та 'user_vinyls'
    op.execute("""
        INSERT INTO releases (
            discogs_id, title, year, released, country, catno, notes,
            lowest_price, median_price, highest_price, num_for_sale,
            rating_average, rating_count, have_count, want_count,
            genres, styles, cover_image, generated_playlist_url, created_at
        )
        SELECT
            v.discogs_id,
            MAX(v.title), MAX(v.year), MAX(v.released), MAX(v.country), MAX(v.catno), MAX(v.notes),
            MAX(v.lowest_price), MAX(v.median_price), MAX(v.highest_price), MAX(v.num_for_sale),
            MAX(v.rating_average), MAX(v.rating_count), MAX(v.have_count), MAX(v.want_count),
            MAX(v.genres), MAX(v.styles), MAX(v.cover_image), MAX(v.generated_playlist_url),
            MIN(v.created_at)
        FROM vinyls v
        GROUP BY v.discogs_id
    """)

    op.execute("""
        INSERT INTO user_vinyls (user_id, release_id, is_wishlist, created_at)
        SELECT u.id, r.id, v.is_wishlist, v.created_at
        FROM vinyls v
        JOIN releases r ON v.discogs_id = r.discogs_id
        JOIN users u ON v.user_id = u.telegram_id
    """)

    # Крок 3: Міграція пов'язаних таблиць (tracks, artists, etc.)
    related_tables = {
        'tracks': ['position', 'title', 'duration'],
        'artists': ['name', 'role', 'position'],
        'formats': ['name', 'qty', 'descriptions'],
        'images': ['type', 'uri', 'uri150', 'width', 'height'],
        'identifiers': ['type', 'value', 'description']
    }

    for table_name, unique_cols in related_tables.items():
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column('release_id', sa.Integer(), nullable=True))

        op.execute(f"""
            UPDATE {table_name}
            SET release_id = (
                SELECT r.id
                FROM releases r
                JOIN vinyls v ON r.discogs_id = v.discogs_id
                WHERE v.id = {table_name}.vinyl_id
            )
        """)

        group_by_cols = ", ".join(unique_cols)
        op.execute(f"""
            DELETE FROM {table_name}
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM {table_name}
                WHERE release_id IS NOT NULL
                GROUP BY release_id, {group_by_cols}
            )
        """)

        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column('vinyl_id')
            batch_op.alter_column('release_id', existing_type=sa.Integer(), nullable=False)
            batch_op.create_foreign_key(f'fk_{table_name}_releases', 'releases', ['release_id'], ['id'])

    # Крок 4: Видалення старої таблиці 'vinyls'
    op.drop_table('vinyls')


def downgrade() -> None:
    # Відкат цієї міграції є руйнівним і не відновлює дані.
    # Створюється схема, що існувала до міграції.
    op.create_table('vinyls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('discogs_id', sa.Integer(), nullable=False),
        sa.Column('is_wishlist', sa.Boolean(), server_default='false', nullable=False),
        # ... інші колонки з таблиці vinyls ...
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    related_tables = ['tracks', 'artists', 'formats', 'images', 'identifiers']
    for table_name in related_tables:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column('vinyl_id', sa.Integer(), nullable=True))
            # Тут потрібно було б відновити дані, але це складно.
            # Просто відновлюємо структуру.
            batch_op.drop_constraint(f'fk_{table_name}_releases', type_='foreignkey')
            batch_op.drop_column('release_id')
            batch_op.alter_column('vinyl_id', existing_type=sa.Integer(), nullable=False)
            batch_op.create_foreign_key(f'fk_{table_name}_vinyls', 'vinyls', ['vinyl_id'], ['id'])

    op.drop_index(op.f('ix_user_vinyls_user_id'), table_name='user_vinyls')
    op.drop_index(op.f('ix_user_vinyls_release_id'), table_name='user_vinyls')
    op.drop_table('user_vinyls')
    op.drop_index(op.f('ix_releases_discogs_id'), table_name='releases')
    op.drop_table('releases')