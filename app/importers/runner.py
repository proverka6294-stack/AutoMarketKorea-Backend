"""Запуск импорта: проверка настроек, загрузка, проверка записей, запись в базу."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.enums import ListingStatus, SourceStatus
from app.importers.base import BaseImporter
from app.importers.errors import (
    SourceFormatError,
    SourceRejectedError,
    SourceUnavailableError,
)
from app.importers.parsing import parse_items
from app.importers.records import ListingRecord
from app.models import Car, CarPhoto, PriceHistory, Source, utcnow
from app.schemas import ImportResult

logger = logging.getLogger(__name__)


def sync_sources(db: Session, importers: dict[str, BaseImporter]) -> None:
    """Создаёт и обновляет строки таблицы sources по списку импортёров.

    Статус «подключён» ставится только если настройки действительно заданы.
    """
    for importer in importers.values():
        source = db.scalar(select(Source).where(Source.key == importer.key))
        if source is None:
            source = Source(key=importer.key, status=SourceStatus.NOT_CONFIGURED.value)
            db.add(source)
        source.name = importer.name
        source.kind = importer.kind
        source.description = importer.description
        source.license_note = importer.license_note

        problem = importer.config_problem()
        if problem:
            source.status = SourceStatus.NOT_CONFIGURED.value
            source.status_message = problem
        elif source.status == SourceStatus.NOT_CONFIGURED.value:
            source.status = SourceStatus.CONFIGURED.value
            source.status_message = "Источник настроен, импорт ещё не запускался."
    db.commit()


def _fail(
    db: Session,
    source: Source,
    result: ImportResult,
    status: SourceStatus,
    outcome: str,
    message: str,
) -> ImportResult:
    source.status = status.value
    source.status_message = message
    db.commit()
    result.outcome = outcome
    result.message = message
    logger.error("Импорт %s не выполнен: %s", source.key, message)
    return result


def _apply(car: Car, record: ListingRecord) -> bool:
    """Переносит поля записи в автомобиль. True, если что-то изменилось."""
    values = {
        "title": record.title or f"{record.brand} {record.model} {record.year}",
        "brand": record.brand,
        "model": record.model,
        "trim": record.trim,
        "year": record.year,
        "price_krw": record.price_krw,
        "mileage_km": record.mileage_km,
        "fuel_type": record.fuel_type,
        "transmission": record.transmission,
        "color": record.color,
        "region": record.region,
        "listing_url": record.listing_url,
        "description": record.description,
        "status": record.status,
    }
    changed = False
    for name, value in values.items():
        if getattr(car, name) != value:
            setattr(car, name, value)
            changed = True
    return changed


def _upsert_records(
    db: Session,
    source: Source,
    records: list[ListingRecord],
    settings: Settings,
    now,
) -> tuple[int, int, int, int, int]:
    """Возвращает (создано, обновлено, без изменений, помечено удалёнными, всего уникальных)."""
    unique: dict[str, ListingRecord] = {}
    for record in records:
        if record.external_id in unique:
            logger.warning("Дубликат external_id=%s в источнике %s", record.external_id, source.key)
        unique[record.external_id] = record

    existing = {
        car.external_id: car
        for car in db.scalars(
            select(Car)
            .where(Car.source_id == source.id)
            .options(selectinload(Car.photos))
        )
    }

    created = updated = unchanged = 0
    for external_id, record in unique.items():
        photo_urls = list(record.photos)
        car = existing.get(external_id)

        if car is None:
            car = Car(
                source_id=source.id,
                external_id=external_id,
                first_seen_at=now,
                last_seen_at=now,
                last_checked_at=now,
            )
            _apply(car, record)
            car.photos = [CarPhoto(url=url, position=i) for i, url in enumerate(photo_urls)]
            if record.price_krw is not None:
                car.price_history.append(
                    PriceHistory(price_krw=record.price_krw, recorded_at=now)
                )
            db.add(car)
            created += 1
            continue

        old_price = car.price_krw
        changed = _apply(car, record)
        if [photo.url for photo in car.photos] != photo_urls:
            car.photos = [CarPhoto(url=url, position=i) for i, url in enumerate(photo_urls)]
            changed = True
        if record.price_krw is not None and record.price_krw != old_price:
            car.price_history.append(
                PriceHistory(price_krw=record.price_krw, recorded_at=now)
            )
        car.last_seen_at = now
        car.last_checked_at = now
        if changed:
            updated += 1
        else:
            unchanged += 1

    removed = 0
    if settings.mark_missing_as_removed and unique:
        for external_id, car in existing.items():
            if external_id not in unique and car.status == ListingStatus.ACTIVE.value:
                car.status = ListingStatus.REMOVED.value
                car.last_checked_at = now
                removed += 1

    return created, updated, unchanged, removed, len(unique)


def run_import(db: Session, importer: BaseImporter, settings: Settings) -> ImportResult:
    sync_sources(db, {importer.key: importer})
    source = db.scalar(select(Source).where(Source.key == importer.key))
    result = ImportResult(source_key=importer.key, outcome="error")

    problem = importer.config_problem()
    if problem:
        logger.warning("Импорт %s пропущен: %s", importer.key, problem)
        result.outcome = "not_configured"
        result.message = problem
        return result

    started = utcnow()
    source.last_attempt_at = started
    db.commit()
    logger.info("Импорт %s: начало", importer.key)

    try:
        raw_items = importer.fetch_items()
    except SourceUnavailableError as exc:
        return _fail(db, source, result, SourceStatus.UNAVAILABLE, "unavailable", str(exc))
    except (SourceRejectedError, SourceFormatError) as exc:
        return _fail(db, source, result, SourceStatus.ERROR, "error", str(exc))
    except Exception:
        logger.exception("Импорт %s: неожиданная ошибка при получении данных", importer.key)
        return _fail(
            db,
            source,
            result,
            SourceStatus.ERROR,
            "error",
            "Неожиданная ошибка при получении данных. Подробности в журнале.",
        )

    parsed = parse_items(raw_items)
    result.fetched = len(raw_items)
    result.invalid = parsed.invalid_count
    result.errors_sample = parsed.errors[:10]

    if raw_items and not parsed.records:
        return _fail(
            db,
            source,
            result,
            SourceStatus.ERROR,
            "error",
            "Ни одна запись не прошла проверку формата. Каталог не изменён.",
        )

    try:
        created, updated, unchanged, removed, total = _upsert_records(
            db, source, parsed.records, settings, started
        )
        message = (
            f"Импорт завершён: создано {created}, обновлено {updated}, "
            f"без изменений {unchanged}, некорректных записей {parsed.invalid_count}."
        )
        if not raw_items:
            message = "Источник вернул пустой список, каталог не изменён."
        source.status = SourceStatus.OK.value
        source.status_message = message
        source.last_success_at = utcnow()
        source.last_imported_count = total
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Импорт %s: ошибка записи в базу", importer.key)
        return _fail(
            db,
            source,
            result,
            SourceStatus.ERROR,
            "error",
            "Ошибка записи в базу данных. Подробности в журнале.",
        )

    result.outcome = "success"
    result.message = message
    result.created = created
    result.updated = updated
    result.unchanged = unchanged
    result.marked_removed = removed
    logger.info("Импорт %s: %s", importer.key, message)
    return result