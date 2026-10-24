from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import make_engine
from app.factory import create_app
from app.models import Car, CarPhoto, PriceHistory, Source


@pytest.fixture()
def settings() -> Settings:
    """Настройки для тестов: ни один источник не подключён, .env не читается."""
    return Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite://",
        admin_api_key="test-admin-key",
        cors_origins="",
        local_feed_path="",
        licensed_feed_url="",
        licensed_feed_api_key="",
        http_timeout_seconds=5,
        http_max_attempts=3,
        http_backoff_seconds=0.0,
        mark_missing_as_removed=False,
    )


@pytest.fixture()
def make_client(settings):
    """Фабрика клиентов: каждый получает свежую базу в памяти."""
    clients: list[TestClient] = []

    def _make(**overrides) -> TestClient:
        app_settings = settings.model_copy(update=overrides)
        engine = make_engine("sqlite://")
        app = create_app(settings=app_settings, engine=engine, configure_logging=False)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture()
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture()
def seeded_client(client) -> TestClient:
    """Клиент с пятью ТЕСТОВЫМИ автомобилями (только для проверки API, не часть продукта)."""
    now = datetime.now(timezone.utc)
    rows = [
        # external_id, brand, model, year, price, mileage, fuel, status, photos, days_ago
        ("A1", "Hyundai", "Sonata", 2020, 18_500_000, 45_000, "gasoline", "active", 2, 5),
        ("A2", "Kia", "K5", 2021, 22_000_000, 30_000, "lpg", "active", 0, 4),
        ("A3", "Genesis", "G80", 2019, 35_000_000, 80_000, "diesel", "active", 0, 3),
        ("A4", "Hyundai", "Ioniq 5", 2022, 41_000_000, 12_000, "electric", "active", 1, 2),
        ("A5", "Kia", "Carnival", 2018, 15_000_000, 120_000, "diesel", "sold", 0, 1),
    ]
    with client.app.state.session_factory() as db:
        source = Source(
            key="test_source",
            name="Test source",
            kind="test",
            description="",
            license_note="",
            status="ok",
        )
        db.add(source)
        db.flush()
        for ext_id, brand, model, year, price, mileage, fuel, status, photos, days_ago in rows:
            car = Car(
                source_id=source.id,
                external_id=ext_id,
                title=f"{brand} {model} {year}",
                brand=brand,
                model=model,
                year=year,
                price_krw=price,
                mileage_km=mileage,
                fuel_type=fuel,
                transmission="automatic",
                status=status,
                first_seen_at=now - timedelta(days=days_ago),
                last_seen_at=now,
                last_checked_at=now,
            )
            car.photos = [
                CarPhoto(url=f"https://example.com/{ext_id}/{i}.jpg", position=i)
                for i in range(photos)
            ]
            car.price_history.append(PriceHistory(price_krw=price, recorded_at=now))
            db.add(car)
        db.commit()
    return client