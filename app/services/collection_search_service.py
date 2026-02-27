from app.database.repositories.vinyl_repo import VinylRepo

class CollectionSearchService:
    @staticmethod
    async def search_user_collection(telegram_id: int, query: str, page: int = 0, limit: int = 5):
        return await VinylRepo.search_user_vinyls(telegram_id, query, page, limit)