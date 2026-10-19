"""HTTP contract for the sizes a document is linked to.

`TASK-DOC-007C` exposes two operations on one path:

* `GET  /documents/{document_id}/variants` — read the linked sizes;
* `PUT  /documents/{document_id}/variants` — replace them wholesale.

Only HTTP is exercised. Documents, products and variants are created through
their own routes, so the fixtures depend on the rest of the API working rather
than on an import of any service — which is also the cheapest way to keep an eye
on the neighbours.

Two things are checked as carefully as the happy path:

* **What the schema refuses.** An identifier is an integer primary key, so
  `"3"`, `3.0`, `3.5`, `true`, `0` and `-1` are all `422`, as are a missing or
  null list, duplicates and unknown fields.
* **What linking leaves alone.** A replacement is not a verdict change: the
  status and the verification history are identical before and after, and the
  `document_products` / `document_batches` tables are never written.

Everything runs against the scratch schema `test_file_service` and a temporary
storage root; the working database and `storage/` are never touched.
"""

import ast
import inspect
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.connection import get_db
from app.main import app
from app.models.document_verification_event import DocumentVerificationEvent
from app.services.document_variant_service import (
    DocumentVariantService,
    DuplicateVariantIdsError,
    ProductVariantsNotFoundError,
    TransactionAlreadyOpenError,
    UncommittedDocumentChangesError,
)

DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"
MAX_BYTES = 64 * 1024

PDF = (
    b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    b"trailer\n<<>>\n%%EOF\n"
)

# The public shape of a linked variant. `storage_key`, ORM collections and any
# other internal column must never appear.
PUBLIC_VARIANT_FIELDS = {
    "id",
    "product_id",
    "size_text",
    "diameter",
    "nominal_diameter",
    "wall_thickness",
}

_MISSING = object()


@pytest.fixture
def client(engine, tmp_path):
    """A client whose every request gets its own session, as in production."""

    def override_get_db():
        session = Session(engine, future=True)
        try:
            yield session
        finally:
            session.close()

    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        STORAGE_ROOT=str(tmp_path / "storage"),
        MAX_UPLOAD_SIZE_BYTES=MAX_BYTES,
    )
    previous_db = app.dependency_overrides.get(get_db, _MISSING)
    previous_settings = app.dependency_overrides.get(get_settings, _MISSING)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        if previous_db is _MISSING:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_db
        if previous_settings is _MISSING:
            app.dependency_overrides.pop(get_settings, None)
        else:
            app.dependency_overrides[get_settings] = previous_settings


# --------------------------------------------------------------------------- #
# HTTP helpers — no service is called to build the fixtures
# --------------------------------------------------------------------------- #


