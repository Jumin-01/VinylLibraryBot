from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models import Identifier
from sqlalchemy.ext.asyncio import AsyncSession

class IdentifierRepo:
    @staticmethod
    async def get_by_release(release_id: int):
        async with AsyncSessionLocal() as session:
            stmt = select(Identifier).where(Identifier.release_id == release_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def add(identifier):
        async with AsyncSessionLocal() as session:
            session.add(identifier)
            await session.commit()
            await session.refresh(identifier)
            return identifier

    @staticmethod
    async def create(session: AsyncSession, release_id: int, type: str, value: str, description: str | None = None):
        ident = Identifier(release_id=release_id, type=type, value=value, description=description)
        session.add(ident)
        return ident