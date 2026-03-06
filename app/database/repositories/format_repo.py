from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models import Format
from sqlalchemy.ext.asyncio import AsyncSession

class FormatRepo:
    @staticmethod
    async def get_by_release(release_id: int):
        async with AsyncSessionLocal() as session:
            stmt = select(Format).where(Format.release_id == release_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def add(format_obj):
        async with AsyncSessionLocal() as session:
            session.add(format_obj)
            await session.commit()
            await session.refresh(format_obj)
            return format_obj

    @staticmethod
    async def create(session: AsyncSession, release_id: int, name: str, qty: int | None = None, descriptions: list | None = None):
        fmt = Format(release_id=release_id, name=name, qty=qty, descriptions=descriptions)
        session.add(fmt)
        return fmt