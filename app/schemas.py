"""Схемы ответов API (то, что видит клиент)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    position: int


class PricePointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    price_krw: int
    recorded_at: datetime


class CarListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    brand: str
    model: str
    trim: str | None = None
    year: int
    price_krw: int | None = None
    currency: str = "KRW"
    mileage_km: int | None = None
    fuel_type: str
    transmission: str
    status: str
    main_photo_url: str | None = None
    source_key: str
    last_checked_at: datetime


class CarDetail(CarListItem):
    color: str | None = None
    region: str | None = None
    description: str | None = None
    listing_url: str | None = None
    photos: list[PhotoOut] = Field(default_factory=list)
    price_history: list[PricePointOut] = Field(default_factory=list)
    source: SourceBrief
    first_seen_at: datetime
    last_seen_at: datetime


class CarPage(BaseModel):
    items: list[CarListItem]
    total: int
    page: int
    page_size: int
    pages: int


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    time: datetime
    database: str
    database_dialect: str


class SourceOut(BaseModel):
    key: str
    name: str
    kind: str
    description: str
    license_note: str
    configured: bool
    status: str
    status_message: str | None = None
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_imported_count: int | None = None
    cars_count: int


class SourceListResponse(BaseModel):
    items: list[SourceOut]


class ImportResult(BaseModel):
    source_key: str
    outcome: str  # success | not_configured | unavailable | error
    message: str = ""
    fetched: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    invalid: int = 0
    marked_removed: int = 0
    errors_sample: list[str] = Field(default_factory=list)