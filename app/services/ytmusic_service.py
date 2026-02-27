import asyncio
from ytmusicapi import YTMusic

class YTMusicService:
    @staticmethod
    async def get_album_url(artist: str, title: str) -> str | None:
        """
        Шукає альбом на YouTube Music за назвою та виконавцем і повертає посилання.
        """
        query = f"{artist} {title}"
        try:
            yt = YTMusic()
            # Виконуємо синхронний запит бібліотеки в окремому потоці, щоб не блокувати бота
            search_results = await asyncio.to_thread(yt.search, query, filter="albums")
            if search_results:
                return f"https://music.youtube.com/browse/{search_results[0]['browseId']}"
        except Exception:
            pass
        return None