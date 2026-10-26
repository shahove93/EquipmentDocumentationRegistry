from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app.main as main_module
from app.config import Settings
from app.database.connection import get_db
from app.main import app
from app.models import Batch, Manufacturer, Product, ProductVariant
from app.services.batch_service import BatchService

_MISSING = object()


@contextmanager
def batch_client(db, tmp_path, *, raise_server_exceptions=True):
    """Isolate database, lifespan log and storage; restore just our overrides."""
    previous = app.dependency_overrides.get(get_db, _MISSING)
    settings = Settings(_env_file=None, DATABASE_URL="postgresql+psycopg://unused/unused", STORAGE_ROOT=str(tmp_path / "storage"), LOG_FILE=str(tmp_path / "app.log"))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(main_module, "get_settings", lambda: settings)
        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app, raise_server_exceptions=raise_server_exceptions) as client:
                yield client
        finally:
            if previous is _MISSING:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous


@pytest.fixture
def client(db, tmp_path):
    with batch_client(db, tmp_path) as value:
        yield value


@pytest.fixture
def variants(db):
    maker = Manufacturer(name="API batch maker")
    rows = [ProductVariant(product=Product(name=f"Product SDR{i}", standard="GOST", manufacturer=maker), size_text="63") for i in (11, 17)]
    db.add_all(rows)
    db.commit()
    return rows


@pytest.fixture
def make_batch(client, variants):
    def make(**kwargs):
        response = client.post("/batches", json={"variant_id": variants[0].id, **kwargs})
        assert response.status_code == 201
        return response.json()
    return make


class TestBatchEndpoints:
    def test_post_location_get_and_database(self, client, db, variants):
        response = client.post("/batches", json={"variant_id": variants[0].id, "batch_number": " B  Ab ", "quantity": "5", "quantity_unit": " шт ", "manufacture_date": "2099-02-28"})
        assert response.status_code == 201
        body = response.json()
        assert body == {"id": body["id"], "variant_id": variants[0].id, "batch_number": "B  Ab", "quantity": "5.00", "quantity_unit": "шт", "manufacture_date": "2099-02-28"}
        assert response.headers["location"] == f"http://testserver/batches/{body['id']}"
        assert client.get(response.headers["location"]).json() == body
        db.expire_all()
        stored = db.get(Batch, body["id"])
        assert str(stored.quantity) == "5.00" and stored.manufacture_date.isoformat() == "2099-02-28"

    def test_minimal_and_duplicates(self, client, make_batch, variants, db):
        first, second = make_batch(), make_batch()
        assert first == {"id": first["id"], "variant_id": variants[0].id, "batch_number": None, "quantity": None, "quantity_unit": None, "manufacture_date": None}
        assert first["id"] != second["id"]
        numbered = [make_batch(batch_number="B", quantity="2") for _ in range(2)]
        other = make_batch(variant_id=variants[1].id, batch_number="B", quantity="2")
        assert len({row["id"] for row in [first, second, *numbered, other]}) == 5
        assert db.scalar(select(func.count()).select_from(Batch)) == 5

    def test_patch_move_clear_omit_and_empty(self, client, db, variants, make_batch, monkeypatch):
        first = make_batch(batch_number="old", quantity="5", quantity_unit="m", manufacture_date="2024-02-29")
        other = make_batch(batch_number="other")
        path = f"/batches/{first['id']}"
        response = client.patch(path, json={"variant_id": variants[1].id, "quantity": None})
        assert response.status_code == 200 and "location" not in response.headers
        expected = {**first, "variant_id": variants[1].id, "quantity": None}
        assert response.json() == expected
        response = client.patch(path, json={"batch_number": None, "manufacture_date": None, "quantity_unit": None})
        expected.update(batch_number=None, manufacture_date=None, quantity_unit=None)
        assert response.json() == expected
        commit = Mock(wraps=db.commit)
        monkeypatch.setattr(db, "commit", commit)
        assert client.patch(path, json={}).json() == expected
        assert commit.call_count == 0
        db.expire_all()
        assert db.get(Batch, first["id"]).variant_id == variants[1].id
        assert client.get(f"/batches/{other['id']}").json() == other
        assert client.patch(path, json={"batch_number": "other"}).status_code == 200

    def test_list_global_defaults_boundaries_offset_and_unknown_query(self, client, db, variants):
        assert client.get("/batches").json() == []
        rows = [Batch(variant_id=variants[i % 2].id, batch_number=f"{100-i:03}") for i in range(55)]
        db.add_all(rows)
        db.commit()
        ids = [row.id for row in rows]
        assert [row["id"] for row in client.get("/batches").json()] == ids[:50]
        assert [row["id"] for row in client.get("/batches?limit=1&offset=0").json()] == ids[:1]
        assert [row["id"] for row in client.get("/batches?limit=100&offset=1&unknown=x").json()] == ids[1:]
        assert client.get("/batches?offset=55").json() == []

    @pytest.mark.parametrize("method", ["delete", "put"])
    def test_unsupported_method_keeps_row(self, client, make_batch, db, method):
        body = make_batch()
        path = f"/batches/{body['id']}"
        assert getattr(client, method)(path).status_code == 405
        db.expire_all()
        assert db.get(Batch, body["id"]) is not None
        assert client.get(path).json() == body


