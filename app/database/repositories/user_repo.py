from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models import User

class UserRepo:
    @staticmethod
    async def get_by_id(user_id: int):
        """Отримати користувача за внутрішнім ID"""
        async with AsyncSessionLocal() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @staticmethod
    async def get_by_telegram_id(telegram_id: int):
        """Отримати користувача за Telegram ID"""
        async with AsyncSessionLocal() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @staticmethod
    async def add_or_update(telegram_id: int, username: str | None, first_name: str, last_name: str | None, language_code: str | None):
        """
        Додати нового користувача або оновити існуючого
        """
        async with AsyncSessionLocal() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                # Оновлюємо дані користувача
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.language_code = language_code
            else:
                # Додаємо нового користувача
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code
                )
                session.add(user)

            await session.commit()
            await session.refresh(user)
            return user

    @staticmethod
    async def deactivate(telegram_id: int):
        """Деактивувати користувача (is_active=False)"""
        async with AsyncSessionLocal() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                user.is_active = False
                await session.commit()
                await session.refresh(user)
            return user