import json
import os
import asyncio
from datetime import datetime

STATS_FILE = "stats.json"

class StatsService:
    _lock = asyncio.Lock()

    @staticmethod
    async def _update_stat(key: str):
        async with StatsService._lock:
            today = datetime.now().strftime("%Y-%m-%d")
            
            data = {}
            if os.path.exists(STATS_FILE):
                try:
                    with open(STATS_FILE, "r") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    data = {}
            
            if today not in data:
                data[today] = {"requests": 0, "api_calls": 0}
            
            # Переконаємося, що ключі існують
            if "requests" not in data[today]: data[today]["requests"] = 0
            if "api_discogs" not in data[today]: data[today]["api_discogs"] = 0
            if "api_youtube" not in data[today]: data[today]["api_youtube"] = 0
            if "api_ai" not in data[today]: data[today]["api_ai"] = 0
            
            data[today][key] += 1
            
            await asyncio.to_thread(StatsService._write_file, data)

    @staticmethod
    def _write_file(data):
        with open(STATS_FILE, "w") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    async def increment_bot_request():
        await StatsService._update_stat("requests")

    @staticmethod
    async def increment_discogs_api():
        await StatsService._update_stat("api_discogs")

    @staticmethod
    async def increment_youtube_api():
        await StatsService._update_stat("api_youtube")

    @staticmethod
    async def increment_ai_api():
        await StatsService._update_stat("api_ai")

    @staticmethod
    def get_stats_sync():
        if not os.path.exists(STATS_FILE):
            return {}
        try:
            with open(STATS_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    @staticmethod
    def get_monthly_requests():
        stats = StatsService.get_stats_sync()
        current_month = datetime.now().strftime("%Y-%m")
        total = 0
        for date_str, data in stats.items():
            if date_str.startswith(current_month):
                total += data.get("requests", 0)
        return total

    @staticmethod
    def get_total_api_calls():
        stats = StatsService.get_stats_sync()
        totals = {
            "api_discogs": 0,
            "api_youtube": 0,
            "api_ai": 0
        }
        for data in stats.values():
            totals["api_discogs"] += data.get("api_discogs", 0)
            totals["api_youtube"] += data.get("api_youtube", 0)
            totals["api_ai"] += data.get("api_ai", 0)
        return totals