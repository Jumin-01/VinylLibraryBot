from app.database.repositories.user_repo import UserRepo

class UserService:
    @staticmethod
    async def get_or_create_user(telegram_user):
        """
        Додає нового користувача або оновлює існуючого
        telegram_user: Telegram User object
        """
        return await UserRepo.add_or_update(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=telegram_user.language_code
        )

    @staticmethod
    async def deactivate_user(telegram_id: int):
        return await UserRepo.deactivate(telegram_id)
    
    @staticmethod
    async def get_user_by_telegram_id(telegram_id: int):
        return await UserRepo.get_by_telegram_id(telegram_id)