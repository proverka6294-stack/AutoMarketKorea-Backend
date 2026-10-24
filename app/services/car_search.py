"""Поиск, фильтрация и сортировка каталога."""
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, contains_eager, selectinload

from app.enums import FuelType, SortOption, StatusFilter, Transmission
from app.models import Car, Source


@dataclass(frozen=True)
class CarFilters:
    page: int = 1
    page_size: int = 20
    q: str | None = None
    brand: str | None = None
    model: str | None = None
    fuel_type: FuelType | None = None
    transmission: Transmission | None = None
    status: StatusFilter = StatusFilter.ACTIVE
    source: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    mileage_min: int | None = None
    mileage_max: int | None = None
    sort: SortOption = SortOption.NEWEST


# В каждой сортировке последним стоит Car.id: порядок всегда однозначный,
# поэтому страницы не «плавают» между запросами.
SORT_ORDER = {
    SortOption.NEWEST: (Car.first_seen_at.desc(), Car.id.desc()),
    SortOption.PRICE_ASC: (Car.price_krw.asc().nulls_last(), Car.id.asc()),
    SortOption.PRICE_DESC: (Car.price_krw.desc().nulls_last(), Car.id.asc()),
    SortOption.YEAR_ASC: (Car.year.asc(), Car.id.asc()),
    SortOption.YEAR_DESC: (Car.year.desc(), Car.id.asc()),
    SortOption.MILEAGE_ASC: (Car.mileage_km.asc().nulls_last(), Car.id.asc()),
    SortOption.MILEAGE_DESC: (Car.mileage_km.desc().nulls_last(), Car.id.asc()),
    SortOption.CHECKED_DESC: (Car.last_checked_at.desc(), Car.id.desc()),
}


def _like_pattern(word: str) -> str:
    """Экранирует спецсимволы LIKE, чтобы '%' и '_' искались как обычные символы."""
    escaped = word.lower().replace("/", "//").replace("%", "/%").replace("_", "/_")
    return f"%{escaped}%"


def build_conditions(f: CarFilters) -> list:
    conditions: list = []

    if f.q:
        # Каждое слово запроса должно встретиться в названии, марке, модели или комплектации.
        for word in f.q.split()[:5]:
            pattern = _like_pattern(word)
            conditions.append(
                or_(
                    func.lower(Car.title).like(pattern, escape="/"),
                    func.lower(Car.brand).like(pattern, escape="/"),
                    func.lower(Car.model).like(pattern, escape="/"),
                    func.lower(Car.trim).like(pattern, escape="/"),
                )
            )
    if f.brand:
        conditions.append(func.lower(Car.brand) == f.brand.lower())
    if f.model:
        conditions.append(func.lower(Car.model) == f.model.lower())
    if f.fuel_type:
        conditions.append(Car.fuel_type == f.fuel_type.value)
    if f.transmission:
        conditions.append(Car.transmission == f.transmission.value)
    if f.status != StatusFilter.ALL:
        conditions.append(Car.status == f.status.value)
    if f.source:
        conditions.append(Source.key == f.source)
    if f.year_min is not None:
        conditions.append(Car.year >= f.year_min)
    if f.year_max is not None:
        conditions.append(Car.year <= f.year_max)
    if f.price_min is not None:
        conditions.append(Car.price_krw >= f.price_min)
    if f.price_max is not None:
        conditions.append(Car.price_krw <= f.price_max)
    if f.mileage_min is not None:
        conditions.append(Car.mileage_km >= f.mileage_min)
    if f.mileage_max is not None:
        conditions.append(Car.mileage_km <= f.mileage_max)
    return conditions


def search_cars(db: Session, f: CarFilters) -> tuple[list[Car], int]:
    conditions = build_conditions(f)

    total = (
        db.scalar(
            select(func.count(Car.id))
            .select_from(Car)
            .join(Car.source)
            .where(*conditions)
        )
        or 0
    )

    statement = (
        select(Car)
        .join(Car.source)
        .options(contains_eager(Car.source), selectinload(Car.photos))
        .where(*conditions)
        .order_by(*SORT_ORDER[f.sort])
        .offset((f.page - 1) * f.page_size)
        .limit(f.page_size)
    )
    cars = list(db.scalars(statement).all())
    return cars, total