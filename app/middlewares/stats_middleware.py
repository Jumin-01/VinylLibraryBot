import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from app.services.stats_service import StatsService

logger = logging.getLogger("bot_activity")

class StatsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Логування дій користувача
        user = data.get("event_from_user")
        if user and isinstance(event, Update):
            user_str = f"{user.id} (@{user.username or 'None'})"
            action = "Unknown"
            content = ""

            if event.message:
                action = "Message"
                content = event.message.text or event.message.caption or f"[{event.message.content_type}]"
            elif event.callback_query:
                action = "Callback"
                content = event.callback_query.data
            
            if action != "Unknown":
                clean_content = str(content).replace("\n", " ")[:200]
                logger.info(f"User: {user_str} | Action: {action} | Content: {clean_content}")

        await StatsService.increment_bot_request()
        return await handler(event, data)