"""Перечисления, общие для базы данных, импорта и API."""
from enum import StrEnum


class ListingStatus(StrEnum):
    ACTIVE = "active"
    SOLD = "sold"
    REMOVED = "removed"
    UNKNOWN = "unknown"


class StatusFilter(StrEnum):
    """Допустимые значения параметра ?status= в GET /cars."""

    ACTIVE = "active"
    SOLD = "sold"
    REMOVED = "removed"
    UNKNOWN = "unknown"
    ALL = "all"


class FuelType(StrEnum):
    GASOLINE = "gasoline"
    DIESEL = "diesel"
    LPG = "lpg"
    HYBRID = "hybrid"
    PLUG_IN_HYBRID = "plug_in_hybrid"
    ELECTRIC = "electric"
    HYDROGEN = "hydrogen"
    OTHER = "other"
    UNKNOWN = "unknown"


class Transmission(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    CVT = "cvt"
    OTHER = "other"
    UNKNOWN = "unknown"


class SortOption(StrEnum):
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    YEAR_ASC = "year_asc"
    YEAR_DESC = "year_desc"
    MILEAGE_ASC = "mileage_asc"
    MILEAGE_DESC = "mileage_desc"
    CHECKED_DESC = "checked_desc"


class SourceStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"  # источник не подключён
    CONFIGURED = "configured"  # настроен, импорт ещё не запускался
    OK = "ok"  # последний импорт успешен
    UNAVAILABLE = "unavailable"  # источник временно недоступен
    ERROR = "error"  # отказ в доступе, неверный формат, внутренняя ошибка