class TestBatchValidation:
    @pytest.mark.parametrize("method", ["post", "patch"])
    @pytest.mark.parametrize("payload", [
        {"variant_id": None}, {"variant_id": True}, {"variant_id": 0}, {"variant_id": -1}, {"variant_id": 1.5},
        {"batch_number": "  "}, {"batch_number": "x" * 101}, {"quantity_unit": ""}, {"quantity_unit": "x" * 31},
        {"quantity": "0"}, {"quantity": "-0"}, {"quantity": True}, {"quantity": "NaN"}, {"quantity": "Infinity"},
        {"quantity": "1.005"}, {"quantity": "1.000"}, {"quantity": "100000000"},
        {"manufacture_date": "2023-02-29"}, {"manufacture_date": True}, {"manufacture_date": "2024-01-01T01:00:00"},
        *[{field: 1} for field in ["id", "product_id", "sdr", "document_ids", "variant", "documents", "unknown"]],
    ])
    def test_invalid_body_no_write_or_service_call(self, client, make_batch, db, variants, monkeypatch, method, payload):
        body = make_batch(batch_number="unchanged")
        before = db.scalar(select(func.count()).select_from(Batch))
        service = Mock(side_effect=AssertionError("validation must precede service"))
        monkeypatch.setattr(BatchService, "create" if method == "post" else "update", service)
        response = getattr(client, method)("/batches" if method == "post" else f"/batches/{body['id']}", json={"variant_id": variants[0].id, **payload})
        assert response.status_code == 422 and "location" not in response.headers
        assert service.call_count == 0
        db.expire_all()
        assert db.scalar(select(func.count()).select_from(Batch)) == before
        assert db.get(Batch, body["id"]).batch_number == "unchanged"

    @pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=-1", "limit=1.5", "limit=abc", "offset=-1", "offset=1.5", "offset=abc"])
    def test_invalid_query(self, client, db, query, monkeypatch):
        service = Mock(side_effect=AssertionError("must not call service"))
        monkeypatch.setattr(BatchService, "list", service)
        assert client.get(f"/batches?{query}").status_code == 422
        assert service.call_count == 0
        assert db.scalar(select(func.count()).select_from(Batch)) == 0

    @pytest.mark.parametrize("method", ["get", "patch"])
    @pytest.mark.parametrize("path", ["abc", "1.5"])
    def test_invalid_path(self, client, method, path):
        kwargs = {"json": {}} if method == "patch" else {}
        assert getattr(client, method)(f"/batches/{path}", **kwargs).status_code == 422

    def test_missing_body_and_required_fk(self, client):
        assert client.post("/batches", json={}).status_code == 422
        assert client.post("/batches").status_code == 422
        assert client.patch("/batches/1").status_code == 422

    @pytest.mark.parametrize("quantity", [0.01, "99999999.99"])
    def test_quantity_boundaries(self, make_batch, quantity):
        assert make_batch(quantity=quantity)["quantity"] == str(quantity)

    def test_string_limits_unicode_and_date_coercion(self, make_batch):
        body = make_batch(batch_number="\u2003" + "Я" * 100 + "\u00a0", quantity_unit=" " + "m" * 30 + " ", manufacture_date=0)
        assert body["batch_number"] == "Я" * 100
        assert body["quantity_unit"] == "m" * 30
        assert body["manufacture_date"] == "1970-01-01"


