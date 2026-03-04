from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models import Track
from sqlalchemy.ext.asyncio import AsyncSession

class TrackRepo:
    @staticmethod
    async def get_by_vinyl(vinyl_id: int):
        async with AsyncSessionLocal() as session:
            stmt = select(Track).where(Track.vinyl_id == vinyl_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def add(track):
        async with AsyncSessionLocal() as session:
            session.add(track)
            await session.commit()
            await session.refresh(track)
            return track

    @staticmethod
    async def create(session: AsyncSession, vinyl_id: int, title: str, position: str, duration: str | None = None):
        track = Track(vinyl_id=vinyl_id, title=title, position=position, duration=duration)
        session.add(track)
        return track