from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_ok_status(self):
        response = client.get("/health")
        assert response.json() == {"status": "ok"}

    def test_content_type_is_json(self):
        response = client.get("/health")
        assert response.headers["content-type"].startswith("application/json")

    def test_payload_is_object_with_single_key(self):
        payload = client.get("/health").json()
        assert isinstance(payload, dict)
        assert list(payload.keys()) == ["status"]

    def test_status_value_is_string(self):
        assert client.get("/health").json()["status"] == "ok"

    def test_get_method_only(self):
        assert client.post("/health").status_code == 405