class TestBatchErrors:
    @pytest.mark.parametrize("key", [0, -1, 999999])
    def test_missing_batch(self, client, key):
        for method, kwargs in [("get", {}), ("patch", {"json": {"variant_id": 999999}})]:
            response = getattr(client, method)(f"/batches/{key}", **kwargs)
            assert response.status_code == 404
            assert response.json() == {"detail": f"Batch {key} not found"}
            assert "location" not in response.headers

    def test_unknown_variant_and_priorities(self, client, make_batch, db):
        body = make_batch(batch_number="old", quantity="5")
        path = f"/batches/{body['id']}"
        for method, url, payload in [("post", "/batches", {"variant_id": 999999}), ("patch", path, {"variant_id": 999999, "batch_number": "new", "quantity": None})]:
            response = getattr(client, method)(url, json=payload)
            assert response.status_code == 404
            assert response.json() == {"detail": "Variant 999999 not found"}
            assert "location" not in response.headers
        assert client.patch("/batches/999999", json={"variant_id": None}).status_code == 422
        assert client.patch(path, json={"variant_id": 999999, "quantity": "1.005"}).status_code == 422
        db.expire_all()
        assert db.scalar(select(func.count()).select_from(Batch)) == 1
        assert client.get(path).json() == body

    @pytest.mark.parametrize("method", ["post", "get", "patch", "list"])
    def test_unexpected_500_safe(self, db, tmp_path, monkeypatch, variants, method):
        def unexpected(*_args, **_kwargs):
            raise RuntimeError("secret SQL /private/path")
        monkeypatch.setattr(BatchService, {"post": "create", "get": "get_by_id", "patch": "update", "list": "list"}[method], unexpected)
        with batch_client(db, tmp_path, raise_server_exceptions=False) as client:
            if method == "list":
                response = client.get("/batches")
            elif method == "get":
                response = client.get("/batches/1")
            elif method == "post":
                response = client.post("/batches", json={"variant_id": variants[0].id})
            else:
                response = client.patch("/batches/1", json={})
        assert app.debug is False
        assert response.status_code == 500
        assert response.text == "Internal Server Error"
        assert "location" not in response.headers


class TestBatchFixtures:
    @pytest.mark.parametrize("existing", [False, True])
    @pytest.mark.parametrize("fail", [False, True])
    def test_restores_overrides_and_settings_even_after_exception(self, db, tmp_path, existing, fail):
        original_overrides = dict(app.dependency_overrides)
        original_settings = main_module.get_settings
        prior = lambda: "prior"
        unrelated = lambda: "unrelated"
        app.dependency_overrides[unrelated] = prior
        if existing:
            app.dependency_overrides[get_db] = prior
        else:
            app.dependency_overrides.pop(get_db, None)
        try:
            try:
                with batch_client(db, tmp_path) as client:
                    assert client.get("/batches").status_code == 200
                    assert main_module.get_settings().LOG_FILE == str(tmp_path / "app.log")
                    if fail:
                        raise RuntimeError("fixture failure")
            except RuntimeError:
                assert fail
            assert app.dependency_overrides.get(get_db, _MISSING) is (prior if existing else _MISSING)
            assert app.dependency_overrides[unrelated] is prior
            assert main_module.get_settings is original_settings
        finally:
            app.dependency_overrides.pop(unrelated, None)
            if get_db in original_overrides:
                app.dependency_overrides[get_db] = original_overrides[get_db]
            else:
                app.dependency_overrides.pop(get_db, None)
