from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from app.services.user_service import UserService


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        telegram_user = data.get("event_from_user")

        if telegram_user and not telegram_user.is_bot:
            # Використовуємо сервіс для отримання або створення користувача.
            # Це також оновить дані (ім'я, username), якщо вони змінилися.
            user = await UserService.get_or_create_user(telegram_user)
            data["user"] = user
            
        return await handler(event, data)