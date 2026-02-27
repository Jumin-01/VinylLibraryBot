from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models import Track

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
    async def create(vinyl_id: int, title: str, position: str, duration: str | None = None):
        async with AsyncSessionLocal() as session:
            track = Track(vinyl_id=vinyl_id, title=title, position=position, duration=duration)
            session.add(track)
            await session.commit()
            return track