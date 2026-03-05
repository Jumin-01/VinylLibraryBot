from app.database.repositories.vinyl_repo import VinylRepo
from app.database.repositories.artist_repo import ArtistRepo
from app.database.models import Vinyl
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
        # --- Крок 1: Перевірка існуючого запису та оновлення статусу (коротка транзакція) ---
        async with AsyncSessionLocal() as session:
            existing_vinyl = await VinylRepo.get_by_discogs_id(user_id=telegram_id, discogs_id=release_id, session=session)
            if existing_vinyl:
                if existing_vinyl.is_wishlist != to_wishlist:
                    await VinylRepo.update(existing_vinyl.id, session=session, is_wishlist=to_wishlist)
                    await session.commit()
                # Повертаємо повний об'єкт з усіма зв'язками
                return await VinylRepo.get_by_id(existing_vinyl.id, session=session)

        # --- Крок 2: Отримання даних з API (поза транзакцією) ---
        # Якщо запис не існує, продовжуємо.
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
            vinyl = await VinylRepo.create(
                session=session,
                user_id=telegram_id,
                is_wishlist=to_wishlist,
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
                created_at=datetime.now(),
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
                await ArtistRepo.create(session, vinyl.id, artist_data.get("name"), role=artist_data.get("role"))

            # Додаємо формати
            for f in release_data.get("formats", []):
                await FormatRepo.create(session, vinyl.id, f.get("name"), qty=f.get("qty"), descriptions=f.get("descriptions"))

            # Додаємо зображення
            for img in release_data.get("images", []):
                 await ImageRepo.create(session, vinyl.id, img.get("type", "secondary"), img.get("uri"), uri150=img.get("uri150"), width=img.get("width"), height=img.get("height"))

            # Додаємо ідентифікатори (штрих-код, номер за каталогом)
            for identifier in release_data.get("identifiers", []):
                # Пропускаємо "Other" ідентифікатори без опису, щоб уникнути сміття
                if identifier.get("type") == "Other" and not identifier.get("description"):
                    continue
                await IdentifierRepo.create(
                    session=session,
                    vinyl_id=vinyl.id,
                    type=identifier.get("type"),
                    value=identifier.get("value"),
                    description=identifier.get("description")
                )

            # Додаємо треки
            for t in release_data.get("tracklist", []):
                await TrackRepo.create(session, vinyl.id, t.get("title"), t.get("position"), t.get("duration"))

            await session.commit()

            # Перезавантажуємо об'єкт з бази, щоб підтягнути зв'язки (artists, tracks) для аналітики
            vinyl_with_relations = await VinylRepo.get_by_id(vinyl.id, session=session)

            # --- ANALYTICS INTEGRATION ---
            event_type = "add_to_wishlist" if to_wishlist else "add_to_collection"
            await AnalyticsService.log_vinyl_interaction(telegram_id, vinyl_with_relations, event_type)

            return vinyl_with_relations

    @staticmethod
    async def get_user_collection(telegram_id: int, page: int = 0, limit: int = 5, is_wishlist: bool = False):
        vinyls, total = await VinylRepo.get_user_vinyls(telegram_id, page=page, limit=limit, is_wishlist=is_wishlist)
        
        # Оновлюємо ціни, якщо вони відсутні (послідовно, щоб уникнути блокування БД)
        if vinyls:
            for v in vinyls:
                await VinylService.update_missing_prices(v)
            
        return vinyls, total

    @staticmethod
    async def search_user_collection(telegram_id: int, query: str, page: int = 0, limit: int = 5, is_wishlist: bool = False):
        vinyls, total = await VinylRepo.search_user_vinyls(telegram_id, query, page, limit, is_wishlist=is_wishlist)
        
        # Оновлюємо ціни, якщо вони відсутні (послідовно, щоб уникнути блокування БД)
        if vinyls:
            for v in vinyls:
                await VinylService.update_missing_prices(v)
            
        return vinyls, total

    @staticmethod
    async def get_vinyl_by_id(vinyl_id: int):
        vinyl = await VinylRepo.get_by_id(vinyl_id)
        if not vinyl:
            return None
            
        # Запускаємо оновлення цін у фоні і не чекаємо його, щоб не блокувати відповідь
        asyncio.create_task(VinylService.update_missing_prices(vinyl))
        
        return vinyl

    @staticmethod
    async def update_missing_prices(vinyl: Vinyl):
        """
        Перевіряє наявність цін. Якщо поля пусті - робить запити до API та оновлює БД.
        """
        if not vinyl.discogs_id:
            return

        # Перевіряємо, чи потрібно взагалі щось оновлювати
        if all(p is not None for p in [vinyl.median_price, vinyl.highest_price, vinyl.lowest_price]):
            return

        updates = {}
        tasks = {}

        # Готуємо завдання для `gather`
        if vinyl.median_price is None or vinyl.highest_price is None:
            tasks['suggestions'] = SearchService.get_price_suggestions(vinyl.discogs_id)
        
        if vinyl.lowest_price is None or vinyl.num_for_sale is None:
            tasks['details'] = SearchService.get_release_details(vinyl.discogs_id)

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
                vinyl.median_price = median_price
            if highest_price:
                updates["highest_price"] = highest_price
                vinyl.highest_price = highest_price

        if 'details' in results_map and results_map['details']:
            details = results_map['details']
            if details.get("lowest_price") is not None:
                updates["lowest_price"] = details.get("lowest_price")
                vinyl.lowest_price = details.get("lowest_price")
            if details.get("num_for_sale") is not None:
                updates["num_for_sale"] = details.get("num_for_sale")
                vinyl.num_for_sale = details.get("num_for_sale")

        # Зберігаємо всі оновлення в БД одним запитом
        if updates:
            await VinylRepo.update(vinyl.id, **updates)

    @staticmethod
    async def delete_vinyl(vinyl_id: int):
        vinyl = await VinylRepo.get_by_id(vinyl_id)
        if not vinyl:
            return False

        event_type = "remove_from_wishlist" if vinyl.is_wishlist else "remove_from_collection"
        await AnalyticsService.log_vinyl_interaction(vinyl.user_id, vinyl, event_type)

        return await VinylRepo.delete(vinyl_id)

    @staticmethod
    async def is_vinyl_in_collection(telegram_id: int, discogs_id: int) -> bool:
        vinyl = await VinylRepo.get_by_discogs_id(telegram_id, discogs_id)
        return vinyl is not None and not vinyl.is_wishlist

    @staticmethod
    async def is_vinyl_in_wishlist(telegram_id: int, discogs_id: int) -> bool:
        vinyl = await VinylRepo.get_by_discogs_id(telegram_id, discogs_id)
        return vinyl is not None and vinyl.is_wishlist

    @staticmethod
    async def get_or_create_playlist_url(vinyl_id: int) -> str | None:
        """
        Повертає збережене посилання на плейлист або створює нове через YTMusicService.
        """
        vinyl = await VinylRepo.get_by_id(vinyl_id)
        if not vinyl:
            return None

        # 1. Якщо посилання вже є в базі - повертаємо його
        if vinyl.generated_playlist_url:
            return vinyl.generated_playlist_url

        # 2. Перевіряємо, чи є посилання у інших користувачів для цього ж релізу (Global Cache)
        shared_url = await VinylRepo.get_shared_playlist_url(vinyl.discogs_id)
        if shared_url:
            await VinylRepo.update(vinyl_id, generated_playlist_url=shared_url)
            return shared_url

        # 3. Якщо немає - генеруємо
        artist_name = vinyl.artists[0].name if vinyl.artists else "Unknown"
        track_titles = [t.title for t in vinyl.tracks]
        
        if not track_titles:
            # Якщо треків немає, пробуємо знайти просто альбом
            return await YTMusicService.get_album_url(artist_name, vinyl.title)

        url = await YTMusicService.create_playlist(artist_name, vinyl.title, track_titles)

        # 4. Зберігаємо в базу
        # Не зберігаємо посилання, якщо це просто результати пошуку (fallback)
        if url and "search?q=" not in url:
            await VinylRepo.update(vinyl_id, generated_playlist_url=url)
        
        return url