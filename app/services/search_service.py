import aiohttp
import asyncio
import io
import json
import os
from datetime import datetime, timedelta
from PIL import Image
from pyzbar import pyzbar
from google import genai
from google.genai import types

from app.config import DISCOGS_TOKEN
from app.services.stats_service import StatsService
from app.database.repositories.discogs_cache_repo import DiscogsCacheRepo

# Створюємо папку для логів, якщо її немає
DEBUG_DIR = "discogs_logs"
if not os.path.exists(DEBUG_DIR):
    os.makedirs(DEBUG_DIR)

class SearchService:

    @staticmethod
    async def search_discogs(query: str, search_type: str = "q", per_page: int = 20):
        url = "https://api.discogs.com/database/search"
        headers = {
            "Authorization": f"Discogs token={DISCOGS_TOKEN}",
            "User-Agent": "VinylLibraryBot/1.0"
        }
        params = {search_type: query, "type": "release", "per_page": per_page, "format": "Vinyl"}

        await StatsService.increment_discogs_api()
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Зберігаємо відповідь у файл для відладки
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-')).rstrip().replace(" ", "_")
                    filename = f"search_{search_type}_{safe_query}_{timestamp}.json"
                    filepath = os.path.join(DEBUG_DIR, filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    return data.get("results", [])
                return []

    @staticmethod
    async def get_release_details(release_id: int):
        # 1. Перевіряємо кеш
        cached_item = await DiscogsCacheRepo.get(release_id)
        if cached_item and (datetime.utcnow() - cached_item.cached_at) < timedelta(days=30):
            return cached_item.data

        # 2. Якщо в кеші немає або застарів - робимо запит до API
        url = f"https://api.discogs.com/releases/{release_id}"
        headers = {
            "Authorization": f"Discogs token={DISCOGS_TOKEN}",
            "User-Agent": "VinylLibraryBot/1.0"
        }
        await StatsService.increment_discogs_api()
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Зберігаємо відповідь у файл для відладки
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"release_{release_id}_{timestamp}.json"
                    filepath = os.path.join(DEBUG_DIR, filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    
                    # 3. Зберігаємо успішну відповідь в кеш
                    await DiscogsCacheRepo.upsert(release_id, data)
                    return data
                return None

    @staticmethod
    async def get_price_suggestions(release_id: int):
        """Отримує рекомендовані ціни для релізу (Price Suggestions)."""
        url = f"https://api.discogs.com/marketplace/price_suggestions/{release_id}"
        headers = {
            "Authorization": f"Discogs token={DISCOGS_TOKEN}",
            "User-Agent": "VinylLibraryBot/1.0"
        }
        await StatsService.increment_discogs_api()
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                print(f"❌ Error getting price suggestions for {release_id}: {resp.status} - {await resp.text()}")
                return None

    @staticmethod
    async def search_by_barcode_photo(file_io: io.BytesIO) -> str | None:
        """Розпізнає штрих-код із зображення."""
        try:
            def _decode(fp):
                image = Image.open(fp)
                barcodes = pyzbar.decode(image)
                if barcodes:
                    return barcodes[0].data.decode('utf-8')
                return None

            barcode_data = await asyncio.to_thread(_decode, file_io)
            return barcode_data
        except Exception as e:
            print(f"Error decoding barcode from photo: {e}")
            return None

    @staticmethod
    async def search_by_photo(file_io: io.BytesIO) -> list:
        """
        Аналізує фото за допомогою Google Gemini (новий SDK),
        витягує Artist, Album, Catalog Number і шукає релізи на Discogs.
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("❌ GOOGLE_API_KEY is missing in environment variables.")
            return []

        client = genai.Client(api_key=api_key)

        # Читаємо байти зображення
        file_content = file_io.read()

        # Prompt implementing: Vision API (OCR + matches) -> Gemini -> JSON
        prompt = """
Analyze this image of a vinyl record (cover or label).

Step 1: Vision Analysis (OCR & Recognition)
- Extract all visible text (OCR).
- Identify the release based on visual matches (cover art, label style).

Step 2: Structured Data
Based on the analysis, provide the following details in JSON format:
{
  "artist": "string (Artist Name)",
  "title": "string (Album Title)",
  "catno": "string (Catalog Number found on label/spine, or null)",
  "ocr_text": "string (Combined visible text for fallback search)"
}
"""

        # Список моделей для спроби (від найшвидшої до найпотужнішої)
        model_candidates = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "models/gemini-2.5-flash",
            "models/gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-flash-latest"
        ]
        data = None
        
        for model_name in model_candidates:
            try:
                await StatsService.increment_ai_api()
                response = await asyncio.to_thread(
                    lambda: client.models.generate_content(
                        model=model_name,
                        contents=[
                            types.Part.from_bytes(data=file_content, mime_type="image/jpeg"),
                            prompt
                        ],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    )
                )
                data = json.loads(response.text)
                break # Якщо успішно - виходимо з циклу
            except Exception as e:
                print(f"⚠️ Model {model_name} failed: {e}")
                continue
        
        if not data:
            print("❌ All Gemini models failed to process the image.")
            try:
                print("📋 Available models:")
                for m in client.models.list():
                    print(f" - {m.name}")
            except Exception as e:
                print(f"Error listing models: {e}")
            return []
            
        artist = data.get("artist")
        title = data.get("title")
        catno = data.get("catno")
        ocr_text = data.get("ocr_text", "")

        search_results = []

        # 1. Пошук за номером каталогу (найбільш точний)
        if catno:
            search_results = await SearchService.search_discogs(catno, "catno")

        # 2. Якщо не знайдено, пошук за Артистом + Назвою
        if not search_results and artist and title:
            query = f"{artist} - {title}"
            search_results = await SearchService.search_discogs(query, "q")
        
        # 3. Fallback: Пошук за розпізнаним текстом, якщо нічого не знайдено
        if not search_results and ocr_text:
            # Use a cleaned version of OCR text (first 15 words to avoid noise)
            fallback_query = " ".join(ocr_text.split()[:15])
            if fallback_query:
                search_results = await SearchService.search_discogs(fallback_query, "q")

        return search_results[:20]