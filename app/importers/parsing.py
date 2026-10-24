"""Разбор ответа источника: извлечение списка и проверка каждой записи."""
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.importers.errors import SourceFormatError
from app.importers.records import ListingRecord

MAX_ERROR_SAMPLES = 20


@dataclass
class ParseResult:
    records: list[ListingRecord] = field(default_factory=list)
    invalid_count: int = 0
    errors: list[str] = field(default_factory=list)


def extract_items(payload: Any) -> list[Any]:
    """Принимает JSON-список или объект {"items": [...]}."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload["items"]
    raise SourceFormatError('Ожидался JSON-список или объект вида {"items": [...]}.')


def _add_error(result: ParseResult, message: str) -> None:
    result.invalid_count += 1
    if len(result.errors) < MAX_ERROR_SAMPLES:
        result.errors.append(message)


def parse_items(raw_items: list[Any]) -> ParseResult:
    """Проверяет записи по одной: плохая запись не ломает весь импорт."""
    result = ParseResult()
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            _add_error(result, f"запись №{index}: ожидался объект JSON")
            continue
        try:
            result.records.append(ListingRecord.model_validate(raw))
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()[:3]
            )
            _add_error(result, f"запись №{index}: {problems}")
    return result