from app.database.repositories.user_repo import UserRepo
from datetime import datetime

class UserService:
    @staticmethod
    async def get_or_create_user(telegram_user):
        """
        Додає нового користувача або оновлює дані існуючого.
        Мова з налаштувань Telegram використовується тільки при створенні нового користувача,
        щоб не перезаписувати вибір, зроблений через /language.
        """
        existing_user = await UserRepo.get_by_telegram_id(telegram_user.id)

        if existing_user:
            # Користувач існує: оновлюємо ім'я/юзернейм, але НЕ мову.
            # Це запобігає перезапису мови, встановленої командою /language.
            return await UserRepo.add_or_update(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                language_code=existing_user.language_code,
            )
        else:
            # Новий користувач: створюємо запис з мовою з його клієнта Telegram.
            return await UserRepo.add_or_update(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                language_code=telegram_user.language_code,
            )

    @staticmethod
    async def deactivate_user(telegram_id: int):
        return await UserRepo.deactivate(telegram_id)
    
    @staticmethod
    async def get_user_by_telegram_id(telegram_id: int):
        return await UserRepo.get_by_telegram_id(telegram_id)