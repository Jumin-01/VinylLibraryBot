from typing import Any

from datetime import datetime
from aiogram.types import User as TelegramUser
from aiogram_i18n.managers import BaseManager
from app.database.repositories.user_repo import UserRepo


class UserManager(BaseManager):
    async def get_locale(self, event_from_user: TelegramUser, **data: Any) -> str:
        """
        Отримує локаль користувача з контексту або бази даних.
        """
        user = data.get("user")
        if user and user.language_code:
            return user.language_code

        # Резервний варіант, якщо користувача немає в контексті
        if event_from_user:
            db_user = await UserRepo.get_by_telegram_id(event_from_user.id)
            if db_user and db_user.language_code:
                return db_user.language_code

        return self.default_locale

    async def set_locale(self, locale: str, event_from_user: TelegramUser, **data: Any) -> None:
        """
        Встановлює локаль для користувача та зберігає її в базі даних.
        """
        user = data.get("user")
        if user and user.language_code != locale:
            user.language_code = locale  # Оновлюємо об'єкт в пам'яті для поточного запиту
            await UserRepo.add_or_update(
                telegram_id=user.telegram_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=locale,
            )