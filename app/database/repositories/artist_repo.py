from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models import Artist
from sqlalchemy.ext.asyncio import AsyncSession

class ArtistRepo:
    @staticmethod
    async def get_by_release(release_id: int):
        async with AsyncSessionLocal() as session:
            stmt = select(Artist).where(Artist.release_id == release_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def add(artist):
        async with AsyncSessionLocal() as session:
            session.add(artist)
            await session.commit()
            await session.refresh(artist)
            return artist

    @staticmethod
    async def create(session: AsyncSession, release_id: int, name: str, role: str | None = None):
        artist = Artist(release_id=release_id, name=name, role=role)
        session.add(artist)
        return artist