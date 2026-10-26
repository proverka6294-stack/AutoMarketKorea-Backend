"""Фоновый сервис: автоматически загружает машины с Carapis, пока не наберется нужное количество."""
import asyncio
import logging

import httpx
from sqlalchemy import func, select

from app.enums import SourceStatus
from app.importers.parsing import parse_items
from app.importers.runner import _upsert_records
from app.models import Car, Source, utcnow

logger = logging.getLogger(__name__)


class AutoLoader:
    def __init__(self, settings, session_factory):
        self.settings = settings
        self.session_factory = session_factory
        self._task = None
        self._stop = asyncio.Event()

    async def start(self):
        if not self.settings.carapis_api_key:
            logger.info("AutoLoader: CARAPIS_API_KEY не задан, автозагрузка отключена")
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("AutoLoader запущен (цель: %d машин)", self.settings.auto_load_target)

    async def stop(self):
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        try:
            await self._load_until_target()
        except Exception:
            logger.exception("AutoLoader: ошибка начальной загрузки")

        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.settings.auto_load_interval)
            except asyncio.TimeoutError:
                pass
            else:
                break
            try:
                await self._load_until_target()
            except Exception:
                logger.exception("AutoLoader: ошибка фоновой загрузки")

    async def _load_until_target(self):
        target = self.settings.auto_load_target
        batch = self.settings.auto_load_batch_size

        with self.session_factory() as db:
            current = db.scalar(select(func.count(Car.id))) or 0

        if current >= target:
            logger.info("AutoLoader: в базе %d машин (цель %d), загрузка не нужна", current, target)
            return

        logger.info("AutoLoader: в базе %d машин, докачиваю до %d", current, target)
        page = 1

        while current < target:
            remaining = target - current
            page_size = min(batch, remaining)

            try:
                records = await self._fetch_batch(page=page, page_size=page_size)
            except Exception as e:
                logger.error("AutoLoader: ошибка загрузки: %s", e)
                break

            if not records:
                logger.info("AutoLoader: источник вернул пусто, останавливаюсь")
                break

            with self.session_factory() as db:
                source = db.scalar(select(Source).where(Source.key == "licensed_json_api"))
                if not source:
                    source = Source(key="licensed_json_api", name="Carapis (автозагрузка)", kind="api", status="ok")
                    db.add(source)
                    db.flush()

                parsed = parse_items(records)
                now = utcnow()
                created, updated, unchanged, removed, total = _upsert_records(db, source, parsed.records, self.settings, now)

                source.status = SourceStatus.OK.value
                source.status_message = f"Автозагрузка: +{created} новых"
                source.last_attempt_at = now
                source.last_success_at = now
                source.last_imported_count = total

                db.commit()
                current = db.scalar(select(func.count(Car.id))) or 0
                logger.info("AutoLoader: создано %d, в базе теперь %d", created, current)

            page += 1
            await asyncio.sleep(1)

    async def _fetch_batch(self, page, page_size):
        # ИСПРАВЛЕННЫЙ АДРЕС И FOLLOW_REDIRECTS=True
        url = "https://api.carapis.com/apix/api/vehicles/"
        headers = {"Authorization": f"Bearer {self.settings.carapis_api_key}"}
        params = {"page": page, "page_size": page_size, "source": "encar"}

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        items = data.get("results") or data.get("data") or []
        records = []
        for car in items:
            # Извлекаем ВСЕ фотографии из массива photos
            photos = [p["url"] for p in car.get("photos", []) if p.get("url")]
            
            records.append({
                "external_id": str(car.get("id")),
                "brand": car.get("brand_name") or "Unknown",
                "model": car.get("model_name") or "Unknown",
                "trim": car.get("trim"),
                "year": car.get("year"),
                "price_krw": int(float(car.get("price_original", 0))) if car.get("price_original") else None,
                "mileage_km": car.get("mileage"),
                "fuel_type": car.get("fuel_type"),
                "transmission": car.get("transmission"),
                "region": car.get("region"),
                "listing_url": car.get("url"),
                "photos": photos,
                "status": "active",
            })
        return records