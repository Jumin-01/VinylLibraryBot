from app.database.repositories.vinyl_repo import VinylRepo
from app.database.repositories.artist_repo import ArtistRepo
from app.database.repositories.format_repo import FormatRepo
from app.database.repositories.track_repo import TrackRepo
from app.database.repositories.image_repo import ImageRepo
from app.database.repositories.identifier_repo import IdentifierRepo
from app.services.search_service import SearchService
from app.services.ytmusic_service import YTMusicService
from datetime import datetime

class VinylService:
    @staticmethod
    async def add_vinyl_from_discogs(telegram_id: int, release_id: int):
        """
        Отримує повні дані про реліз з Discogs за ID та додає платівку до колекції користувача.
        """
        release_data = await SearchService.get_release_details(release_id)
        if not release_data:
            return None

        # Отримуємо catno з labels, оскільки в корені об'єкта release його немає
        catno = None
        labels = release_data.get("labels", [])
        if labels:
            catno = labels[0].get("catno")

        community_data = release_data.get("community", {})
        rating_data = community_data.get("rating", {})

        vinyl = await VinylRepo.create(
            user_id=telegram_id,
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
            want_count=community_data.get("want")
        )

        # Додаємо артистів
        for artist_data in release_data.get("artists", []):
            await ArtistRepo.create(vinyl.id, artist_data.get("name"), role=artist_data.get("role"))

        # Додаємо формати
        for f in release_data.get("formats", []):
            await FormatRepo.create(vinyl.id, f.get("name"), qty=f.get("qty"), descriptions=f.get("descriptions"))

        # Додаємо зображення
        for img in release_data.get("images", []):
             await ImageRepo.create(vinyl.id, img.get("type", "secondary"), img.get("uri"), uri150=img.get("uri150"), width=img.get("width"), height=img.get("height"))

        # Додаємо ідентифікатори (штрих-код, номер за каталогом)
        for identifier in release_data.get("identifiers", []):
            # Пропускаємо "Other" ідентифікатори без опису, щоб уникнути сміття
            if identifier.get("type") == "Other" and not identifier.get("description"):
                continue
            await IdentifierRepo.create(
                vinyl_id=vinyl.id,
                type=identifier.get("type"),
                value=identifier.get("value"),
                description=identifier.get("description")
            )

        # Додаємо треки
        for t in release_data.get("tracklist", []):
            await TrackRepo.create(vinyl.id, t.get("title"), t.get("position"), t.get("duration"))

        return vinyl

    @staticmethod
    async def get_user_collection(telegram_id: int, page: int = 0, limit: int = 5):
        return await VinylRepo.get_user_vinyls(telegram_id, page=page, limit=limit)

    @staticmethod
    async def get_vinyl_by_id(vinyl_id: int):
        return await VinylRepo.get_by_id(vinyl_id)

    @staticmethod
    async def delete_vinyl(vinyl_id: int):
        return await VinylRepo.delete(vinyl_id)

    @staticmethod
    async def is_vinyl_in_collection(telegram_id: int, discogs_id: int) -> bool:
        vinyl = await VinylRepo.get_by_discogs_id(telegram_id, discogs_id)
        return vinyl is not None

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

        # 2. Якщо немає - генеруємо
        artist_name = vinyl.artists[0].name if vinyl.artists else "Unknown"
        track_titles = [t.title for t in vinyl.tracks]
        
        if not track_titles:
            # Якщо треків немає, пробуємо знайти просто альбом
            return await YTMusicService.get_album_url(artist_name, vinyl.title)

        url = await YTMusicService.create_playlist(artist_name, vinyl.title, track_titles)

        # 3. Зберігаємо в базу
        # Не зберігаємо посилання, якщо це просто результати пошуку (fallback)
        if url and "search?q=" not in url:
            await VinylRepo.update(vinyl_id, generated_playlist_url=url)
        
        return url