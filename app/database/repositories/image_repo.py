from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models import Image

class ImageRepo:
    @staticmethod
    async def get_by_vinyl(vinyl_id: int):
        async with AsyncSessionLocal() as session:
            stmt = select(Image).where(Image.vinyl_id == vinyl_id)
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
    async def create(vinyl_id: int, type: str, uri: str, uri150: str | None = None, width: int | None = None, height: int | None = None):
        async with AsyncSessionLocal() as session:
            img = Image(vinyl_id=vinyl_id, type=type, uri=uri, uri150=uri150, width=width, height=height)
            session.add(img)
            await session.commit()
            return img