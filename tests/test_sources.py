import json


def test_unconfigured_sources_are_reported_honestly(client):
    response = client.get("/sources")
    assert response.status_code == 200
    items = {item["key"]: item for item in response.json()["items"]}
    assert set(items) == {"local_file", "licensed_json_api"}
    for item in items.values():
        assert item["configured"] is False
        assert item["status"] == "not_configured"
        assert item["status_message"]
        assert item["cars_count"] == 0
        assert item["last_success_at"] is None
        assert item["last_imported_count"] is None


def test_configured_source_is_not_reported_as_synced_before_import(make_client, tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps({"items": []}), encoding="utf-8")
    client = make_client(local_feed_path=str(feed))

    items = {item["key"]: item for item in client.get("/sources").json()["items"]}
    local = items["local_file"]
    assert local["configured"] is True
    assert local["status"] == "configured"
    assert local["last_success_at"] is None
    assert items["licensed_json_api"]["status"] == "not_configured"