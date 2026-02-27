import sys
import os
import asyncio

# Додаємо корінь проекту до sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from app.config import BOT_TOKEN
from app.database.db import init_db

# --- Роутери ---
from app.handlers.user_handlers import router as user_router
from app.handlers.search_handlers import router as search_router
from app.handlers.collection_handlers import router as collection_router
from app.handlers.collection_search_handlers import router as collection_search_router
from app.handlers.statistics_handlers import router as statistics_router
from app.middlewares.auth import AuthMiddleware


async def main():
    # Ініціалізація бази даних
    await init_db()

    # Створюємо бота і диспетчер
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # --- Middleware ---
    # Реєструємо middleware для автоматичного збереження/оновлення користувача при кожній дії
    dp.update.outer_middleware(AuthMiddleware())

    # --- Підключаємо роутери ---
    dp.include_router(user_router)
    dp.include_router(search_router)
    dp.include_router(collection_router)
    dp.include_router(collection_search_router)
    dp.include_router(statistics_router)
    
    # --- Запуск polling ---
    print("🚀 Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        input("Press Enter to exit...")