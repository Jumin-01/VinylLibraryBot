import sys
import os
import asyncio
import logging
import uvicorn
from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles

# Додаємо корінь проекту до sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from app.config import BOT_TOKEN, LOG_FILE
from app.database.db import init_db

# --- Роутери ---
from app.handlers.user_handlers import router as user_router
from app.handlers.search_handlers import router as search_router
from app.handlers.collection_handlers import router as collection_router
from app.handlers.collection_search_handlers import router as collection_search_router
from app.handlers.statistics_handlers import router as statistics_router
from app.handlers.wishlist_handlers import router as wishlist_router
from app.middlewares.auth import AuthMiddleware
from app.middlewares.stats_middleware import StatsMiddleware
from app.web.routes.panel_routes import router as web_router

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Ініціалізація FastAPI
app = FastAPI(title="VinylBot Web")
app.include_router(web_router, prefix="/web", tags=["web"])
# Якщо потрібні статичні файли (css/js), розкоментуйте:
# app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

async def main():
    # Ініціалізація бази даних
    # await init_db()
    pass

    # Створюємо бота і диспетчер
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # --- Middleware ---
    # Реєструємо middleware для автоматичного збереження/оновлення користувача при кожній дії
    dp.update.outer_middleware(AuthMiddleware())
    dp.update.outer_middleware(StatsMiddleware())

    # --- Підключаємо роутери ---
    dp.include_router(user_router)
    dp.include_router(search_router)
    dp.include_router(collection_router)
    dp.include_router(collection_search_router)
    dp.include_router(statistics_router)
    dp.include_router(wishlist_router)
    
    # --- Запуск polling ---
    print("🚀 Bot is starting...")
    
    # Запускаємо веб-сервер та бота паралельно
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    await asyncio.gather(
        dp.start_polling(bot),
        server.serve()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        pass