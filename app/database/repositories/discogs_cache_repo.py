from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.database.db import AsyncSessionLocal
from app.database.models import DiscogsCache
from datetime import datetime

class DiscogsCacheRepo:
    @staticmethod
    async def get(discogs_id: int):
        """Отримати запис з кешу за discogs_id."""
        async with AsyncSessionLocal() as session:
            return await session.get(DiscogsCache, discogs_id)

    @staticmethod
    async def upsert(discogs_id: int, data: dict):
        """Додати або оновити запис в кеші."""
        async with AsyncSessionLocal() as session:
            stmt = sqlite_insert(DiscogsCache).values(
                discogs_id=discogs_id,
                data=data,
                cached_at=datetime.utcnow()
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['discogs_id'],
                set_=dict(data=data, cached_at=datetime.utcnow())
            )
            await session.execute(stmt)
            await session.commit()