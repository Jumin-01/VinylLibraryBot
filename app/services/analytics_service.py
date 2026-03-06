import asyncio
from app.database.repositories.analytics_repo import AnalyticsRepo
from app.database.models import Release

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
    async def log_vinyl_interaction(user_id: int, release: Release, event_type: str, user_vinyl_id: int):
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
            entity_type="user_vinyl",
            entity_id=str(user_vinyl_id),
            meta={"title": release.title, "release_id": release.id}
        )

        # Оновлюємо профіль (Artist, Genre, Year)
        tasks = []
        
        if release.artists:
            for artist in release.artists:
                tasks.append(AnalyticsRepo.update_artist_score(user_id, artist.name, weight))
        
        if release.genres:
            for genre in release.genres:
                tasks.append(AnalyticsRepo.update_genre_score(user_id, genre, weight))
                
        if release.year and release.year > 1900:
            tasks.append(AnalyticsRepo.update_year_score(user_id, release.year, weight))
            
        # Виконуємо оновлення паралельно
        if tasks:
            await asyncio.gather(*tasks)