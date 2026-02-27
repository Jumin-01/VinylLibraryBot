import aiohttp
from rapidfuzz import fuzz
from app.config import DISCOGS_TOKEN
import cv2
import numpy as np
import easyocr
import torch
import asyncio
import re
import gc
from PIL import Image
from pyzbar import pyzbar
import io

gpu_support = torch.cuda.is_available()

class SearchService:
    # Семфор для обмеження одночасних завдань OCR.
    # Встановлено в 1, оскільки ініціалізація Reader є важкою операцією,
    # і ми хочемо уникнути паралельного завантаження моделей у пам'ять.
    ocr_semaphore = asyncio.Semaphore(1)

    @staticmethod
    async def search_discogs(query: str, search_type: str = "q", per_page: int = 50):
        url = "https://api.discogs.com/database/search"
        headers = {"Authorization": f"Discogs token={DISCOGS_TOKEN}"}
        params = {search_type: query, "type": "release", "per_page": per_page, "format": "Vinyl"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                return (await resp.json()).get("results", [])

    @staticmethod
    async def get_release_details(release_id: int):
        url = f"https://api.discogs.com/releases/{release_id}"
        headers = {"Authorization": f"Discogs token={DISCOGS_TOKEN}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None

    @staticmethod
    async def search_by_barcode_photo(file_io: io.BytesIO) -> str | None:
        """
        Розпізнає штрих-код із зображення.
        """
        try:
            # Виконуємо обробку зображення в окремому потоці, щоб не блокувати бота
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
    async def search_by_photo(file_io):
        """
        Розпізнає текст з зображення, шукає реліз на Discogs та повертає найкращі результати.
        Обмежує одночасні операції OCR та очищує пам'ять.
        """
        all_text = []
        
        # Обмежуємо кількість одночасних розпізнавань за допомогою семафора
        async with SearchService.ocr_semaphore:
            file_bytes = np.frombuffer(file_io.read(), np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            
            if img is None:
                del file_bytes
                gc.collect()
                return []

            # Resize image to speed up OCR (max dimension 1024px)
            h, w = img.shape[:2]
            if max(h, w) > 1024:
                scale = 1024 / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            # Попередня обробка зображення
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            reader = None # Ініціалізуємо змінну перед блоком try
            try:
                # Створюємо Reader "на льоту" для кожного запиту. Це повільніше, але економить пам'ять.
                reader = easyocr.Reader(['en'], gpu=gpu_support, verbose=False)
                ocr_results = await asyncio.to_thread(reader.readtext, gray, detail=1, mag_ratio=1.5)
                all_text = [t for (_, t, conf) in ocr_results if conf > 0.4]
            finally:
                # Послідовно видаляємо всі великі об'єкти, щоб звільнити пам'ять
                del file_bytes
                del img
                del gray
                if 'ocr_results' in locals():
                    del ocr_results
                # Найважливіше: видаляємо сам об'єкт Reader, щоб вивільнити модель з пам'яті
                if reader is not None:
                    del reader
                
                # Примусово викликаємо збирач сміття
                gc.collect()
                # Якщо використовується GPU, додатково очищуємо кеш PyTorch
                if gpu_support:
                    torch.cuda.empty_cache()

        if not all_text:
            return []

        # Очищення тексту
        noise_words = {
            "STEREO", "MONO", "SIDE", "RPM", "33", "45", "SIDE 1", "SIDE 2", "SIDE A", "SIDE B",
            "33 1/3", "COPYRIGHT", "RIGHTS", "RESERVED", "MANUFACTURED", "DISTRIBUTED", "RECORDS",
            "THE", "AND", "OF", "IN", "MADE", "BY", "ALL"
        }
        cleaned = list(set(t.upper() for t in all_text if len(t.strip()) > 2 and t.upper() not in noise_words))

        # Пошук кандидатів на номер за каталогом
        broad_pattern = re.compile(r'\b[A-Z0-9]+(?:[- ][A-Z0-9]+)*\b')
        cat_candidates = []
        for text in cleaned:
            matches = broad_pattern.findall(text)
            for m in matches:
                if any(c.isdigit() for c in m) and len(m) > 3:
                    if m.isdigit() and 1950 <= int(m) <= 2030:
                        continue
                    cat_candidates.append(m)
        cat_candidates = list(set(cat_candidates))

        # Пошук
        search_results = []
        # 1. Спробувати за номером каталогу (найбільш надійний)
        for catno in cat_candidates:
            results = await SearchService.search_discogs(catno, "catno")
            if results:
                search_results.extend(results)

        # 2. Якщо нічого не знайдено, спробувати за іншими рядками з цифрами
        if not search_results:
            digit_lines = [t for t in cleaned if any(c.isdigit() for c in t) and t not in cat_candidates]
            for line in digit_lines[:3]:
                results = await SearchService.search_discogs(line, "q")
                if results:
                    search_results.extend(results)
                    break # Зупиняємось після першого успішного пошуку

        # 3. Fallback: пошук за найдовшими текстовими рядками (ймовірно, артист/назва)
        if not search_results:
            text_lines = sorted([t for t in cleaned if not any(c.isdigit() for c in t)], key=len, reverse=True)
            query = " ".join(text_lines[:2])
            if query:
                search_results = await SearchService.search_discogs(query, "q")

        if not search_results:
            return []

        # Ранжування результатів
        text_lines = sorted([t for t in cleaned if not any(c.isdigit() for c in t)], key=len, reverse=True)
        candidate_artist = text_lines[0] if text_lines else ""
        candidate_title = text_lines[1] if len(text_lines) > 1 else ""

        scored = []
        unique_releases = {r['id']: r for r in search_results}.values() # Унікальні релізи

        for release in unique_releases:
            s = SearchService.score_release(release, candidate_artist, candidate_title, cat_candidates)
            scored.append((s, release))

        scored.sort(reverse=True, key=lambda x: x[0])
        final_results = [r for (_, r) in scored[:20]] # Повертаємо топ-20

        return final_results

    @staticmethod
    def score_release(release, ocr_artist: str, ocr_title: str, ocr_catnos: list[str]):
        score = 0
        discogs_title = release.get("title", "").upper()
        discogs_catno = release.get("catno", "").upper()
        discogs_label = " ".join(release.get("label", [])).upper()

        if ocr_artist:
            score += fuzz.partial_ratio(ocr_artist, discogs_title)
        if ocr_title:
            score += fuzz.partial_ratio(ocr_title, discogs_title)
        for cat in ocr_catnos:
            if cat in discogs_catno:
                score += 120
            else:
                score += fuzz.partial_ratio(cat, discogs_catno)
        if ocr_artist and ocr_artist in discogs_label:
            score += 40
        return score