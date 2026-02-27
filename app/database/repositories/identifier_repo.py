from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models import Identifier

class IdentifierRepo:
    @staticmethod
    async def get_by_vinyl(vinyl_id: int):
        async with AsyncSessionLocal() as session:
            stmt = select(Identifier).where(Identifier.vinyl_id == vinyl_id)
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
    async def create(vinyl_id: int, type: str, value: str, description: str | None = None):
        async with AsyncSessionLocal() as session:
            ident = Identifier(vinyl_id=vinyl_id, type=type, value=value, description=description)
            session.add(ident)
            await session.commit()
            return ident