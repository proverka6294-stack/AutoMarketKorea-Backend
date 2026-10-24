import pytest


def test_empty_catalog_is_empty_not_fake(client):
    body = client.get("/cars").json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["pages"] == 0


def test_list_defaults_to_active_and_newest_first(seeded_client):
    response = seeded_client.get("/cars")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["pages"] == 1
    assert all(item["status"] == "active" for item in body["items"])
    assert body["items"][0]["model"] == "Ioniq 5"
    assert body["items"][0]["currency"] == "KRW"


def test_pagination(seeded_client):
    body = seeded_client.get("/cars?page=2&page_size=3").json()
    assert body["total"] == 4
    assert body["pages"] == 2
    assert len(body["items"]) == 1

    beyond = seeded_client.get("/cars?page=3&page_size=3").json()
    assert beyond["items"] == []
    assert beyond["total"] == 4


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page_size=0",
        "page_size=101",
        "year_min=1900",
        "price_min=-1",
        "sort=banana",
        "fuel_type=steam",
        "status=maybe",
        "year_min=2022&year_max=2019",
        "price_min=100&price_max=50",
        "mileage_min=10&mileage_max=5",
    ],
)
def test_invalid_parameters_return_422(seeded_client, query):
    assert seeded_client.get(f"/cars?{query}").status_code == 422


def test_filter_by_brand_is_case_insensitive_and_respects_status(seeded_client):
    assert seeded_client.get("/cars?brand=kia").json()["total"] == 1
    assert seeded_client.get("/cars?brand=KIA&status=all").json()["total"] == 2
    assert seeded_client.get("/cars?status=sold").json()["total"] == 1


def test_filters_fuel_year_price_mileage_source(seeded_client):
    assert seeded_client.get("/cars?fuel_type=electric").json()["total"] == 1
    assert seeded_client.get("/cars?year_min=2021").json()["total"] == 2
    assert seeded_client.get("/cars?price_min=20000000&price_max=40000000").json()["total"] == 2
    assert seeded_client.get("/cars?mileage_max=50000").json()["total"] == 3
    assert seeded_client.get("/cars?source=test_source").json()["total"] == 4
    assert seeded_client.get("/cars?source=nope").json()["total"] == 0


def test_search_q(seeded_client):
    assert seeded_client.get("/cars?q=ioniq").json()["total"] == 1
    assert seeded_client.get("/cars?q=hyundai").json()["total"] == 2
    assert seeded_client.get("/cars?q=hyundai%202020").json()["total"] == 1


def test_search_treats_percent_as_plain_character(seeded_client):
    assert seeded_client.get("/cars?q=%25").json()["total"] == 0
    assert seeded_client.get("/cars?q=_").json()["total"] == 0


def test_sorting(seeded_client):
    def column(query, field):
        return [item[field] for item in seeded_client.get(f"/cars?{query}").json()["items"]]

    prices = column("sort=price_asc", "price_krw")
    assert prices == sorted(prices)
    assert column("sort=price_desc", "price_krw") == sorted(prices, reverse=True)

    mileage = column("sort=mileage_asc", "mileage_km")
    assert mileage == sorted(mileage)

    years = column("sort=year_desc", "year")
    assert years == sorted(years, reverse=True)


def test_car_detail(seeded_client):
    car_id = seeded_client.get("/cars?q=sonata").json()["items"][0]["id"]
    response = seeded_client.get(f"/cars/{car_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["brand"] == "Hyundai"
    assert body["source"]["key"] == "test_source"
    assert [photo["position"] for photo in body["photos"]] == [0, 1]
    assert len(body["price_history"]) == 1
    assert body["price_history"][0]["price_krw"] == 18_500_000
    assert body["last_checked_at"]


def test_car_detail_errors(seeded_client):
    assert seeded_client.get("/cars/999999").status_code == 404
    assert seeded_client.get("/cars/0").status_code == 422
    assert seeded_client.get("/cars/abc").status_code == 422