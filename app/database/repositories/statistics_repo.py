from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.database.db import AsyncSessionLocal
from app.database.models import Vinyl, Artist, User
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from app.services.valuation_service import ValuationService

class StatisticsRepo:
    @staticmethod
    async def get_stats(telegram_id: int):
        async with AsyncSessionLocal() as session:
            # 1. Загальна кількість релізів
            total_stmt = select(func.count(Vinyl.id)).where(Vinyl.user_id == telegram_id)
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
                .join(Vinyl)
                .where(Vinyl.user_id == telegram_id)
            )
            unique_artists = (await session.execute(artists_stmt)).scalar() or 0

            # 3. Кількість країн
            countries_stmt = (
                select(func.count(func.distinct(Vinyl.country)))
                .where(Vinyl.user_id == telegram_id)
                .where(Vinyl.country.is_not(None))
            )
            unique_countries = (await session.execute(countries_stmt)).scalar() or 0

            # 4, 5, 6. Роки (найстаріший, найновіший, середній)
            years_stmt = (
                select(
                    func.min(Vinyl.year),
                    func.max(Vinyl.year),
                    func.avg(Vinyl.year)
                )
                .where(Vinyl.user_id == telegram_id)
                .where(Vinyl.year.is_not(None))
                .where(Vinyl.year > 0) # Фільтруємо 0 або некоректні роки
            )
            min_year, max_year, avg_year = (await session.execute(years_stmt)).one()

            # --- Розширена статистика ---

            # Топ-5 Артистів
            top_artists_stmt = (
                select(Artist.name, func.count(Vinyl.id))
                .join(Vinyl)
                .where(Vinyl.user_id == telegram_id)
                .group_by(Artist.name)
                .order_by(func.count(Vinyl.id).desc())
                .limit(5)
            )
            top_artists = (await session.execute(top_artists_stmt)).all()

            # Топ-5 Країн
            top_countries_stmt = (
                select(Vinyl.country, func.count(Vinyl.id))
                .where(Vinyl.user_id == telegram_id)
                .where(Vinyl.country.is_not(None))
                .group_by(Vinyl.country)
                .order_by(func.count(Vinyl.id).desc())
                .limit(5)
            )
            top_countries = (await session.execute(top_countries_stmt)).all()

            # Топ релізів за рейтингом
            top_rated_stmt = (
                select(Vinyl)
                .options(selectinload(Vinyl.artists))
                .where(Vinyl.user_id == telegram_id)
                .where(Vinyl.rating_average.is_not(None))
                .order_by(Vinyl.rating_average.desc())
                .limit(5)
            )
            top_rated_releases = (await session.execute(top_rated_stmt)).scalars().all()

            # Топ найрідкісніших релізів (найменше 'have' на Discogs)
            rarest_stmt = (
                select(Vinyl)
                .options(selectinload(Vinyl.artists))
                .where(Vinyl.user_id == telegram_id)
                .where(Vinyl.have_count.is_not(None))
                .where(Vinyl.have_count > 0)
                .order_by(Vinyl.have_count.asc())
                .limit(5)
            )
            rarest_releases = (await session.execute(rarest_stmt)).scalars().all()

            # --- Обробка JSON полів (Жанри, Стилі) та Десятиліть в Python ---
            all_vinyls_stmt = (
                select(Vinyl)
                .options(selectinload(Vinyl.artists))
                .where(Vinyl.user_id == telegram_id)
            )
            all_vinyls = (await session.execute(all_vinyls_stmt)).scalars().all()

            genre_counts = Counter()
            style_counts = Counter()
            genre_ratings = defaultdict(list)
            genre_artists = defaultdict(set)
            decade_counts = Counter()
            total_collection_value = 0.0
            valued_releases = []

            for v in all_vinyls:
                # Жанри та Стилі
                if v.genres:
                    for g in v.genres:
                        genre_counts[g] += 1
                        if v.rating_average:
                            genre_ratings[g].append(v.rating_average)
                        for a in v.artists:
                            genre_artists[g].add(a.name)
                if v.styles:
                    for s in v.styles:
                        style_counts[s] += 1
                
                # Десятиліття
                if v.year and isinstance(v.year, int) and v.year > 1900:
                    decade = (v.year // 10) * 10
                    decade_counts[decade] += 1
                
                # Оцінка вартості
                val = ValuationService.calculate_smart_value(
                    v.lowest_price,
                    v.median_price,
                    v.highest_price,
                    v.num_for_sale,
                    v.have_count,
                    v.want_count
                )
                if val:
                    total_collection_value += val['avg']
                    valued_releases.append({'vinyl': v, 'value': val})

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
            stmt = select(User).where(User.telegram_id == telegram_id)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if not user:
                return None
            
            now = datetime.utcnow()
            
            # Total vinyls
            total_stmt = select(func.count(Vinyl.id)).where(Vinyl.user_id == telegram_id)
            total = (await session.execute(total_stmt)).scalar() or 0

            # Added last 30 days
            last_30 = now - timedelta(days=30)
            added_30_stmt = select(func.count(Vinyl.id)).where(Vinyl.user_id == telegram_id, Vinyl.created_at >= last_30)
            added_30 = (await session.execute(added_30_stmt)).scalar() or 0

            return {
                "joined_at": user.created_at,
                "days_member": (now - user.created_at).days,
                "total_items": total,
                "added_last_30": added_30
            }