def create_manufacturer(client: TestClient, name: str | None = None) -> int:
    response = client.post(
        "/manufacturers", json={"name": name or f"Завод {uuid.uuid4().hex[:8]}"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_product(client: TestClient, manufacturer_id: int) -> int:
    response = client.post(
        "/products",
        json={
            "name": f"Труба ПЭ100 SDR11 {uuid.uuid4().hex[:8]}",
            "standard": "ГОСТ 58121.2-2018",
            "manufacturer_id": manufacturer_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_variant(client: TestClient, product_id: int, size_text: str) -> int:
    response = client.post(
        f"/products/{product_id}/variants", json={"size_text": size_text}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def product_variants(client: TestClient, sizes: list[str]) -> list[int]:
    """One product holding the given sizes; returns the variant ids in order."""
    manufacturer_id = create_manufacturer(client)
    product_id = create_product(client, manufacturer_id)
    return [create_variant(client, product_id, size) for size in sizes]


def create_document_type(client: TestClient) -> int:
    response = client.post(
        "/document-types", json={"name": f"Тип {uuid.uuid4().hex[:8]}"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_document(client: TestClient, document_type_id: int) -> int:
    response = client.post(
        "/documents",
        json={
            "document_type_id": document_type_id,
            "number": f"D-{uuid.uuid4().hex[:8]}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(client: TestClient, document_id: int) -> dict:
    response = client.post(
        f"/documents/{document_id}/files",
        files={"file": ("scan.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def decide(
    client: TestClient, document_id: int, decision: str, reason: str | None = None
):
    body: dict[str, object] = {"decision": decision}
    if reason is not None:
        body["reason"] = reason
    return client.post(f"/documents/{document_id}/verification", json=body)


def document_status(client: TestClient, document_id: int) -> str:
    response = client.get(f"/documents/{document_id}")
    assert response.status_code == 200, response.text
    return response.json()["verification_status"]


def get_variants(client: TestClient, document_id: int):
    return client.get(f"/documents/{document_id}/variants")


def linked_ids(client: TestClient, document_id: int) -> list[int]:
    response = get_variants(client, document_id)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()]


def put_variants(client: TestClient, document_id: int, variant_ids):
    return client.put(
        f"/documents/{document_id}/variants", json={"variant_ids": variant_ids}
    )


def event_count(db: Session, document_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(DocumentVerificationEvent)
        .where(DocumentVerificationEvent.document_id == document_id)
    )


def a_verified_document(client: TestClient) -> int:
    """A document that reached `verified` the way a user would, over HTTP."""
    document_id = create_document(client, create_document_type(client))
    upload(client, document_id)
    assert decide(client, document_id, "verified").status_code == 200
    return document_id


# --------------------------------------------------------------------------- #
# 1-3: readings
# --------------------------------------------------------------------------- #


class TestRead:
    def test_missing_document_is_404(self, client):
        response = get_variants(client, 9_999_999)
        assert response.status_code == 404, response.text

    def test_empty_list_is_200_and_empty(self, client):
        document_id = create_document(client, create_document_type(client))

        response = get_variants(client, document_id)

        assert response.status_code == 200
        assert response.json() == []

    def test_three_linked_variants_are_returned_in_id_order(self, client):
        document_id = create_document(client, create_document_type(client))
        a, b, c = product_variants(client, ["Ø32", "Ø63", "Ø110"])
        # link out of order, so the read order cannot come from the request
        assert put_variants(client, document_id, [c, a, b]).status_code == 200

        response = get_variants(client, document_id)

        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [a, b, c]


# --------------------------------------------------------------------------- #
# 4-10: replacements
# --------------------------------------------------------------------------- #


class TestReplace:
    def test_links_one_variant(self, client):
        document_id = create_document(client, create_document_type(client))
        (variant_id,) = product_variants(client, ["Ø63"])

        response = put_variants(client, document_id, [variant_id])

        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()] == [variant_id]
        assert linked_ids(client, document_id) == [variant_id]

    def test_links_three_variants_of_one_product(self, client):
        document_id = create_document(client, create_document_type(client))
        variant_ids = product_variants(client, ["Ø32", "Ø63", "Ø110"])

        response = put_variants(client, document_id, variant_ids)

        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()] == sorted(variant_ids)
        assert linked_ids(client, document_id) == sorted(variant_ids)

    def test_links_variants_of_different_products(self, client):
        document_id = create_document(client, create_document_type(client))
        (first,) = product_variants(client, ["Ø63"])
        (second,) = product_variants(client, ["Ø110"])

        response = put_variants(client, document_id, [first, second])

        assert response.status_code == 200, response.text
        assert linked_ids(client, document_id) == sorted([first, second])

    def test_replaces_a_b_with_b_c(self, client):
        document_id = create_document(client, create_document_type(client))
        a, b, c = product_variants(client, ["Ø32", "Ø63", "Ø110"])
        assert put_variants(client, document_id, [a, b]).status_code == 200

        assert put_variants(client, document_id, [b, c]).status_code == 200

        assert linked_ids(client, document_id) == sorted([b, c])

    def test_empty_list_clears_every_link(self, client):
        document_id = create_document(client, create_document_type(client))
        variant_ids = product_variants(client, ["Ø32", "Ø63", "Ø110"])
        assert put_variants(client, document_id, variant_ids).status_code == 200

        response = put_variants(client, document_id, [])

        assert response.status_code == 200, response.text
        assert response.json() == []
        assert linked_ids(client, document_id) == []

    def test_repeating_the_same_set_is_accepted(self, client, db):
        document_id = create_document(client, create_document_type(client))
        variant_ids = product_variants(client, ["Ø32", "Ø63"])
        first = put_variants(client, document_id, variant_ids)
        assert first.status_code == 200

        second = put_variants(client, document_id, variant_ids)

        assert second.status_code == 200, second.text
        assert second.json() == first.json()
        assert linked_ids(client, document_id) == sorted(variant_ids)

    def test_request_order_does_not_change_the_result(self, client):
        document_id = create_document(client, create_document_type(client))
        a, b, c = product_variants(client, ["Ø32", "Ø63", "Ø110"])

        response = put_variants(client, document_id, [c, a, b])

        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()] == [a, b, c]


# --------------------------------------------------------------------------- #
# 11-18: what the schema and the service refuse
# --------------------------------------------------------------------------- #


class TestErrors:
    def test_missing_document_on_put_is_404(self, client):
        (variant_id,) = product_variants(client, ["Ø63"])

        response = put_variants(client, 9_999_999, [variant_id])

        assert response.status_code == 404, response.text

    def test_missing_variant_is_422(self, client):
        document_id = create_document(client, create_document_type(client))

        response = put_variants(client, document_id, [9_999_999])

        assert response.status_code == 422, response.text
        assert linked_ids(client, document_id) == []

    def test_mixed_list_changes_nothing(self, client):
        document_id = create_document(client, create_document_type(client))
        a, b = product_variants(client, ["Ø32", "Ø63"])
        assert put_variants(client, document_id, [a, b]).status_code == 200

        response = put_variants(client, document_id, [a, 9_999_999])

        assert response.status_code == 422, response.text
        assert linked_ids(client, document_id) == sorted([a, b])

    def test_duplicates_are_422(self, client):
        document_id = create_document(client, create_document_type(client))
        (variant_id,) = product_variants(client, ["Ø63"])

        response = put_variants(client, document_id, [variant_id, variant_id])

        assert response.status_code == 422, response.text
        assert linked_ids(client, document_id) == []

    def test_missing_variant_ids_is_422(self, client):
        document_id = create_document(client, create_document_type(client))

        response = client.put(
            f"/documents/{document_id}/variants", json={}
        )

        assert response.status_code == 422, response.text

    def test_null_variant_ids_is_422(self, client):
        document_id = create_document(client, create_document_type(client))

        response = client.put(
            f"/documents/{document_id}/variants", json={"variant_ids": None}
        )

        assert response.status_code == 422, response.text

    def test_variant_ids_must_be_a_list(self, client):
        document_id = create_document(client, create_document_type(client))

        response = client.put(
            f"/documents/{document_id}/variants", json={"variant_ids": 3}
        )

        assert response.status_code == 422, response.text

    @pytest.mark.parametrize(
        "bad_id",
        ["3", 3.0, 3.5, True, False, 0, -1],
    )
    def test_non_positive_integer_ids_are_422(self, client, bad_id):
        document_id = create_document(client, create_document_type(client))

        response = put_variants(client, document_id, [bad_id])

        assert response.status_code == 422, (bad_id, response.text)

    def test_extra_fields_are_422(self, client):
        document_id = create_document(client, create_document_type(client))

        response = client.put(
            f"/documents/{document_id}/variants",
            json={"variant_ids": [], "note": "extra"},
        )

        assert response.status_code == 422, response.text

    def test_errors_reveal_no_internals(self, client):
        document_id = create_document(client, create_document_type(client))
        (variant_id,) = product_variants(client, ["Ø63"])

        for response in (
            get_variants(client, 9_999_999),
            put_variants(client, document_id, [9_999_999]),
            put_variants(client, document_id, [variant_id, variant_id]),
        ):
            lowered = response.text.lower()
            for needle in ("select", "traceback", "psycopg", "storage_key", "password"):
                assert needle not in lowered, (needle, response.text)


# --------------------------------------------------------------------------- #
# 19-20: what the response exposes
# --------------------------------------------------------------------------- #


class TestResponseShape:
    def test_get_exposes_only_public_fields(self, client):
        document_id = create_document(client, create_document_type(client))
        (variant_id,) = product_variants(client, ["Ø63"])
        assert put_variants(client, document_id, [variant_id]).status_code == 200

        item = get_variants(client, document_id).json()[0]

        assert set(item) == PUBLIC_VARIANT_FIELDS
        assert item["size_text"] == "Ø63"

    def test_put_serialises_the_detached_objects(self, client):
        document_id = create_document(client, create_document_type(client))
        (variant_id,) = product_variants(client, ["Ø63"])

        item = put_variants(client, document_id, [variant_id]).json()[0]

        # every field is populated, not just the id: the service hands back
        # detached objects and the schema still has to read their attributes
        assert set(item) == PUBLIC_VARIANT_FIELDS
        assert item["id"] == variant_id
        assert item["size_text"] == "Ø63"
        assert item["product_id"] is not None


# --------------------------------------------------------------------------- #
# 21-27: isolation and the verdict
# --------------------------------------------------------------------------- #


class TestIsolationAndVerdict:
    def test_two_documents_keep_their_own_sets(self, client):
        first = create_document(client, create_document_type(client))
        second = create_document(client, create_document_type(client))
        a, b = product_variants(client, ["Ø32", "Ø63"])

        assert put_variants(client, first, [a]).status_code == 200
        assert put_variants(client, second, [b]).status_code == 200

        assert linked_ids(client, first) == [a]
        assert linked_ids(client, second) == [b]

    def test_one_variant_can_belong_to_many_documents(self, client):
        first = create_document(client, create_document_type(client))
        second = create_document(client, create_document_type(client))
        (variant_id,) = product_variants(client, ["Ø63"])

        assert put_variants(client, first, [variant_id]).status_code == 200
        assert put_variants(client, second, [variant_id]).status_code == 200

        assert linked_ids(client, first) == [variant_id]
        assert linked_ids(client, second) == [variant_id]

    def test_linking_keeps_pending(self, client, db):
        document_id = create_document(client, create_document_type(client))
        (variant_id,) = product_variants(client, ["Ø63"])

        assert put_variants(client, document_id, [variant_id]).status_code == 200

        assert document_status(client, document_id) == "pending"
        assert event_count(db, document_id) == 0

    def test_linking_keeps_verified(self, client, db):
        document_id = a_verified_document(client)
        before = event_count(db, document_id)
        (variant_id,) = product_variants(client, ["Ø63"])

        assert put_variants(client, document_id, [variant_id]).status_code == 200

        assert document_status(client, document_id) == "verified"
        assert event_count(db, document_id) == before

    def test_linking_keeps_rejected(self, client, db):
        document_id = create_document(client, create_document_type(client))
        upload(client, document_id)
        assert (
            decide(client, document_id, "rejected", "Скан нечитаем").status_code == 200
        )
        before = event_count(db, document_id)
        (variant_id,) = product_variants(client, ["Ø63"])

        assert put_variants(client, document_id, [variant_id]).status_code == 200

        assert document_status(client, document_id) == "rejected"
        assert event_count(db, document_id) == before

    def test_no_reopened_event_is_recorded(self, client):
        document_id = a_verified_document(client)
        (variant_id,) = product_variants(client, ["Ø63"])

        assert put_variants(client, document_id, [variant_id]).status_code == 200
        assert put_variants(client, document_id, []).status_code == 200

        history = client.get(f"/documents/{document_id}/verification-history")
        assert history.status_code == 200, history.text
        assert [row["event_type"] for row in history.json()] == ["verified"]

    def test_product_and_batch_link_tables_are_untouched(self, client, db):
        document_id = create_document(client, create_document_type(client))
        variant_ids = product_variants(client, ["Ø32", "Ø63", "Ø110"])

        assert put_variants(client, document_id, variant_ids).status_code == 200

        assert db.scalar(text("select count(*) from document_products")) == 0
        assert db.scalar(text("select count(*) from document_batches")) == 0


# --------------------------------------------------------------------------- #
# 28-31: the router delegates, and the error table
# --------------------------------------------------------------------------- #


class TestRouterDelegates:
    def test_put_calls_the_service(self, client, monkeypatch):
        document_id = create_document(client, create_document_type(client))
        (variant_id,) = product_variants(client, ["Ø63"])
        original = DocumentVariantService.set_variants
        calls: list[tuple] = []

        def spy(db, document_id_, variant_ids):
            calls.append((document_id_, list(variant_ids)))
            return original(db, document_id_, variant_ids)

        monkeypatch.setattr(
            DocumentVariantService, "set_variants", staticmethod(spy)
        )

        assert put_variants(client, document_id, [variant_id]).status_code == 200

        assert calls == [(document_id, [variant_id])]

    def test_get_calls_the_service(self, client, monkeypatch):
        document_id = create_document(client, create_document_type(client))
        original = DocumentVariantService.list_variants
        seen: list[int] = []

        def spy(db, document_id_):
            seen.append(document_id_)
            return original(db, document_id_)

        monkeypatch.setattr(
            DocumentVariantService, "list_variants", staticmethod(spy)
        )

        assert get_variants(client, document_id).status_code == 200

        assert seen == [document_id]

    def test_the_router_runs_no_sql_of_its_own(self):
        from app.api.document_variants import router as router_module

        tree = ast.parse(inspect.getsource(router_module))
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert "commit" not in attributes
        assert "rollback" not in attributes
        assert "with_for_update" not in attributes
        assert "select" not in called_names

    def test_the_router_imports_the_service(self):
        from app.api.document_variants import router as router_module

        source = inspect.getsource(router_module)
        assert "DocumentVariantService" in source


class TestErrorMapping:
    def test_missing_document_maps_to_404(self, client):
        assert get_variants(client, 9_999_999).status_code == 404

    def test_missing_variant_maps_to_422(self, client):
        document_id = create_document(client, create_document_type(client))
        assert put_variants(client, document_id, [9_999_999]).status_code == 422

    def test_duplicate_ids_map_to_422(self, client, monkeypatch):
        # the schema refuses duplicates before the service is reached, so the
        # backstop branch is exercised by making the service raise directly
        document_id = create_document(client, create_document_type(client))
        (variant_id,) = product_variants(client, ["Ø63"])

        def raise_duplicate(db, document_id_, variant_ids):
            raise DuplicateVariantIdsError([variant_id])

        monkeypatch.setattr(
            DocumentVariantService, "set_variants", staticmethod(raise_duplicate)
        )

        response = put_variants(client, document_id, [variant_id])

        assert response.status_code == 422, response.text

    def test_transaction_conflict_maps_to_409(self, client, monkeypatch):
        document_id = create_document(client, create_document_type(client))

        def raise_conflict(db, document_id_, variant_ids):
            raise TransactionAlreadyOpenError("open")

        monkeypatch.setattr(
            DocumentVariantService, "set_variants", staticmethod(raise_conflict)
        )

        response = put_variants(client, document_id, [])

        assert response.status_code == 409, response.text
        assert "traceback" not in response.text.lower()

    def test_uncommitted_changes_map_to_409(self, client, monkeypatch):
        document_id = create_document(client, create_document_type(client))

        def raise_uncommitted(db, document_id_, variant_ids):
            raise UncommittedDocumentChangesError(document_id_)

        monkeypatch.setattr(
            DocumentVariantService, "set_variants", staticmethod(raise_uncommitted)
        )

        response = put_variants(client, document_id, [])

        assert response.status_code == 409, response.text

    def test_missing_variants_from_the_service_map_to_422(self, client, monkeypatch):
        document_id = create_document(client, create_document_type(client))

        def raise_missing(db, document_id_, variant_ids):
            raise ProductVariantsNotFoundError([7])

        monkeypatch.setattr(
            DocumentVariantService, "set_variants", staticmethod(raise_missing)
        )

        response = put_variants(client, document_id, [])

        assert response.status_code == 422, response.text


# --------------------------------------------------------------------------- #
# 32-34: the documented surface
# --------------------------------------------------------------------------- #


class TestContracts:
    def test_the_variants_path_carries_exactly_get_and_put(self):
        paths = app.openapi()["paths"]
        assert set(paths["/documents/{document_id}/variants"]) == {"get", "put"}

    def test_there_is_no_delete_for_a_single_link(self):
        paths = app.openapi()["paths"]
        for path in (
            "/documents/{document_id}/variants",
            "/documents/{document_id}/variants/{variant_id}",
        ):
            if path in paths:
                assert "delete" not in paths[path]

    def test_totals_grew_to_nineteen_paths_and_thirty_four_operations(self):
        paths = app.openapi()["paths"]
        assert len(paths) == 19
        assert sum(len(item) for item in paths.values()) == 34

    def test_put_body_requires_variant_ids(self):
        schema = app.openapi()
        operation = schema["paths"]["/documents/{document_id}/variants"]["put"]
        ref = operation["requestBody"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        name = ref.rsplit("/", 1)[-1]
        component = schema["components"]["schemas"][name]
        assert component["required"] == ["variant_ids"]
        assert "variant_ids" in component["properties"]

    def test_no_new_migration_was_added(self):
        from pathlib import Path

        versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        assert len(list(versions.glob("*.py"))) == 12

    def test_the_existing_document_and_file_api_is_untouched(self):
        paths = app.openapi()["paths"]
        assert set(paths["/documents"]) == {"get", "post"}
        assert set(paths["/documents/{document_id}"]) == {"get", "patch"}
        assert set(paths["/documents/{document_id}/files"]) == {"get", "post"}
        assert set(
            paths["/documents/{document_id}/files/{file_id}"]
        ) == {"get", "delete"}


# --------------------------------------------------------------------------- #
# 35: the scenario the feature exists for
# --------------------------------------------------------------------------- #


class TestCertificateCoversThreeSizes:
    def test_one_put_links_a_certificate_to_three_sizes(self, client):
        document_id = create_document(client, create_document_type(client))
        a, b, c = product_variants(client, ["Ø32", "Ø63", "Ø110"])

        response = put_variants(client, document_id, [a, b, c])

        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()] == [a, b, c]
        assert [
            item["size_text"] for item in get_variants(client, document_id).json()
        ] == ["Ø32", "Ø63", "Ø110"]
