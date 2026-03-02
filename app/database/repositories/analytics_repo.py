from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.database.db import AsyncSessionLocal
from app.database.models import UserEvent, UserGenreStat, UserArtistStat, UserYearStat

class AnalyticsRepo:
    @staticmethod
    async def log_event(user_id: int, event_type: str, weight: int, entity_type: str = None, entity_id: str = None, meta: dict = None):
        async with AsyncSessionLocal() as session:
            event = UserEvent(
                user_id=user_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id else None,
                weight=weight,
                metadata_json=meta
            )
            session.add(event)
            await session.commit()

    @staticmethod
    async def update_genre_score(user_id: int, genre: str, score_delta: int):
        async with AsyncSessionLocal() as session:
            # SQLite upsert logic
            stmt = sqlite_insert(UserGenreStat).values(user_id=user_id, genre=genre, score=score_delta)
            stmt = stmt.on_conflict_do_update(
                index_elements=['user_id', 'genre'],
                set_=dict(score=UserGenreStat.score + score_delta)
            )
            await session.execute(stmt)
            await session.commit()

    @staticmethod
    async def update_artist_score(user_id: int, artist_name: str, score_delta: int):
        async with AsyncSessionLocal() as session:
            stmt = sqlite_insert(UserArtistStat).values(user_id=user_id, artist_name=artist_name, score=score_delta)
            stmt = stmt.on_conflict_do_update(
                index_elements=['user_id', 'artist_name'],
                set_=dict(score=UserArtistStat.score + score_delta)
            )
            await session.execute(stmt)
            await session.commit()

    @staticmethod
    async def update_year_score(user_id: int, year: int, score_delta: int):
        async with AsyncSessionLocal() as session:
            stmt = sqlite_insert(UserYearStat).values(user_id=user_id, year=year, score=score_delta)
            stmt = stmt.on_conflict_do_update(
                index_elements=['user_id', 'year'],
                set_=dict(score=UserYearStat.score + score_delta)
            )
            await session.execute(stmt)
            await session.commit()
            
    @staticmethod
    async def get_top_genres(user_id: int, limit: int = 5):
        async with AsyncSessionLocal() as session:
            stmt = select(UserGenreStat).where(UserGenreStat.user_id == user_id).order_by(UserGenreStat.score.desc()).limit(limit)
            return (await session.execute(stmt)).scalars().all()

    @staticmethod
    async def get_top_artists(user_id: int, limit: int = 5):
        async with AsyncSessionLocal() as session:
            stmt = select(UserArtistStat).where(UserArtistStat.user_id == user_id).order_by(UserArtistStat.score.desc()).limit(limit)
            return (await session.execute(stmt)).scalars().all()