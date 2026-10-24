import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.importers.http_feed import HttpJsonFeedImporter
from app.importers.records import ListingRecord
from app.importers.runner import run_import
from app.models import Source

ADMIN = {"X-Admin-Key": "test-admin-key"}
IMPORT_LOCAL = "/admin/sources/local_file/import"


def item(external_id: str, **overrides) -> dict:
    data = {
        "external_id": external_id,
        "brand": "Hyundai",
        "model": "Sonata",
        "year": 2020,
        "price_krw": 18_500_000,
        "mileage_km": 45_000,
        "fuel_type": "gasoline",
        "transmission": "automatic",
        "photos": ["https://example.com/p1.jpg"],
    }
    data.update(overrides)
    return data


def write_feed(path: Path, items: list) -> None:
    path.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")


@pytest.fixture()
def http_settings(settings):
    return settings.model_copy(
        update={
            "licensed_feed_url": "https://feed.example.test/cars",
            "licensed_feed_api_key": "secret-test-key",
        }
    )


def run_http(client, settings, handler):
    importer = HttpJsonFeedImporter(settings, transport=httpx.MockTransport(handler))
    with client.app.state.session_factory() as db:
        return run_import(db, importer, settings)


def stored_status(client, key: str) -> str:
    with client.app.state.session_factory() as db:
        return db.scalar(select(Source).where(Source.key == key)).status


# ---------- проверка формата записей ----------


def test_record_normalizes_values_and_rejects_bad_urls():
    record = ListingRecord.model_validate(
        item("X1", fuel_type="전기", transmission="오토", brand="  Kia  ")
    )
    assert record.fuel_type == "electric"
    assert record.transmission == "automatic"
    assert record.brand == "Kia"

    with pytest.raises(ValidationError):
        ListingRecord.model_validate(item("X2", photos=["javascript:alert(1)"]))
    with pytest.raises(ValidationError):
        ListingRecord.model_validate(item("X3", year=1800))
    with pytest.raises(ValidationError):
        ListingRecord.model_validate(item("X4", price_krw=-5))


# ---------- административный запуск и защита ключом ----------


def test_admin_import_requires_correct_key(client):
    assert client.post(IMPORT_LOCAL).status_code == 401
    assert client.post(IMPORT_LOCAL, headers={"X-Admin-Key": "wrong"}).status_code == 401


def test_admin_import_disabled_without_admin_key(make_client):
    client = make_client(admin_api_key="")
    assert client.post(IMPORT_LOCAL, headers=ADMIN).status_code == 503


def test_unknown_source_returns_404(client):
    assert client.post("/admin/sources/nope/import", headers=ADMIN).status_code == 404


def test_import_from_unconfigured_source_does_nothing_and_says_so(client):
    response = client.post(IMPORT_LOCAL, headers=ADMIN)
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "not_configured"
    assert body["created"] == 0
    assert "LOCAL_FEED_PATH" in body["message"]
    assert client.get("/cars").json()["total"] == 0


# ---------- импорт из локального файла ----------


def test_local_file_import_create_update_and_price_history(make_client, tmp_path):
    feed = tmp_path / "feed.json"
    bad = {"external_id": "BAD", "brand": "X", "model": "Y", "year": 1800}
    write_feed(feed, [item("A1"), item("A2", brand="Kia", model="K5"), bad])
    client = make_client(local_feed_path=str(feed))

    first = client.post(IMPORT_LOCAL, headers=ADMIN).json()
    assert first["outcome"] == "success"
    assert first["fetched"] == 3
    assert first["created"] == 2
    assert first["invalid"] == 1
    assert len(first["errors_sample"]) == 1
    assert client.get("/cars").json()["total"] == 2

    sources = {s["key"]: s for s in client.get("/sources").json()["items"]}
    assert sources["local_file"]["status"] == "ok"
    assert sources["local_file"]["cars_count"] == 2
    assert sources["local_file"]["last_success_at"] is not None

    # Второй импорт: у A1 изменилась цена, A2 без изменений.
    write_feed(feed, [item("A1", price_krw=17_900_000), item("A2", brand="Kia", model="K5")])
    second = client.post(IMPORT_LOCAL, headers=ADMIN).json()
    assert second["created"] == 0
    assert second["updated"] == 1
    assert second["unchanged"] == 1

    car_id = client.get("/cars?brand=hyundai").json()["items"][0]["id"]
    detail = client.get(f"/cars/{car_id}").json()
    assert detail["price_krw"] == 17_900_000
    assert [p["price_krw"] for p in detail["price_history"]] == [18_500_000, 17_900_000]


