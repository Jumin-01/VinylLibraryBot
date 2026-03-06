from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.database.db import AsyncSessionLocal
from app.database.models import Release, UserVinyl, Artist, User
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from app.services.valuation_service import ValuationService

class StatisticsRepo:
    @staticmethod
    async def get_stats(telegram_id: int):
        async with AsyncSessionLocal() as session:
            # Спочатку отримуємо внутрішній ID користувача за його telegram_id
            user_id_stmt = select(User.id).where(User.telegram_id == telegram_id)
            user_id = (await session.execute(user_id_stmt)).scalar_one_or_none()

            if not user_id:
                # Повертаємо порожню статистику, якщо користувача не знайдено
                return {"total_releases": 0}

            # 1. Загальна кількість релізів
            total_stmt = select(func.count(UserVinyl.id)).where(UserVinyl.user_id == user_id, UserVinyl.is_wishlist == False)
            total_releases = (await session.execute(total_stmt)).scalar() or 0

            if total_releases == 0:
                return {
                    "total_releases": 0,
                    "unique_artists": 0,
                    "unique_countries": 0,
                    "oldest_release": None,
                    "newest_release": None,
                    "average_year": None,
                    "top_artists": [],
                    "top_countries": [],
                    "top_genres": [],
                    "top_styles": [],
                    "top_rated_genre": None,
                    "most_diverse_genre": None,
                    "top_rated_releases": [],
                    "rarest_releases": [],
                    "most_expensive_releases": [],
                    "decades_distribution": []
                }

            # 2. Кількість унікальних артистів
            artists_stmt = (
                select(func.count(func.distinct(Artist.name)))
                .join(Release, Artist.release_id == Release.id)
                .join(UserVinyl, UserVinyl.release_id == Release.id)
                .where(UserVinyl.user_id == user_id)
                .where(UserVinyl.is_wishlist == False)
            )
            unique_artists = (await session.execute(artists_stmt)).scalar() or 0

            # 3. Кількість країн
            countries_stmt = (
                select(func.count(func.distinct(Release.country)))
                .join(UserVinyl, UserVinyl.release_id == Release.id)
                .where(UserVinyl.user_id == user_id)
                .where(UserVinyl.is_wishlist == False)
                .where(Release.country.is_not(None))
            )
            unique_countries = (await session.execute(countries_stmt)).scalar() or 0

            # 4, 5, 6. Роки (найстаріший, найновіший, середній)
            years_stmt = (
                select(
                    func.min(Release.year),
                    func.max(Release.year),
                    func.avg(Release.year)
                )
                .join(UserVinyl, UserVinyl.release_id == Release.id)
                .where(UserVinyl.user_id == user_id)
                .where(UserVinyl.is_wishlist == False)
                .where(Release.year.is_not(None))
                .where(Release.year > 0) # Фільтруємо 0 або некоректні роки
            )
            min_year, max_year, avg_year = (await session.execute(years_stmt)).one()

            # --- Розширена статистика ---

            # Топ-5 Артистів
            top_artists_stmt = (
                select(Artist.name, func.count(UserVinyl.id))
                .join(Release, Artist.release_id == Release.id)
                .join(UserVinyl, UserVinyl.release_id == Release.id)
                .where(UserVinyl.user_id == user_id)
                .where(UserVinyl.is_wishlist == False)
                .group_by(Artist.name)
                .order_by(func.count(UserVinyl.id).desc())
                .limit(5)
            )
            top_artists = (await session.execute(top_artists_stmt)).all()

            # Топ-5 Країн
            top_countries_stmt = (
                select(Release.country, func.count(UserVinyl.id))
                .join(UserVinyl, UserVinyl.release_id == Release.id)
                .where(UserVinyl.user_id == user_id)
                .where(UserVinyl.is_wishlist == False)
                .where(Release.country.is_not(None))
                .group_by(Release.country)
                .order_by(func.count(UserVinyl.id).desc())
                .limit(5)
            )
            top_countries = (await session.execute(top_countries_stmt)).all()

            # Топ релізів за рейтингом
            top_rated_stmt = (
                select(UserVinyl)
                .join(UserVinyl.release)
                .options(selectinload(UserVinyl.release).selectinload(Release.artists))
                .where(UserVinyl.user_id == user_id)
                .where(UserVinyl.is_wishlist == False)
                .where(Release.rating_average.is_not(None))
                .order_by(Release.rating_average.desc())
                .limit(5)
            )
            top_rated_user_vinyls = (await session.execute(top_rated_stmt)).scalars().all()
            top_rated_releases = [uv.release for uv in top_rated_user_vinyls]

            # Топ найрідкісніших релізів (найменше 'have' на Discogs)
            rarest_stmt = (
                select(UserVinyl)
                .join(UserVinyl.release)
                .options(selectinload(UserVinyl.release).selectinload(Release.artists))
                .where(UserVinyl.user_id == user_id)
                .where(UserVinyl.is_wishlist == False)
                .where(Release.have_count.is_not(None))
                .where(Release.have_count > 0)
                .order_by(Release.have_count.asc())
                .limit(5)
            )
            rarest_user_vinyls = (await session.execute(rarest_stmt)).scalars().all()
            rarest_releases = [uv.release for uv in rarest_user_vinyls]

            # --- Обробка JSON полів (Жанри, Стилі) та Десятиліть в Python ---
            all_vinyls_stmt = (
                select(UserVinyl)
                .options(selectinload(UserVinyl.release).selectinload(Release.artists))
                .where(UserVinyl.user_id == user_id)
                .where(UserVinyl.is_wishlist == False)
            )
            all_user_vinyls = (await session.execute(all_vinyls_stmt)).scalars().all()

            genre_counts = Counter()
            style_counts = Counter()
            genre_ratings = defaultdict(list)
            genre_artists = defaultdict(set)
            decade_counts = Counter()
            total_collection_value = 0.0
            valued_releases = []

            for uv in all_user_vinyls:
                release = uv.release
                # Жанри та Стилі
                if release.genres:
                    for g in release.genres:
                        genre_counts[g] += 1
                        if release.rating_average:
                            genre_ratings[g].append(release.rating_average)
                        for a in release.artists:
                            genre_artists[g].add(a.name)
                if release.styles:
                    for s in release.styles:
                        style_counts[s] += 1
                
                # Десятиліття
                if release.year and isinstance(release.year, int) and release.year > 1900:
                    decade = (release.year // 10) * 10
                    decade_counts[decade] += 1
                
                # Оцінка вартості
                val = ValuationService.calculate_smart_value(
                    release.lowest_price,
                    release.median_price,
                    release.highest_price,
                    release.num_for_sale,
                    release.have_count,
                    release.want_count
                )
                if val:
                    total_collection_value += val['avg']
                    valued_releases.append({'vinyl': release, 'value': val})

            # Агрегація результатів
            top_genres = genre_counts.most_common(5)
            top_styles = style_counts.most_common(5)

            # Сортуємо релізи за оціночною вартістю
            valued_releases.sort(key=lambda x: x['value']['avg'], reverse=True)
            most_expensive_releases = valued_releases[:5]

            # Жанр з найвищим середнім рейтингом (мінімум 2 релізи)
            avg_genre_ratings = []
            for g, ratings in genre_ratings.items():
                if len(ratings) >= 2:
                    avg = sum(ratings) / len(ratings)
                    avg_genre_ratings.append((g, avg))
            avg_genre_ratings.sort(key=lambda x: x[1], reverse=True)
            top_rated_genre = avg_genre_ratings[0] if avg_genre_ratings else None

            # Найрізноманітніший жанр (найбільше унікальних артистів)
            diversity = []
            for g, artists_set in genre_artists.items():
                diversity.append((g, len(artists_set)))
            diversity.sort(key=lambda x: x[1], reverse=True)
            most_diverse_genre = diversity[0] if diversity else None

            # Розподіл по десятиліттях
            total_dated = sum(decade_counts.values())
            decades_dist = []
            if total_dated > 0:
                for d in sorted(decade_counts.keys()):
                    count = decade_counts[d]
                    perc = (count / total_dated) * 100
                    decades_dist.append((d, count, perc))

            return {
                "total_releases": total_releases,
                "unique_artists": unique_artists,
                "unique_countries": unique_countries,
                "oldest_release": min_year,
                "newest_release": max_year,
                "average_year": int(avg_year) if avg_year else None,
                "top_artists": top_artists,
                "top_countries": top_countries,
                "top_genres": top_genres,
                "top_styles": top_styles,
                "top_rated_genre": top_rated_genre,
                "most_diverse_genre": most_diverse_genre,
                "top_rated_releases": top_rated_releases,
                "rarest_releases": rarest_releases,
                "most_expensive_releases": most_expensive_releases,
                "decades_distribution": decades_dist,
                "total_collection_value": round(total_collection_value, 2)
            }

    @staticmethod
    async def get_activity_stats(telegram_id: int):
        async with AsyncSessionLocal() as session:
            user_stmt = select(User).where(User.telegram_id == telegram_id)
            user = (await session.execute(user_stmt)).scalar_one_or_none()
            if not user:
                return None
            
            user_id = user.id
            now = datetime.utcnow()
            
            # Total vinyls
            total_stmt = select(func.count(UserVinyl.id)).where(UserVinyl.user_id == user_id)
            total = (await session.execute(total_stmt)).scalar() or 0

            # Added last 30 days
            last_30 = now - timedelta(days=30)
            added_30_stmt = select(func.count(UserVinyl.id)).where(UserVinyl.user_id == user_id, UserVinyl.created_at >= last_30)
            added_30 = (await session.execute(added_30_stmt)).scalar() or 0

            return {
                "joined_at": user.created_at,
                "days_member": (now - user.created_at).days,
                "total_items": total,
                "added_last_30": added_30
            }
