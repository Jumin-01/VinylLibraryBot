from sqlalchemy import select, func, or_, update
from app.database.db import AsyncSessionLocal
from app.database.models import Vinyl, Artist

from sqlalchemy.orm import selectinload

class VinylRepo:
    @staticmethod
    async def create(user_id: int, **kwargs):
        """Створює та зберігає об'єкт Vinyl."""
        async with AsyncSessionLocal() as session:
            # ВАЖЛИВО: user_id передається як іменований аргумент!
            vinyl = Vinyl(user_id=user_id, **kwargs) 
            session.add(vinyl)
            await session.commit()
            await session.refresh(vinyl)
            return vinyl

    @staticmethod
    async def update(vinyl_id: int, **kwargs):
        """Оновлює поля платівки."""
        async with AsyncSessionLocal() as session:
            stmt = update(Vinyl).where(Vinyl.id == vinyl_id).values(**kwargs)
            await session.execute(stmt)
            await session.commit()


    @staticmethod
    async def get_by_id(vinyl_id: int):
        """Отримати платівку за ID."""
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Vinyl)
                .options(
                    selectinload(Vinyl.artists),
                    selectinload(Vinyl.formats),
                    selectinload(Vinyl.tracks),
                    selectinload(Vinyl.images),
                    selectinload(Vinyl.identifiers),
                )
                .where(Vinyl.id == vinyl_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @staticmethod
    async def get_by_discogs_id(user_id: int, discogs_id: int):
        async with AsyncSessionLocal() as session:
            stmt = select(Vinyl).where(Vinyl.user_id == user_id, Vinyl.discogs_id == discogs_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @staticmethod
    async def delete(vinyl_id: int):
        """Видалити платівку за ID."""
        async with AsyncSessionLocal() as session:
            vinyl = await session.get(Vinyl, vinyl_id)
            if vinyl:
                await session.delete(vinyl)
                await session.commit()
                return True
            return False

    @staticmethod
    async def get_user_vinyls(user_id: int, page: int = 0, limit: int = 5, is_wishlist: bool = False):
        offset = page * limit
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Vinyl)
                .options(
                    selectinload(Vinyl.artists),
                    selectinload(Vinyl.formats),
                    selectinload(Vinyl.tracks)
                )
                .where(Vinyl.user_id == user_id, Vinyl.is_wishlist == is_wishlist)
                .order_by(Vinyl.id.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            vinyls = result.scalars().all()

            # Повертаємо також total_count для пагінації
            count_stmt = select(func.count()).select_from(Vinyl).where(Vinyl.user_id == user_id, Vinyl.is_wishlist == is_wishlist)
            total_count = (await session.execute(count_stmt)).scalar()

            return vinyls, total_count

    @staticmethod
    async def search_user_vinyls(user_id: int, query: str, page: int = 0, limit: int = 5, is_wishlist: bool = False):
        offset = page * limit
        search_term = f"%{query}%"
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Vinyl)
                .join(Vinyl.artists)
                .options(
                    selectinload(Vinyl.artists),
                    selectinload(Vinyl.formats),
                    selectinload(Vinyl.tracks)
                )
                .where(
                    Vinyl.user_id == user_id,
                    Vinyl.is_wishlist == is_wishlist,
                    or_(
                        Vinyl.title.ilike(search_term),
                        Artist.name.ilike(search_term)
                    )
                )
                .distinct()
                .order_by(Vinyl.id.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            vinyls = result.scalars().all()

            count_stmt = (
                select(func.count(func.distinct(Vinyl.id)))
                .join(Vinyl.artists)
                .where(
                    Vinyl.user_id == user_id,
                    Vinyl.is_wishlist == is_wishlist,
                    or_(
                        Vinyl.title.ilike(search_term),
                        Artist.name.ilike(search_term)
                    )
                )
            )
            total_count = (await session.execute(count_stmt)).scalar()

            return vinyls, total_count