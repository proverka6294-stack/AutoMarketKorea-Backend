from sqlalchemy.exc import OperationalError

from app.api.deps import get_db


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["database_dialect"] == "sqlite"
    assert body["version"]


def test_health_reports_database_failure(client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("db down"))

        def close(self):
            pass

    def broken_db():
        yield BrokenSession()

    client.app.dependency_overrides[get_db] = broken_db
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"


def test_root_points_to_docs(client):
    body = client.get("/").json()
    assert body["docs"] == "/docs"