def test_missing_listings_are_kept_by_default(make_client, tmp_path):
    feed = tmp_path / "feed.json"
    write_feed(feed, [item("A1"), item("A2", brand="Kia", model="K5")])
    client = make_client(local_feed_path=str(feed))
    client.post(IMPORT_LOCAL, headers=ADMIN)

    write_feed(feed, [item("A1")])
    body = client.post(IMPORT_LOCAL, headers=ADMIN).json()
    assert body["marked_removed"] == 0
    assert client.get("/cars").json()["total"] == 2


def test_missing_listings_marked_removed_when_enabled(make_client, tmp_path):
    feed = tmp_path / "feed.json"
    write_feed(feed, [item("A1"), item("A2", brand="Kia", model="K5")])
    client = make_client(local_feed_path=str(feed), mark_missing_as_removed=True)
    client.post(IMPORT_LOCAL, headers=ADMIN)

    write_feed(feed, [item("A1")])
    body = client.post(IMPORT_LOCAL, headers=ADMIN).json()
    assert body["marked_removed"] == 1
    assert client.get("/cars").json()["total"] == 1
    assert client.get("/cars?status=removed").json()["total"] == 1


def test_bad_feed_format_reports_error(make_client, tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text('{"foo": 1}', encoding="utf-8")
    client = make_client(local_feed_path=str(feed))

    body = client.post(IMPORT_LOCAL, headers=ADMIN).json()
    assert body["outcome"] == "error"
    assert stored_status(client, "local_file") == "error"
    assert client.get("/cars").json()["total"] == 0


def test_feed_where_every_record_is_invalid_saves_nothing(make_client, tmp_path):
    feed = tmp_path / "feed.json"
    write_feed(feed, [{"external_id": "B1", "brand": "X", "model": "Y", "year": 1800}])
    client = make_client(local_feed_path=str(feed))

    body = client.post(IMPORT_LOCAL, headers=ADMIN).json()
    assert body["outcome"] == "error"
    assert body["invalid"] == 1
    assert client.get("/cars").json()["total"] == 0


def test_sample_file_from_readme_imports(make_client):
    sample = Path(__file__).resolve().parent.parent / "data" / "sample_listings.json"
    client = make_client(local_feed_path=str(sample))

    body = client.post(IMPORT_LOCAL, headers=ADMIN).json()
    assert body["outcome"] == "success"
    assert body["created"] == 4
    assert body["invalid"] == 1
    assert client.get("/cars?fuel_type=electric").json()["total"] == 1


# ---------- импорт из API: повторы, недоступность, ошибки ----------


def test_http_importer_retries_transient_errors_then_succeeds(client, http_settings):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["authorization"] == "Bearer secret-test-key"
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"items": [item("H1")]})

    result = run_http(client, http_settings, handler)
    assert result.outcome == "success"
    assert result.created == 1
    assert len(calls) == 3


def test_http_importer_reports_unavailable_after_all_attempts(client, http_settings):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(503)

    result = run_http(client, http_settings, handler)
    assert result.outcome == "unavailable"
    assert len(calls) == http_settings.http_max_attempts
    assert stored_status(client, "licensed_json_api") == "unavailable"


def test_http_importer_retries_network_errors(client, http_settings):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectError("boom", request=request)

    result = run_http(client, http_settings, handler)
    assert result.outcome == "unavailable"
    assert len(calls) == http_settings.http_max_attempts


def test_http_importer_does_not_retry_access_denied(client, http_settings):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(401)

    result = run_http(client, http_settings, handler)
    assert result.outcome == "error"
    assert "HTTP 401" in result.message
    assert len(calls) == 1
    assert stored_status(client, "licensed_json_api") == "error"


def test_http_importer_rejects_non_json(client, http_settings):
    result = run_http(
        client, http_settings, lambda request: httpx.Response(200, content=b"not json")
    )
    assert result.outcome == "error"


def test_failed_import_keeps_previously_imported_cars(client, http_settings):
    ok = run_http(
        client, http_settings, lambda r: httpx.Response(200, json={"items": [item("H1")]})
    )
    assert ok.outcome == "success"

    failed = run_http(client, http_settings, lambda r: httpx.Response(503))
    assert failed.outcome == "unavailable"
    assert client.get("/cars").json()["total"] == 1


def test_http_importer_refuses_insecure_url(client, settings):
    insecure = settings.model_copy(
        update={"licensed_feed_url": "http://feed.example.test/cars"}
    )
    result = run_http(client, insecure, lambda r: httpx.Response(200, json=[]))
    assert result.outcome == "not_configured"
    assert "https" in result.message