import asyncio
from app.database.repositories.analytics_repo import AnalyticsRepo
from app.database.models import Vinyl

class AnalyticsService:
    # Ваги подій
    WEIGHTS = {
        "add_to_collection": 5,
        "add_to_wishlist": 4,
        "remove_from_collection": -5,
        "remove_from_wishlist": -4,
        "listen_yt": 3,
        "view_release": 2,
        "view_artist": 2,
        "search_api": 1,
        "search_collection": 1,
        "search_wishlist": 1,
        "share_stats": 6
    }

    @staticmethod
    async def log_action(user_id: int, event_type: str, entity_type: str = None, entity_id: str = None, metadata: dict = None):
        """
        Логує подію та асинхронно оновлює статистику профілю користувача.
        """
        weight = AnalyticsService.WEIGHTS.get(event_type, 1)
        
        # 1. Записуємо "сиру" подію
        await AnalyticsRepo.log_event(user_id, event_type, weight, entity_type, entity_id, metadata)

        # 2. Якщо це проста дія пошуку, оновлювати профіль жанрів/артистів поки не треба (або можна парсити запит)
        # Але якщо це дія з конкретним релізом, ми повинні оновити вподобання
        pass

    @staticmethod
    async def log_vinyl_interaction(user_id: int, vinyl: Vinyl, event_type: str):
        """
        Спеціальний метод для дій з платівкою (додавання, перегляд).
        Автоматично розбирає платівку на жанри, артистів та роки і оновлює статистику.
        """
        weight = AnalyticsService.WEIGHTS.get(event_type, 1)
        
        # Логуємо подію
        await AnalyticsRepo.log_event(
            user_id=user_id, 
            event_type=event_type, 
            weight=weight, 
            entity_type="release", 
            entity_id=str(vinyl.id),
            meta={"title": vinyl.title}
        )

        # Оновлюємо профіль (Artist, Genre, Year)
        tasks = []
        
        if vinyl.artists:
            for artist in vinyl.artists:
                tasks.append(AnalyticsRepo.update_artist_score(user_id, artist.name, weight))
        
        if vinyl.genres:
            for genre in vinyl.genres:
                tasks.append(AnalyticsRepo.update_genre_score(user_id, genre, weight))
                
        if vinyl.year and vinyl.year > 1900:
            tasks.append(AnalyticsRepo.update_year_score(user_id, vinyl.year, weight))
            
        # Виконуємо оновлення паралельно
        if tasks:
            await asyncio.gather(*tasks)