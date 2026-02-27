from app.database.repositories.statistics_repo import StatisticsRepo

class StatisticsService:
    @staticmethod
    async def get_user_statistics(telegram_id: int):
        """
        Отримує статистику колекції користувача.
        """
        return await StatisticsRepo.get_stats(telegram_id)

    @staticmethod
    async def get_user_activity(telegram_id: int):
        return await StatisticsRepo.get_activity_stats(telegram_id)
