from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models import Artist
from sqlalchemy.ext.asyncio import AsyncSession

class ArtistRepo:
    @staticmethod
    async def get_by_vinyl(vinyl_id: int):
        async with AsyncSessionLocal() as session:
            stmt = select(Artist).where(Artist.vinyl_id == vinyl_id)
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
    async def create(session: AsyncSession, vinyl_id: int, name: str, role: str | None = None):
        artist = Artist(vinyl_id=vinyl_id, name=name, role=role)
        session.add(artist)
        return artist