from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.db import AsyncSessionLocal
from app.database.models import User
from datetime import datetime

class UserRepo:
    @staticmethod
    async def get_by_telegram_id(telegram_id: int, session: AsyncSession | None = None):
        """Fetches a user by their Telegram ID."""
        async def _get(s: AsyncSession):
            return await s.scalar(select(User).where(User.telegram_id == telegram_id))

        if session:
            return await _get(session)
        async with AsyncSessionLocal() as new_session:
            return await _get(new_session)

    @staticmethod
    async def add_or_update(
        telegram_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None,
        language_code: str | None,
    ):
        """
        Adds a new user or updates an existing one.
        Crucially, it always updates `last_active_at` for existing users.
        """
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
            
            if user:
                # Update existing user
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                if language_code is not None:
                    user.language_code = language_code
                # Always update last active time
                user.last_active_at = datetime.utcnow()
            else:
                # Create new user
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code,
                )
                session.add(user)
            
            await session.commit()
            await session.refresh(user)
            return user

    @staticmethod
    async def deactivate(telegram_id: int):
        """Deactivates a user."""
        async with AsyncSessionLocal() as session:
            stmt = update(User).where(User.telegram_id == telegram_id).values(is_active=False)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0