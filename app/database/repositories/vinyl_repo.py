from sqlalchemy import select, func, or_, update
from app.database.db import AsyncSessionLocal
from app.database.models import Vinyl, Artist
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

class VinylRepo:
    @staticmethod
    async def create(session: AsyncSession, user_id: int, **kwargs):
        """Створює об'єкт Vinyl в рамках існуючої сесії."""
        vinyl = Vinyl(user_id=user_id, **kwargs)
        session.add(vinyl)
        await session.flush()
        await session.refresh(vinyl)
        return vinyl

    @staticmethod
    async def update(vinyl_id: int, session: AsyncSession | None = None, **kwargs):
        """Оновлює поля платівки."""
        if session:
            stmt = update(Vinyl).where(Vinyl.id == vinyl_id).values(**kwargs)
            await session.execute(stmt)
        else:
            async with AsyncSessionLocal() as new_session:
                stmt = update(Vinyl).where(Vinyl.id == vinyl_id).values(**kwargs)
                await new_session.execute(stmt)
                await new_session.commit()

    @staticmethod
    async def get_by_id(vinyl_id: int, session: AsyncSession | None = None):
        """Отримати платівку за ID."""
        async def _get(s: AsyncSession):
            return await s.get(
                Vinyl,
                vinyl_id,
                options=[
                    selectinload(Vinyl.artists),
                    selectinload(Vinyl.formats),
                    selectinload(Vinyl.tracks),
                    selectinload(Vinyl.images),
                    selectinload(Vinyl.identifiers),
                ],
            )

        if session:
            return await _get(session)
        async with AsyncSessionLocal() as new_session:
            return await _get(new_session)

    @staticmethod
    async def get_by_discogs_id(user_id: int, discogs_id: int, session: AsyncSession | None = None):
        async def _get(s: AsyncSession):
            stmt = select(Vinyl).where(Vinyl.user_id == user_id, Vinyl.discogs_id == discogs_id)
            result = await s.execute(stmt)
            return result.scalar_one_or_none()
        
        if session:
            return await _get(session)
        async with AsyncSessionLocal() as new_session:
            return await _get(new_session)

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
    async def get_shared_playlist_url(discogs_id: int) -> str | None:
        """
        Шукає існуюче посилання на плейлист у будь-якого користувача для даного discogs_id.
        """
        async with AsyncSessionLocal() as session:
            # Шукаємо перший-ліпший запис з таким discogs_id, де є посилання
            stmt = select(Vinyl.generated_playlist_url).where(
                Vinyl.discogs_id == discogs_id,
                Vinyl.generated_playlist_url.is_not(None),
                Vinyl.generated_playlist_url != ""
            ).limit(1)
            
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

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