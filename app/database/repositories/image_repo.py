from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models import Image
from sqlalchemy.ext.asyncio import AsyncSession

class ImageRepo:
    @staticmethod
    async def get_by_release(release_id: int):
        async with AsyncSessionLocal() as session:
            stmt = select(Image).where(Image.release_id == release_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def add(image):
        async with AsyncSessionLocal() as session:
            session.add(image)
            await session.commit()
            await session.refresh(image)
            return image

    @staticmethod
    async def create(session: AsyncSession, release_id: int, type: str, uri: str, uri150: str | None = None, width: int | None = None, height: int | None = None):
        img = Image(release_id=release_id, type=type, uri=uri, uri150=uri150, width=width, height=height)
        session.add(img)
        return img