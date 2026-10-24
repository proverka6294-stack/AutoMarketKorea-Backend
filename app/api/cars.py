"""GET /cars и GET /cars/{id} — каталог автомобилей."""
import math

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import get_db
from app.enums import FuelType, SortOption, StatusFilter, Transmission
from app.models import Car
from app.schemas import CarDetail, CarListItem, CarPage
from app.services.car_search import CarFilters, search_cars

router = APIRouter(prefix="/cars", tags=["cars"])


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _check_range(name_min: str, value_min, name_max: str, value_max) -> None:
    if value_min is not None and value_max is not None and value_min > value_max:
        raise HTTPException(
            status_code=422, detail=f"{name_min} не может быть больше {name_max}."
        )


def get_filters(
    page: int = Query(default=1, ge=1, le=100000, description="Номер страницы, с 1"),
    page_size: int = Query(default=20, ge=1, le=100, description="Размер страницы, 1-100"),
    q: str | None = Query(default=None, max_length=100, description="Поиск по названию, марке, модели"),
    brand: str | None = Query(default=None, max_length=80),
    model: str | None = Query(default=None, max_length=80),
    fuel_type: FuelType | None = Query(default=None),
    transmission: Transmission | None = Query(default=None),
    status: StatusFilter = Query(default=StatusFilter.ACTIVE),
    source: str | None = Query(default=None, max_length=50, description="Ключ источника"),
    year_min: int | None = Query(default=None, ge=1980, le=2100),
    year_max: int | None = Query(default=None, ge=1980, le=2100),
    price_min: int | None = Query(default=None, ge=0, description="Цена от, вон"),
    price_max: int | None = Query(default=None, ge=0, description="Цена до, вон"),
    mileage_min: int | None = Query(default=None, ge=0, description="Пробег от, км"),
    mileage_max: int | None = Query(default=None, ge=0, description="Пробег до, км"),
    sort: SortOption = Query(default=SortOption.NEWEST),
) -> CarFilters:
    _check_range("year_min", year_min, "year_max", year_max)
    _check_range("price_min", price_min, "price_max", price_max)
    _check_range("mileage_min", mileage_min, "mileage_max", mileage_max)
    return CarFilters(
        page=page,
        page_size=page_size,
        q=_clean(q),
        brand=_clean(brand),
        model=_clean(model),
        fuel_type=fuel_type,
        transmission=transmission,
        status=status,
        source=_clean(source),
        year_min=year_min,
        year_max=year_max,
        price_min=price_min,
        price_max=price_max,
        mileage_min=mileage_min,
        mileage_max=mileage_max,
        sort=sort,
    )


@router.get("", response_model=CarPage)
def list_cars(
    filters: CarFilters = Depends(get_filters), db: Session = Depends(get_db)
) -> CarPage:
    cars, total = search_cars(db, filters)
    pages = math.ceil(total / filters.page_size) if total else 0
    return CarPage(
        items=[CarListItem.model_validate(car) for car in cars],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        pages=pages,
    )


@router.get("/{car_id}", response_model=CarDetail)
def get_car(car_id: int = Path(ge=1), db: Session = Depends(get_db)) -> CarDetail:
    car = db.scalar(
        select(Car)
        .where(Car.id == car_id)
        .options(
            joinedload(Car.source),
            selectinload(Car.photos),
            selectinload(Car.price_history),
        )
    )
    if car is None:
        raise HTTPException(status_code=404, detail="Автомобиль не найден.")
    return CarDetail.model_validate(car)