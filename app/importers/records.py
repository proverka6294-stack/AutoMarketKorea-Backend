"""Единый формат объявления, который принимает импорт.

Любой источник (файл, API) должен отдавать записи в этом формате:
{"items": [ {...}, {...} ]}
"""
from typing import Annotated, Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.enums import FuelType, ListingStatus, Transmission

ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]

_FUEL_SYNONYMS = {
    "petrol": "gasoline",
    "gas": "gasoline",
    "가솔린": "gasoline",
    "휘발유": "gasoline",
    "경유": "diesel",
    "디젤": "diesel",
    "전기": "electric",
    "ev": "electric",
    "하이브리드": "hybrid",
    "phev": "plug_in_hybrid",
    "수소": "hydrogen",
}

_TRANSMISSION_SYNONYMS = {
    "auto": "automatic",
    "at": "automatic",
    "오토": "automatic",
    "자동": "automatic",
    "mt": "manual",
    "수동": "manual",
}


def _normalize_enum(value: Any, enum_cls, fallback, synonyms: dict[str, str] | None = None):
    if value is None:
        return fallback
    if isinstance(value, enum_cls):
        return value
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if synonyms:
        text = synonyms.get(text, text)
    try:
        return enum_cls(text)
    except ValueError:
        return fallback


def _is_http_url(value: str) -> bool:
    parts = urlparse(value)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


class ListingRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True, validate_default=True, extra="ignore")

    external_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    brand: ShortText
    model: ShortText
    trim: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, max_length=200)
    year: int = Field(ge=1980, le=2100)
    price_krw: int | None = Field(default=None, ge=0, le=10_000_000_000)
    mileage_km: int | None = Field(default=None, ge=0, le=2_000_000)
    fuel_type: FuelType = FuelType.UNKNOWN
    transmission: Transmission = Transmission.UNKNOWN
    color: str | None = Field(default=None, max_length=40)
    region: str | None = Field(default=None, max_length=80)
    listing_url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    status: ListingStatus = ListingStatus.ACTIVE
    photos: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("external_id", mode="before")
    @classmethod
    def _external_id_to_str(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("external_id должен быть строкой или числом")
        if isinstance(value, int):
            return str(value)
        return value

    @field_validator(
        "trim", "title", "color", "region", "listing_url", "description", mode="before"
    )
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("fuel_type", mode="before")
    @classmethod
    def _fuel(cls, value: Any) -> Any:
        return _normalize_enum(value, FuelType, FuelType.UNKNOWN, _FUEL_SYNONYMS)

    @field_validator("transmission", mode="before")
    @classmethod
    def _transmission(cls, value: Any) -> Any:
        return _normalize_enum(
            value, Transmission, Transmission.UNKNOWN, _TRANSMISSION_SYNONYMS
        )

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, value: Any) -> Any:
        return _normalize_enum(value, ListingStatus, ListingStatus.UNKNOWN)

    @field_validator("listing_url")
    @classmethod
    def _check_listing_url(cls, value: str | None) -> str | None:
        if value is not None and not _is_http_url(value):
            raise ValueError("listing_url должен быть ссылкой http(s)")
        return value

    @field_validator("photos")
    @classmethod
    def _check_photos(cls, urls: list[str]) -> list[str]:
        cleaned: list[str] = []
        for url in urls:
            url = url.strip()
            if len(url) > 500 or not _is_http_url(url):
                raise ValueError("фото должно быть ссылкой http(s) длиной до 500 символов")
            cleaned.append(url)
        return cleaned