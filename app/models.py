"""Модели базы данных: источники, автомобили, фото, история цен."""
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.database import Base
from app.enums import FuelType, ListingStatus, SourceStatus, Transmission


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Всегда хранит и возвращает время в UTC с указанием часового пояса.

    SQLite теряет часовой пояс, поэтому добавляем его при чтении.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Source(Base):
    """Источник объявлений и состояние последнего импорта."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text, default="")
    license_note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(20), default=SourceStatus.NOT_CONFIGURED.value
    )
    status_message: Mapped[str | None] = mapped_column(Text, default=None)
    last_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    last_imported_count: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow
    )

    cars: Mapped[list["Car"]] = relationship(back_populates="source")


class Car(Base):
    """Объявление об автомобиле."""

    __tablename__ = "cars"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_cars_source_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(100))

    title: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(80), index=True)
    trim: Mapped[str | None] = mapped_column(String(80), default=None)
    year: Mapped[int] = mapped_column(Integer, index=True)

    price_krw: Mapped[int | None] = mapped_column(BigInteger, default=None, index=True)
    mileage_km: Mapped[int | None] = mapped_column(Integer, default=None)

    fuel_type: Mapped[str] = mapped_column(
        String(20), default=FuelType.UNKNOWN.value, index=True
    )
    transmission: Mapped[str] = mapped_column(
        String(20), default=Transmission.UNKNOWN.value
    )
    color: Mapped[str | None] = mapped_column(String(40), default=None)
    region: Mapped[str | None] = mapped_column(String(80), default=None)
    listing_url: Mapped[str | None] = mapped_column(String(500), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)

    status: Mapped[str] = mapped_column(
        String(20), default=ListingStatus.ACTIVE.value, index=True
    )

    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_checked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow
    )

    source: Mapped["Source"] = relationship(back_populates="cars")
    photos: Mapped[list["CarPhoto"]] = relationship(
        back_populates="car",
        cascade="all, delete-orphan",
        order_by="CarPhoto.position",
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="car",
        cascade="all, delete-orphan",
        order_by="PriceHistory.recorded_at",
    )

    @property
    def main_photo_url(self) -> str | None:
        return self.photos[0].url if self.photos else None

    @property
    def source_key(self) -> str:
        return self.source.key


class CarPhoto(Base):
    __tablename__ = "car_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_id: Mapped[int] = mapped_column(
        ForeignKey("cars.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(Integer, default=0)

    car: Mapped["Car"] = relationship(back_populates="photos")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_id: Mapped[int] = mapped_column(
        ForeignKey("cars.id", ondelete="CASCADE"), index=True
    )
    price_krw: Mapped[int] = mapped_column(BigInteger)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    car: Mapped["Car"] = relationship(back_populates="price_history")