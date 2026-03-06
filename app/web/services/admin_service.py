import os
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from app.database.db import AsyncSessionLocal
from app.database.models import User, UserVinyl, Release
from app.config import LOG_FILE
from app.services.stats_service import StatsService

class AdminService:
    @staticmethod
    async def get_dashboard_stats():
        async with AsyncSessionLocal() as session:
            total_users = await session.scalar(select(func.count(User.id)))
            total_vinyls = await session.scalar(select(func.count(UserVinyl.id)))
            
            # Останні 5 зареєстрованих користувачів
            recent_users_stmt = select(User).order_by(desc(User.created_at)).limit(5)
            recent_users = (await session.execute(recent_users_stmt)).scalars().all()
            
            monthly_requests = await asyncio.to_thread(StatsService.get_monthly_requests)
            
            return {
                "total_users": total_users,
                "total_vinyls": total_vinyls,
                "recent_users": recent_users,
                "monthly_requests": monthly_requests
            }

    @staticmethod
    async def get_all_users():
        async with AsyncSessionLocal() as session:
            stmt = select(User).order_by(User.id)
            users = (await session.execute(stmt)).scalars().all()
            return users

    @staticmethod
    async def get_user_details(user_id: int):
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return None
            
            # Отримуємо кількість платівок
            vinyl_count = await session.scalar(
                select(func.count(UserVinyl.id)).where(UserVinyl.user_id == user.id)
            )
            
            # Отримуємо список платівок
            stmt = select(UserVinyl).options(selectinload(UserVinyl.release)).where(UserVinyl.user_id == user.id).order_by(desc(UserVinyl.created_at))
            vinyls = (await session.execute(stmt)).scalars().all()
            
            return {
                "user": user,
                "vinyl_count": vinyl_count,
                "vinyls": vinyls
            }

    @staticmethod
    async def get_all_vinyls(limit: int = 100):
        async with AsyncSessionLocal() as session:
            # Join with User to display owner
            stmt = (
                select(UserVinyl, User)
                .join(User, UserVinyl.user_id == User.id)
                .options(selectinload(UserVinyl.release).selectinload(Release.artists))
                .order_by(desc(UserVinyl.created_at))
                .limit(limit)
            )
            results = (await session.execute(stmt)).all()
            return results

    @staticmethod
    async def get_vinyl_details(vinyl_id: int):
        async with AsyncSessionLocal() as session:
            stmt = (
                select(UserVinyl)
                .options(
                    selectinload(UserVinyl.release).selectinload(Release.artists),
                    selectinload(UserVinyl.release).selectinload(Release.tracks),
                    selectinload(UserVinyl.user)
                )
                .where(UserVinyl.id == vinyl_id)
            )
            user_vinyl = (await session.execute(stmt)).scalar_one_or_none()
            
            if not user_vinyl:
                return None
                
            # Fetch owner
            # user is already loaded via selectinload(UserVinyl.user)
            
            return {"vinyl": user_vinyl, "owner": user_vinyl.user}

    @staticmethod
    async def toggle_user_active(user_id: int):
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if user:
                # Припускаємо, що у моделі User є поле is_active. 
                # Якщо немає, це поле треба додати в модель.
                # Зазвичай воно є за замовчуванням або використовується статус.
                if hasattr(user, 'is_active'):
                    user.is_active = not user.is_active
                    await session.commit()
                    return True
            return False

    @staticmethod
    def get_logs(lines: int = 100):
        if not os.path.exists(LOG_FILE):
            return ["Log file not found."]
        
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                # Читаємо останні N рядків ефективно
                all_lines = f.readlines()
                return all_lines[-lines:]
        except Exception as e:
            return [f"Error reading logs: {str(e)}"]

    @staticmethod
    def get_user_logs(telegram_id: int, limit: int = 500):
        if not os.path.exists(LOG_FILE):
            return []
        
        search_str = f"User: {telegram_id}"
        matching_lines = []
        
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if search_str in line:
                        matching_lines.append(line.strip())
        except Exception:
            pass
            
        return matching_lines[-limit:]

    @staticmethod
    def clear_logs():
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("")

    @staticmethod
    async def get_chart_data(period: str = "week"):
        async with AsyncSessionLocal() as session:
            today = datetime.now().date()
            labels = []
            filter_date = None
            
            # Налаштування періоду
            if period == "week":
                days = 7
                labels = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days-1, -1, -1)]
                date_expr = func.date
                filter_date = datetime.now() - timedelta(days=7)
            elif period == "month":
                days = 30
                labels = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days-1, -1, -1)]
                date_expr = func.date
                filter_date = datetime.now() - timedelta(days=30)
            elif period == "year":
                # Останні 12 місяців
                curr = today.replace(day=1)
                for _ in range(12):
                    labels.append(curr.strftime('%Y-%m'))
                    # Перехід на попередній місяць
                    curr = (curr - timedelta(days=1)).replace(day=1)
                labels.reverse()
                date_expr = lambda col: func.strftime('%Y-%m', col)
                filter_date = datetime.now() - timedelta(days=365)
            else: # all
                # Для "весь час" групуємо по місяцях, лейбли сформуємо з даних
                date_expr = lambda col: func.strftime('%Y-%m', col)
                filter_date = None
            
            async def fetch_data(model, lbls):
                col = model.created_at
                expr = date_expr(col)
                stmt = (
                    select(expr, func.count(model.id))
                    .group_by(expr)
                )
                if filter_date:
                    stmt = stmt.where(col >= filter_date)

                result = await session.execute(stmt)
                data_map = {row[0]: row[1] for row in result.all()}

                if not lbls:
                    # Якщо лейблів немає (period='all'), беремо всі наявні дати
                    sorted_keys = sorted(data_map.keys())
                    return sorted_keys, [data_map[k] for k in sorted_keys]
                
                return lbls, [data_map.get(l, 0) for l in lbls]

            final_labels, users_data = await fetch_data(User, labels)
            
            # Якщо period='all' і users порожні, спробуємо взяти лейбли з вінілів
            if period == "all" and not final_labels:
                 final_labels, vinyls_data = await fetch_data(UserVinyl, [])
                 # Перезапитуємо юзерів з новими лейблами (будуть нулі)
                 _, users_data = await fetch_data(User, final_labels)
            else:
                 _, vinyls_data = await fetch_data(UserVinyl, final_labels)

            # Отримуємо статистику запитів з JSON
            stats_json = await asyncio.to_thread(StatsService.get_stats_sync)
            requests_data = []
            discogs_data = []
            youtube_data = []
            ai_data = []

            for date_str in final_labels:
                day_stats = stats_json.get(date_str, {})
                requests_data.append(day_stats.get("requests", 0))
                discogs_data.append(day_stats.get("api_discogs", 0))
                youtube_data.append(day_stats.get("api_youtube", 0))
                ai_data.append(day_stats.get("api_ai", 0))

            return {
                "labels": final_labels,
                "users": users_data,
                "vinyls": vinyls_data,
                "requests": requests_data,
                "api_discogs": discogs_data,
                "api_youtube": youtube_data,
                "api_ai": ai_data
            }

    @staticmethod
    def get_env_settings():
        """Читає налаштування з .env файлу та додає статистику."""
        settings = {}
        api_stats = StatsService.get_total_api_calls()
        
        # Зіставлення ключів .env з ключами статистики
        key_to_stat_map = {
            "DISCOGS_TOKEN": "api_discogs",
            "GOOGLE_API_KEY": "api_ai",
        }

        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        stat_key = key_to_stat_map.get(key)
                        stat_value = api_stats.get(stat_key) if stat_key else None
                        settings[key] = {"value": value, "stats": stat_value}
        return settings

    @staticmethod
    def save_env_settings(new_settings: dict):
        """Зберігає налаштування у .env файл."""
        lines = []
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        updated_keys = set()
        new_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0]
                if key in new_settings:
                    new_lines.append(f"{key}={new_settings[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        # Додаємо нові ключі
        for key, value in new_settings.items():
            if key not in updated_keys:
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines.append("\n")
                new_lines.append(f"{key}={value}\n")
                
        with open(".env", "w", encoding="utf-8") as f:
            f.writelines(new_lines)