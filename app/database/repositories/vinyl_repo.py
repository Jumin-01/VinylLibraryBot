from sqlalchemy import select, func, or_, update
from app.database.db import AsyncSessionLocal
from app.database.models import Artist, Release, UserVinyl
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

class VinylRepo:
    @staticmethod
    async def create_release(session: AsyncSession, **kwargs) -> Release:
        """Створює об'єкт Release в рамках існуючої сесії."""
        release = Release(**kwargs)
        session.add(release)
        await session.flush()
        await session.refresh(release)
        return release

    @staticmethod
    async def create_user_vinyl(session: AsyncSession, user_id: int, release_id: int, is_wishlist: bool) -> UserVinyl:
        """Створює зв'язок User-Release (додає платівку користувачу)."""
        user_vinyl = UserVinyl(user_id=user_id, release_id=release_id, is_wishlist=is_wishlist)
        session.add(user_vinyl)
        await session.flush()
        await session.refresh(user_vinyl)
        return user_vinyl

    @staticmethod
    async def update_user_vinyl(user_vinyl_id: int, session: AsyncSession | None = None, **kwargs):
        """Оновлює поля платівки користувача (напр. is_wishlist)."""
        if session:
            stmt = update(UserVinyl).where(UserVinyl.id == user_vinyl_id).values(**kwargs)
            await session.execute(stmt)
        else:
            async with AsyncSessionLocal() as new_session:
                stmt = update(UserVinyl).where(UserVinyl.id == user_vinyl_id).values(**kwargs)
                await new_session.execute(stmt)
                await new_session.commit()

    @staticmethod
    async def update_release(release_id: int, session: AsyncSession | None = None, **kwargs):
        """Оновлює поля релізу (напр. ціни)."""
        if session:
            stmt = update(Release).where(Release.id == release_id).values(**kwargs)
            await session.execute(stmt)
        else:
            async with AsyncSessionLocal() as new_session:
                stmt = update(Release).where(Release.id == release_id).values(**kwargs)
                await new_session.execute(stmt)
                await new_session.commit()

    @staticmethod
    async def get_user_vinyl_by_id(user_vinyl_id: int, session: AsyncSession | None = None) -> UserVinyl | None:
        """Отримати платівку користувача за її ID."""
        async def _get(s: AsyncSession):
            stmt = select(UserVinyl).where(UserVinyl.id == user_vinyl_id).options(
                selectinload(UserVinyl.release).selectinload(Release.artists),
                selectinload(UserVinyl.release).selectinload(Release.formats),
                selectinload(UserVinyl.release).selectinload(Release.tracks),
                selectinload(UserVinyl.release).selectinload(Release.images),
                selectinload(UserVinyl.release).selectinload(Release.identifiers),
            )
            return (await s.execute(stmt)).scalar_one_or_none()

        if session:
            return await _get(session)
        async with AsyncSessionLocal() as new_session:
            return await _get(new_session)

    @staticmethod
    async def get_release_by_discogs_id(discogs_id: int, session: AsyncSession | None = None) -> Release | None:
        """Отримати реліз за Discogs ID."""
        async def _get(s: AsyncSession):
            stmt = select(Release).where(Release.discogs_id == discogs_id)
            return (await s.execute(stmt)).scalar_one_or_none()

        if session:
            return await _get(session)
        async with AsyncSessionLocal() as new_session:
            return await _get(new_session)

    @staticmethod
    async def get_user_vinyl_by_release_id(user_id: int, release_id: int, session: AsyncSession | None = None) -> UserVinyl | None:
        """Перевірити, чи є у користувача платівка з даним release_id."""
        async def _get(s: AsyncSession):
            stmt = select(UserVinyl).where(UserVinyl.user_id == user_id, UserVinyl.release_id == release_id)
            return (await s.execute(stmt)).scalar_one_or_none()

        if session:
            return await _get(session)
        async with AsyncSessionLocal() as new_session:
            return await _get(new_session)

    @staticmethod
    async def delete_user_vinyl(user_vinyl_id: int):
        """Видалити платівку з колекції користувача за ID."""
        async with AsyncSessionLocal() as session:
            user_vinyl = await session.get(UserVinyl, user_vinyl_id)
            if user_vinyl:
                await session.delete(user_vinyl)
                await session.commit()
                return True
            return False

    @staticmethod
    async def get_user_vinyls(user_id: int, page: int = 0, limit: int = 5, is_wishlist: bool = False):
        offset = page * limit
        async with AsyncSessionLocal() as session:
            stmt = (
                select(UserVinyl)
                .options(
                    selectinload(UserVinyl.release).selectinload(Release.artists),
                    selectinload(UserVinyl.release).selectinload(Release.formats),
                    selectinload(UserVinyl.release).selectinload(Release.tracks)
                )
                .where(UserVinyl.user_id == user_id, UserVinyl.is_wishlist == is_wishlist)
                .order_by(UserVinyl.id.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            user_vinyls = result.scalars().all()

            # Повертаємо також total_count для пагінації
            count_stmt = select(func.count(UserVinyl.id)).where(UserVinyl.user_id == user_id, UserVinyl.is_wishlist == is_wishlist)
            total_count = (await session.execute(count_stmt)).scalar()

            return user_vinyls, total_count

    @staticmethod
    async def get_shared_playlist_url(discogs_id: int) -> str | None:
        """
        Шукає існуюче посилання на плейлист у будь-якого користувача для даного discogs_id.
        """
        async with AsyncSessionLocal() as session:
            # Шукаємо перший-ліпший запис з таким discogs_id, де є посилання
            stmt = select(Release.generated_playlist_url).where(
                Release.discogs_id == discogs_id,
                Release.generated_playlist_url.is_not(None),
                Release.generated_playlist_url != ""
            ).limit(1)
            
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @staticmethod
    async def search_user_vinyls(user_id: int, query: str, page: int = 0, limit: int = 5, is_wishlist: bool = False):
        offset = page * limit
        search_term = f"%{query}%"
        async with AsyncSessionLocal() as session:
            # Запит для пошуку ID платівок користувача, що відповідають критеріям
            subquery = (
                select(UserVinyl.id)
                .join(UserVinyl.release)
                .join(Release.artists)
                .outerjoin(Release.artists)
                .where(
                    UserVinyl.user_id == user_id,
                    UserVinyl.is_wishlist == is_wishlist,
                    or_(
                        Release.title.ilike(search_term),
                        Artist.name.ilike(search_term)
                    )
                )
                .distinct()
            )

            # Основний запит для вибірки повних об'єктів
            stmt = (
                select(UserVinyl)
                .options(
                    selectinload(UserVinyl.release).selectinload(Release.artists),
                    selectinload(UserVinyl.release).selectinload(Release.formats),
                    selectinload(UserVinyl.release).selectinload(Release.tracks)
                )
                .where(UserVinyl.id.in_(subquery))
                .order_by(UserVinyl.id.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            user_vinyls = result.scalars().all()

            count_stmt = select(func.count()).select_from(subquery.subquery())
            total_count = (await session.execute(count_stmt)).scalar()

            return user_vinyls, total_count