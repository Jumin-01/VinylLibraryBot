from app.database.repositories.vinyl_repo import VinylRepo
from app.database.repositories.artist_repo import ArtistRepo
from app.database.repositories.user_repo import UserRepo
from app.database.models import Release, UserVinyl
from app.database.db import AsyncSessionLocal
from app.database.repositories.format_repo import FormatRepo
from app.database.repositories.track_repo import TrackRepo
from app.database.repositories.image_repo import ImageRepo
from app.database.repositories.identifier_repo import IdentifierRepo
from app.services.search_service import SearchService
from app.services.ytmusic_service import YTMusicService
from app.services.analytics_service import AnalyticsService
from datetime import datetime
import asyncio

class VinylService:
    @staticmethod
    def _extract_prices(suggestions: dict | None):
        """Helper to extract VG+ and Mint prices robustly."""
        if not suggestions:
            return None, None
            
        vg_plus = suggestions.get("Very Good Plus (VG+)", {}).get("value")
        mint = suggestions.get("Mint (M)", {}).get("value")
        
        # Fallback search if exact keys missing
        if not vg_plus:
            for k, v in suggestions.items():
                if "Very Good Plus" in k:
                    vg_plus = v.get("value")
                    break
        
        if not mint:
            for k, v in suggestions.items():
                if "Mint" in k and "Near" not in k:
                    mint = v.get("value")
                    break
                    
        return vg_plus, mint

    @staticmethod
    async def add_vinyl_from_discogs(telegram_id: int, release_id: int, to_wishlist: bool = False, release_data: dict | None = None):
        """
        Отримує дані з Discogs.
        Якщо платівка вже існує, оновлює її статус (колекція/вішліст), якщо потрібно.
        Якщо не існує - створює нову.
        Все в рамках однієї транзакції.
        """
        user = await UserRepo.get_by_telegram_id(telegram_id)
        if not user:
            # This should not happen if AuthMiddleware is working correctly
            return None
        internal_user_id = user.id

        # --- Крок 1: Перевірка існуючого релізу та платівки користувача ---
        async with AsyncSessionLocal() as session:
            release = await VinylRepo.get_release_by_discogs_id(release_id, session=session)
            if release:
                user_vinyl = await VinylRepo.get_user_vinyl_by_release_id(internal_user_id, release.id, session=session)
                if user_vinyl:
                    # Платівка вже є у користувача, можливо треба оновити статус
                    if user_vinyl.is_wishlist != to_wishlist:
                        await VinylRepo.update_user_vinyl(user_vinyl.id, session=session, is_wishlist=to_wishlist)
                        await session.commit()
                    # Повертаємо повний об'єкт
                    return await VinylRepo.get_user_vinyl_by_id(user_vinyl.id, session=session)
                else:
                    # Реліз існує, але не у цього користувача. Створюємо зв'язок.
                    new_user_vinyl = await VinylRepo.create_user_vinyl(
                        session, user_id=internal_user_id, release_id=release.id, is_wishlist=to_wishlist
                    )
                    await session.commit()
                    # Логуємо аналітику
                    event_type = "add_to_wishlist" if to_wishlist else "add_to_collection"
                    await AnalyticsService.log_vinyl_interaction(internal_user_id, release, event_type, new_user_vinyl.id)
                    # Повертаємо повний об'єкт
                    return await VinylRepo.get_user_vinyl_by_id(new_user_vinyl.id, session=session)

        # --- Крок 2: Отримання даних з API (поза транзакцією) ---
        # Якщо реліз не існує в нашій БД, отримуємо дані з Discogs
        if not release_data:
            results = await asyncio.gather(
                SearchService.get_release_details(release_id),
                SearchService.get_price_suggestions(release_id)
            )
            release_data, suggestions = results
        else:
            # Якщо дані релізу вже є (з кешу пошуку), отримуємо тільки ціни
            suggestions = await SearchService.get_price_suggestions(release_id)

        if not release_data:
            return None

        # Отримуємо catno з labels, оскільки в корені об'єкта release його немає
        catno = None
        labels = release_data.get("labels", [])
        if labels:
            catno = labels[0].get("catno")

        community_data = release_data.get("community", {})
        rating_data = community_data.get("rating", {})

        median_price, highest_price = VinylService._extract_prices(suggestions) # _extract_prices вже обробляє None

        # --- Крок 3: Створення нового запису (нова, окрема транзакція) ---
        async with AsyncSessionLocal() as session:
            # Створюємо сам реліз
            release = await VinylRepo.create_release(
                session=session,
                title=release_data.get("title"),
                discogs_id=release_data.get("id"),
                year=release_data.get("year"),
                released=release_data.get("released"),
                country=release_data.get("country"),
                catno=catno,
                notes=release_data.get("notes"),
                cover_image=release_data.get("images", [{}])[0].get("uri") if release_data.get("images") else None,
                genres=release_data.get("genres"),
                styles=release_data.get("styles"),
                # Додаткові поля
                lowest_price=release_data.get("lowest_price"),
                num_for_sale=release_data.get("num_for_sale"),
                rating_average=rating_data.get("average"),
                rating_count=rating_data.get("count"),
                have_count=community_data.get("have"),
                want_count=community_data.get("want"),
                median_price=median_price,
                highest_price=highest_price
            )

            # Додаємо артистів
            for artist_data in release_data.get("artists", []):
                await ArtistRepo.create(session, release.id, artist_data.get("name"), role=artist_data.get("role"))

            # Додаємо формати
            for f in release_data.get("formats", []):
                await FormatRepo.create(session, release.id, f.get("name"), qty=f.get("qty"), descriptions=f.get("descriptions"))

            # Додаємо зображення
            for img in release_data.get("images", []):
                 await ImageRepo.create(session, release.id, img.get("type", "secondary"), img.get("uri"), uri150=img.get("uri150"), width=img.get("width"), height=img.get("height"))

            # Додаємо ідентифікатори (штрих-код, номер за каталогом)
            for identifier in release_data.get("identifiers", []):
                # Пропускаємо "Other" ідентифікатори без опису, щоб уникнути сміття
                if identifier.get("type") == "Other" and not identifier.get("description"):
                    continue
                await IdentifierRepo.create(
                    session=session,
                    release_id=release.id,
                    type=identifier.get("type"),
                    value=identifier.get("value"),
                    description=identifier.get("description")
                )

            # Додаємо треки
            for t in release_data.get("tracklist", []):
                await TrackRepo.create(session, release.id, t.get("title"), t.get("position"), t.get("duration"))

            # Створюємо запис для користувача
            user_vinyl = await VinylRepo.create_user_vinyl(
                session, user_id=internal_user_id, release_id=release.id, is_wishlist=to_wishlist
            )
            await session.commit()

            # Перезавантажуємо об'єкт з бази, щоб підтягнути зв'язки для аналітики
            final_user_vinyl = await VinylRepo.get_user_vinyl_by_id(user_vinyl.id, session=session)

            # --- ANALYTICS INTEGRATION ---
            event_type = "add_to_wishlist" if to_wishlist else "add_to_collection"
            await AnalyticsService.log_vinyl_interaction(internal_user_id, final_user_vinyl.release, event_type, final_user_vinyl.id)

            return final_user_vinyl

    @staticmethod
    async def get_user_collection(telegram_id: int, page: int = 0, limit: int = 5, is_wishlist: bool = False):
        user = await UserRepo.get_by_telegram_id(telegram_id)
        if not user:
            return [], 0
        user_vinyls, total = await VinylRepo.get_user_vinyls(user.id, page=page, limit=limit, is_wishlist=is_wishlist)
        
        # Оновлюємо ціни, якщо вони відсутні (послідовно, щоб уникнути блокування БД)
        if user_vinyls:
            for uv in user_vinyls:
                await VinylService.update_missing_prices(uv.release)
            
        return user_vinyls, total

    @staticmethod
    async def search_user_collection(telegram_id: int, query: str, page: int = 0, limit: int = 5, is_wishlist: bool = False):
        user = await UserRepo.get_by_telegram_id(telegram_id)
        if not user:
            return [], 0
        user_vinyls, total = await VinylRepo.search_user_vinyls(user.id, query, page, limit, is_wishlist=is_wishlist)
        
        # Оновлюємо ціни, якщо вони відсутні (послідовно, щоб уникнути блокування БД)
        if user_vinyls:
            for uv in user_vinyls:
                await VinylService.update_missing_prices(uv.release)
            
        return user_vinyls, total

    @staticmethod
    async def get_user_vinyl_by_id(user_vinyl_id: int):
        user_vinyl = await VinylRepo.get_user_vinyl_by_id(user_vinyl_id)
        if not user_vinyl:
            return None
            
        # Запускаємо оновлення цін у фоні і не чекаємо його, щоб не блокувати відповідь
        asyncio.create_task(VinylService.update_missing_prices(user_vinyl.release))
        
        return user_vinyl

    @staticmethod
    async def update_missing_prices(release: Release):
        """
        Перевіряє наявність цін. Якщо поля пусті - робить запити до API та оновлює БД.
        """
        if not release.discogs_id:
            return

        # Перевіряємо, чи потрібно взагалі щось оновлювати
        if all(p is not None for p in [release.median_price, release.highest_price, release.lowest_price]):
            return

        updates = {}
        tasks = {}

        # Готуємо завдання для `gather`
        if release.median_price is None or release.highest_price is None:
            tasks['suggestions'] = SearchService.get_price_suggestions(release.discogs_id)
        
        if release.lowest_price is None or release.num_for_sale is None:
            tasks['details'] = SearchService.get_release_details(release.discogs_id)

        if not tasks:
            return

        # Виконуємо запити паралельно
        results = await asyncio.gather(*tasks.values())
        results_map = dict(zip(tasks.keys(), results))

        # Обробляємо результати
        if 'suggestions' in results_map and results_map['suggestions']:
            median_price, highest_price = VinylService._extract_prices(results_map['suggestions'])
            if median_price:
                updates["median_price"] = median_price
                release.median_price = median_price
            if highest_price:
                updates["highest_price"] = highest_price
                release.highest_price = highest_price

        if 'details' in results_map and results_map['details']:
            details = results_map['details']
            if details.get("lowest_price") is not None:
                updates["lowest_price"] = details.get("lowest_price")
                release.lowest_price = details.get("lowest_price")
            if details.get("num_for_sale") is not None:
                updates["num_for_sale"] = details.get("num_for_sale")
                release.num_for_sale = details.get("num_for_sale")

        # Зберігаємо всі оновлення в БД одним запитом
        if updates:
            await VinylRepo.update_release(release.id, **updates)

    @staticmethod
    async def delete_vinyl(user_vinyl_id: int):
        user_vinyl = await VinylRepo.get_user_vinyl_by_id(user_vinyl_id)
        if not user_vinyl:
            return False

        event_type = "remove_from_wishlist" if user_vinyl.is_wishlist else "remove_from_collection"
        await AnalyticsService.log_vinyl_interaction(user_vinyl.user_id, user_vinyl.release, event_type, user_vinyl.id)

        return await VinylRepo.delete_user_vinyl(user_vinyl_id)

    @staticmethod
    async def is_vinyl_in_collection(telegram_id: int, discogs_id: int) -> bool:
        user = await UserRepo.get_by_telegram_id(telegram_id)
        if not user:
            return False
        release = await VinylRepo.get_release_by_discogs_id(discogs_id)
        if not release:
            return False
        user_vinyl = await VinylRepo.get_user_vinyl_by_release_id(user.id, release.id)
        return user_vinyl is not None and not user_vinyl.is_wishlist

    @staticmethod
    async def is_vinyl_in_wishlist(telegram_id: int, discogs_id: int) -> bool:
        user = await UserRepo.get_by_telegram_id(telegram_id)
        if not user:
            return False
        release = await VinylRepo.get_release_by_discogs_id(discogs_id)
        if not release:
            return False
        user_vinyl = await VinylRepo.get_user_vinyl_by_release_id(user.id, release.id)
        return user_vinyl is not None and user_vinyl.is_wishlist

    @staticmethod
    async def get_or_create_playlist_url(user_vinyl_id: int) -> str | None:
        """
        Повертає збережене посилання на плейлист або створює нове через YTMusicService.
        """
        user_vinyl = await VinylRepo.get_user_vinyl_by_id(user_vinyl_id)
        if not user_vinyl or not user_vinyl.release:
            return None
        
        release = user_vinyl.release

        # 1. Якщо посилання вже є в базі - повертаємо його
        if release.generated_playlist_url:
            return release.generated_playlist_url

        # 2. Перевіряємо, чи є посилання у інших користувачів для цього ж релізу (Global Cache)
        shared_url = await VinylRepo.get_shared_playlist_url(release.discogs_id)
        if shared_url:
            await VinylRepo.update_release(release.id, generated_playlist_url=shared_url)
            return shared_url

        # 3. Якщо немає - генеруємо
        artist_name = release.artists[0].name if release.artists else "Unknown"
        track_titles = [t.title for t in release.tracks]
        
        if not track_titles:
            # Якщо треків немає, пробуємо знайти просто альбом
            return await YTMusicService.get_album_url(artist_name, release.title)

        url = await YTMusicService.create_playlist(artist_name, release.title, track_titles)

        # 4. Зберігаємо в базу
        # Не зберігаємо посилання, якщо це просто результати пошуку (fallback)
        if url and "search?q=" not in url:
            await VinylRepo.update_release(release.id, generated_playlist_url=url)
        
        return url