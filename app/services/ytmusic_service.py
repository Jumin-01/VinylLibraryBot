import os
import logging
import asyncio
from urllib.parse import quote
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.services.stats_service import StatsService

logger = logging.getLogger(__name__)

class YTMusicService:
    @staticmethod
    def _get_public_service():
        """
        YouTube service для пошуку через API Key (велика квота)
        """
        api_key = os.getenv("YOUTUBE_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("⚠️ YOUTUBE_API_KEY not set.")
            return None
        try:
            return build('youtube', 'v3', developerKey=api_key, cache_discovery=False)
        except Exception as e:
            logger.error(f"❌ Error initializing public YouTube service: {e}")
            return None

    @staticmethod
    def _normalize(s: str) -> str:
        """A simple normalization function to compare titles."""
        return "".join(c for c in s.lower() if c.isalnum())

    @staticmethod
    async def get_album_url(artist: str, album: str) -> str | None:
        """
        Шукає існуючий плейлист альбому на YouTube Music за допомогою API Key.
        Якщо не знаходить, повертає посилання на пошук.
        """
        query = f"{artist} {album}"

        def _sync_search():
            public_yt = YTMusicService._get_public_service()
            if not public_yt:
                logger.warning("⚠️ Public service not available for search. Returning search link.")
                return f"https://music.youtube.com/search?q={quote(query)}"
            try:
                resp = public_yt.search().list(
                    q=query,
                    type="playlist",
                    part="id",
                    maxResults=1
                ).execute()
                items = resp.get("items", [])
                if items:
                    playlist_id = items[0]['id']['playlistId']
                    logger.info(f"Found existing playlist for '{query}': {playlist_id}")
                    return f"https://music.youtube.com/playlist?list={playlist_id}"
            except HttpError as e:
                if e.resp.status == 403 and "quotaExceeded" in str(e):
                    logger.warning("❌ Public API quota exceeded during search.")
                else:
                    logger.error(f"Search error: {e}")
            except Exception as e:
                logger.error(f"Search error: {e}")
            
            logger.info(f"No playlist found for '{query}'. Returning search link.")
            return f"https://music.youtube.com/search?q={quote(query)}"

        await StatsService.increment_youtube_api()
        return await asyncio.to_thread(_sync_search)

    @staticmethod
    async def create_playlist(artist: str, album_title: str, tracks: list[str]) -> str | None:
        """
        Шукає плейлист альбому на YouTube Music, який відповідає треклисту.
        Повертає URL, якщо знайдено плейлист, що містить >= 70% треків.
        Інакше повертає посилання на пошук.
        """
        query = f"{artist} {album_title}"
        
        if not tracks:
            return await YTMusicService.get_album_url(artist, album_title)

        def _sync_search_and_verify():
            public_yt = YTMusicService._get_public_service()
            if not public_yt:
                logger.warning("⚠️ Public service not available. Returning search link.")
                return f"https://music.youtube.com/search?q={quote(query)}"

            try:
                # 1. Search for candidate playlists
                search_resp = public_yt.search().list(
                    q=query,
                    type="playlist",
                    part="id,snippet",
                    maxResults=5
                ).execute()

                playlist_candidates = search_resp.get("items", [])
                if not playlist_candidates:
                    logger.info(f"No playlists found for '{query}'. Returning search link.")
                    return f"https://music.youtube.com/search?q={quote(query)}"

                normalized_vinyl_tracks = {YTMusicService._normalize(t) for t in tracks}

                # 2. Iterate through candidates and check their tracks
                for playlist_item in playlist_candidates:
                    playlist_id = playlist_item['id']['playlistId']
                    playlist_title = playlist_item['snippet']['title']
                    logger.info(f"Checking playlist: '{playlist_title}' ({playlist_id})")

                    try:
                        # Get tracks for the current playlist
                        playlist_tracks_resp = public_yt.playlistItems().list(
                            part="snippet",
                            playlistId=playlist_id,
                            maxResults=50
                        ).execute()

                        yt_track_items = playlist_tracks_resp.get("items", [])
                        if not yt_track_items:
                            continue

                        normalized_yt_tracks = {YTMusicService._normalize(item['snippet']['title']) for item in yt_track_items}
                        found_matches = sum(1 for vinyl_track_norm in normalized_vinyl_tracks if any(vinyl_track_norm in yt_track_norm for yt_track_norm in normalized_yt_tracks))

                        match_ratio = found_matches / len(normalized_vinyl_tracks)
                        logger.info(f"Playlist '{playlist_title}' match ratio: {match_ratio:.2f}")

                        if match_ratio >= 0.7:
                            logger.info(f"✅ Found suitable playlist with {match_ratio:.2f} match.")
                            return f"https://music.youtube.com/playlist?list={playlist_id}"

                    except HttpError as e:
                        logger.warning(f"Could not fetch items for playlist {playlist_id}: {e}")
                    except Exception as e:
                        logger.error(f"Error processing playlist {playlist_id}: {e}")

            except HttpError as e:
                if e.resp.status == 403 and "quotaExceeded" in str(e):
                    logger.warning("❌ Public API quota exceeded during search.")
                else:
                    logger.error(f"Search error: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")

            # Fallback if no suitable playlist is found
            logger.info(f"No suitable playlist found for '{query}'. Returning search link.")
            return f"https://music.youtube.com/search?q={quote(query)}"

        await StatsService.increment_youtube_api()
        return await asyncio.to_thread(_sync_search_and_verify)