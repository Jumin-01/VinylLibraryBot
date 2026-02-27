from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models import Artist

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
    async def create(vinyl_id: int, name: str, role: str | None = None):
        async with AsyncSessionLocal() as session:
            artist = Artist(vinyl_id=vinyl_id, name=name, role=role)
            session.add(artist)
            await session.commit()
            return artist