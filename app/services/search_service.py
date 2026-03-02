import aiohttp
import asyncio
import io
import json
import os
from PIL import Image
from pyzbar import pyzbar
from google import genai
from google.genai import types

from app.config import DISCOGS_TOKEN
from app.services.stats_service import StatsService

class SearchService:

    @staticmethod
    async def search_discogs(query: str, search_type: str = "q", per_page: int = 50):
        url = "https://api.discogs.com/database/search"
        headers = {"Authorization": f"Discogs token={DISCOGS_TOKEN}"}
        params = {search_type: query, "type": "release", "per_page": per_page, "format": "Vinyl"}

        await StatsService.increment_discogs_api()
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    return (await resp.json()).get("results", [])
                return []

    @staticmethod
    async def get_release_details(release_id: int):
        url = f"https://api.discogs.com/releases/{release_id}"
        headers = {"Authorization": f"Discogs token={DISCOGS_TOKEN}"}
        await StatsService.increment_discogs_api()
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
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
        seen_ids = set()

        # 1. Search by Catalog Number (Most accurate)
        if catno:
            cat_results = await SearchService.search_discogs(catno, "catno")
            for res in cat_results:
                if res["id"] not in seen_ids:
                    search_results.append(res)
                    seen_ids.add(res["id"])

        # 2. Search by Artist + Title (If CatNo failed or to enrich results)
        if artist and title:
            query = f"{artist} - {title}"
            text_results = await SearchService.search_discogs(query, "q")
            for res in text_results:
                if res["id"] not in seen_ids:
                    search_results.append(res)
                    seen_ids.add(res["id"])
        
        # 3. Fallback: Search by OCR Text (If nothing found yet)
        if not search_results and ocr_text:
            # Use a cleaned version of OCR text (first 15 words to avoid noise)
            fallback_query = " ".join(ocr_text.split()[:15])
            fallback_results = await SearchService.search_discogs(fallback_query, "q")
            for res in fallback_results:
                if res["id"] not in seen_ids:
                    search_results.append(res)
                    seen_ids.add(res["id"])

        return search_results[:20]