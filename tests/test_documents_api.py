"""HTTP tests for the document collection and card routes.

Only three operations exist in this slice — `POST /documents`,
`GET /documents` and `GET /documents/{document_id}` — so the assertions here
also pin what is deliberately absent: no `PATCH`, no verification route, no
history and no `DELETE`. The routes are exercised through `TestClient` against
the isolated test schema `test_file_service`, created by the shared `engine`
fixture; the working database is never touched.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.document_types.schemas import DocumentTypeCreate
from app.api.documents.schemas import DocumentCreate
from app.api.issuers.schemas import IssuerCreate
from app.config import Settings, get_settings
from app.database.connection import get_db
from app.main import app
from app.models.document import Document
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.file import File
from app.services.document_service import DocumentService
from app.services.document_type_service import DocumentTypeService
from app.services.issuer_service import IssuerService

DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"

# A minimal but real PDF: the service identifies the type by signature, so the
# declared content type alone would not be enough.
PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"

#: An id no database row can carry, used to force the reference checks.
UNKNOWN_ID = 10_000_000

#: The exact public surface of `DocumentOut`.
DOCUMENT_FIELDS = {
    "id",
    "document_type_id",
    "number",
    "issue_date",
    "valid_from",
    "valid_to",
    "issuer_id",
    "verification_status",
    "notes",
}

#: Things a response must never carry: storage internals, ORM relationships and
#: history.
INTERNAL_FIELDS = {
    "storage_key",
    "files",
    "document_type",
    "issuer",
    "products",
    "variants",
    "batches",
    "events",
}

_MISSING = object()


@pytest.fixture
def client(db, tmp_path):
    """HTTP client wired to the test session and a scratch storage root.

    `get_db` is replaced with the session the test uses, and `get_settings` with
    storage rooted in `tmp_path`, so neither the working database nor the
    project's `storage/` directory can be reached. Any override already present
    is saved and restored, so a failing test cannot leak it.
    """
    previous_db = app.dependency_overrides.get(get_db, _MISSING)
    previous_settings = app.dependency_overrides.get(get_settings, _MISSING)
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        STORAGE_ROOT=str(tmp_path / "storage"),
        MAX_UPLOAD_SIZE_BYTES=1024,
    )
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as test_client:
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


@pytest.fixture
def document_type(db):
    return DocumentTypeService.create(
        db, DocumentTypeCreate(name=f"Type {uuid.uuid4().hex[:12]}")
    )


@pytest.fixture
def issuer(db):
    return IssuerService.create(
        db, IssuerCreate(name=f"Issuer {uuid.uuid4().hex[:12]}")
    )


@pytest.fixture
def make_document(db, document_type):
    def _make(**overrides) -> Document:
        values: dict[str, object] = {
            "document_type_id": document_type.id,
            "number": f"DOC-{uuid.uuid4().hex[:8]}",
        }
        values.update(overrides)
        return DocumentService.create(db, DocumentCreate(**values))  # type: ignore[arg-type]

    return _make


def payload(document_type_id: int, **overrides: object) -> dict:
    values: dict[str, object] = {
        "document_type_id": document_type_id,
        "number": "CERT-001",
    }
    values.update(overrides)
    return values


def count_rows(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


class TestCreateDocument:
    def test_returns_201(self, client, document_type):
        response = client.post("/documents", json=payload(document_type.id))
        assert response.status_code == 201

    def test_content_type_is_json(self, client, document_type):
        response = client.post("/documents", json=payload(document_type.id))
        assert response.headers["content-type"].startswith("application/json")

    def test_new_document_is_pending(self, client, document_type):
        body = client.post("/documents", json=payload(document_type.id)).json()
        assert body["verification_status"] == "pending"

    def test_returns_exactly_the_public_fields(self, client, document_type):
        body = client.post("/documents", json=payload(document_type.id)).json()
        assert set(body) == DOCUMENT_FIELDS

    def test_values_match_the_payload(self, client, document_type):
        body = client.post(
            "/documents",
            json=payload(
                document_type.id,
                number="CERT-777",
                issue_date="2026-01-15",
                valid_from="2026-01-15",
                valid_to="2027-01-15",
                notes="Испытания пройдены",
            ),
        ).json()
        assert body["document_type_id"] == document_type.id
        assert body["number"] == "CERT-777"
        assert body["issue_date"] == "2026-01-15"
        assert body["valid_from"] == "2026-01-15"
        assert body["valid_to"] == "2027-01-15"
        assert body["notes"] == "Испытания пройдены"

    def test_optional_fields_are_null_by_default(self, client, document_type):
        body = client.post("/documents", json=payload(document_type.id)).json()
        assert body["issue_date"] is None
        assert body["valid_from"] is None
        assert body["valid_to"] is None
        assert body["issuer_id"] is None
        assert body["notes"] is None

    def test_issuer_id_is_accepted(self, client, document_type, issuer):
        body = client.post(
            "/documents", json=payload(document_type.id, issuer_id=issuer.id)
        ).json()
        assert body["issuer_id"] == issuer.id

    def test_number_is_stripped(self, client, document_type):
        body = client.post(
            "/documents", json=payload(document_type.id, number="  CERT-1  ")
        ).json()
        assert body["number"] == "CERT-1"

    def test_location_header_points_at_the_card(self, client, document_type):
        response = client.post("/documents", json=payload(document_type.id))
        document_id = response.json()["id"]
        assert response.headers["location"].endswith(f"/documents/{document_id}")

    def test_row_is_persisted_in_the_database(self, client, db, document_type):
        body = client.post("/documents", json=payload(document_type.id)).json()
        db.expire_all()
        stored = db.get(Document, body["id"])
        assert stored is not None
        assert stored.number == body["number"]

    def test_row_is_persisted_in_the_isolated_schema(
        self, client, db, document_type
    ):
        body = client.post("/documents", json=payload(document_type.id)).json()
        assert count_rows(db, Document) == 1
        assert db.get(Document, body["id"]) is not None

    def test_missing_document_type_is_422(self, client):
        response = client.post("/documents", json=payload(UNKNOWN_ID))
        assert response.status_code == 422

    def test_missing_issuer_is_422(self, client, document_type):
        response = client.post(
            "/documents", json=payload(document_type.id, issuer_id=UNKNOWN_ID)
        )
        assert response.status_code == 422

    def test_missing_document_type_writes_nothing(self, client, db):
        client.post("/documents", json=payload(UNKNOWN_ID))
        assert count_rows(db, Document) == 0

    def test_missing_issuer_writes_nothing(self, client, db, document_type):
        client.post(
            "/documents", json=payload(document_type.id, issuer_id=UNKNOWN_ID)
        )
        assert count_rows(db, Document) == 0

    def test_missing_number_is_422(self, client, document_type):
        response = client.post(
            "/documents", json={"document_type_id": document_type.id}
        )
        assert response.status_code == 422

    def test_unknown_field_is_422(self, client, document_type):
        response = client.post(
            "/documents",
            json=payload(document_type.id, verification_status="verified"),
        )
        assert response.status_code == 422

    def test_boolean_document_type_id_is_422(self, client):
        response = client.post(
            "/documents", json={"document_type_id": True, "number": "CERT-1"}
        )
        assert response.status_code == 422

    def test_non_positive_document_type_id_is_422(self, client):
        response = client.post(
            "/documents", json={"document_type_id": 0, "number": "CERT-1"}
        )
        assert response.status_code == 422

    def test_inverted_validity_window_is_422(self, client, document_type):
        response = client.post(
            "/documents",
            json=payload(
                document_type.id,
                valid_from="2026-01-10",
                valid_to="2026-01-01",
            ),
        )
        assert response.status_code == 422

    def test_error_body_is_json(self, client):
        response = client.post("/documents", json=payload(UNKNOWN_ID))
        assert response.headers["content-type"].startswith("application/json")
        assert "detail" in response.json()

    def test_error_body_leaks_no_internals(self, client):
        response = client.post("/documents", json=payload(UNKNOWN_ID))
        lowered = response.text.lower()
        for needle in (
            "select",
            "insert",
            "update",
            "postgresql",
            "psycopg",
            "traceback",
            "storage_key",
            "password",
        ):
            assert needle not in lowered, needle

    def test_no_verification_event_is_written(self, client, db, document_type):
        body = client.post("/documents", json=payload(document_type.id)).json()
        events = db.scalar(
            select(func.count())
            .select_from(DocumentVerificationEvent)
            .where(DocumentVerificationEvent.document_id == body["id"])
        )
        assert events == 0

    def test_no_file_is_created(self, client, db, document_type):
        client.post("/documents", json=payload(document_type.id))
        assert count_rows(db, File) == 0

    def test_response_exposes_no_internal_fields(self, client, document_type):
        response = client.post("/documents", json=payload(document_type.id))
        assert set(response.json()).isdisjoint(INTERNAL_FIELDS)
        assert "storage_key" not in response.text


class TestListDocuments:
    def test_empty_returns_200_and_empty_array(self, client):
        response = client.get("/documents")
        assert response.status_code == 200
        assert response.json() == []

    def test_content_type_is_json(self, client, make_document):
        make_document()
        response = client.get("/documents")
        assert response.headers["content-type"].startswith("application/json")

    def test_body_is_a_json_array(self, client, make_document):
        make_document()
        assert isinstance(client.get("/documents").json(), list)

    def test_returns_all_rows(self, client, make_document):
        for _ in range(3):
            make_document()
        assert len(client.get("/documents").json()) == 3

    def test_order_is_id_ascending(self, client, make_document):
        ids = [make_document().id for _ in range(4)]
        returned = [item["id"] for item in client.get("/documents").json()]
        assert returned == sorted(ids)

    def test_default_limit_is_fifty(self, client, make_document):
        for _ in range(52):
            make_document()
        assert len(client.get("/documents").json()) == 50

    def test_limit_one(self, client, make_document):
        for _ in range(3):
            make_document()
        assert len(client.get("/documents", params={"limit": 1}).json()) == 1

    def test_limit_one_hundred(self, client, make_document):
        for _ in range(3):
            make_document()
        assert len(client.get("/documents", params={"limit": 100}).json()) == 3

    def test_limit_zero_is_422(self, client):
        assert client.get("/documents", params={"limit": 0}).status_code == 422

    def test_limit_above_maximum_is_422(self, client):
        assert client.get("/documents", params={"limit": 101}).status_code == 422

    def test_negative_limit_is_422(self, client):
        assert client.get("/documents", params={"limit": -1}).status_code == 422

    def test_negative_offset_is_422(self, client):
        assert client.get("/documents", params={"offset": -1}).status_code == 422

    def test_non_integer_limit_is_422(self, client):
        assert client.get("/documents", params={"limit": "x"}).status_code == 422

    def test_offset_skips_the_first_rows(self, client, make_document):
        ids = [make_document().id for _ in range(3)]
        returned = [
            item["id"] for item in client.get("/documents", params={"offset": 1}).json()
        ]
        assert returned == sorted(ids)[1:]

    def test_offset_beyond_end_is_empty(self, client, make_document):
        make_document()
        response = client.get("/documents", params={"offset": 10})
        assert response.status_code == 200
        assert response.json() == []

    def test_default_offset_is_zero(self, client, make_document):
        ids = [make_document().id for _ in range(2)]
        returned = [item["id"] for item in client.get("/documents").json()]
        assert returned == sorted(ids)

    def test_items_expose_only_public_fields(self, client, make_document):
        make_document()
        item = client.get("/documents").json()[0]
        assert set(item) == DOCUMENT_FIELDS

    def test_items_expose_no_internal_fields(self, client, make_document):
        make_document()
        response = client.get("/documents")
        assert "storage_key" not in response.text
        for item in response.json():
            assert set(item).isdisjoint(INTERNAL_FIELDS)

    def test_does_not_modify_rows(self, client, db, make_document):
        document = make_document()
        client.get("/documents")
        db.expire_all()
        assert db.get(Document, document.id).verification_status == "pending"

    def test_writes_no_history_events(self, client, db, make_document):
        make_document()
        client.get("/documents")
        assert count_rows(db, DocumentVerificationEvent) == 0


class TestGetDocument:
    def test_returns_200(self, client, make_document):
        document = make_document()
        assert client.get(f"/documents/{document.id}").status_code == 200

    def test_body_matches_the_stored_row(self, client, make_document):
        document = make_document(number="CERT-42", notes="note")
        body = client.get(f"/documents/{document.id}").json()
        assert body["id"] == document.id
        assert body["number"] == "CERT-42"
        assert body["notes"] == "note"
        assert body["verification_status"] == "pending"

    def test_returns_exactly_the_public_fields(self, client, make_document):
        document = make_document()
        assert set(client.get(f"/documents/{document.id}").json()) == DOCUMENT_FIELDS

    def test_unknown_id_is_404(self, client):
        assert client.get(f"/documents/{UNKNOWN_ID}").status_code == 404

    def test_zero_is_404(self, client):
        assert client.get("/documents/0").status_code == 404

    def test_negative_id_is_404(self, client):
        assert client.get("/documents/-1").status_code == 404

    def test_error_is_a_json_detail(self, client):
        response = client.get(f"/documents/{UNKNOWN_ID}")
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == {"detail": f"Document {UNKNOWN_ID} not found"}

    def test_error_body_leaks_no_internals(self, client):
        lowered = client.get(f"/documents/{UNKNOWN_ID}").text.lower()
        for needle in ("select", "postgresql", "psycopg", "traceback", "storage_key"):
            assert needle not in lowered, needle

    def test_does_not_modify_the_row(self, client, db, make_document):
        document = make_document()
        client.get(f"/documents/{document.id}")
        db.expire_all()
        stored = db.get(Document, document.id)
        assert stored.verification_status == "pending"
        assert stored.number == document.number

    def test_writes_no_history_event(self, client, db, make_document):
        document = make_document()
        client.get(f"/documents/{document.id}")
        client.get(f"/documents/{document.id}")
        events = db.scalar(
            select(func.count())
            .select_from(DocumentVerificationEvent)
            .where(DocumentVerificationEvent.document_id == document.id)
        )
        assert events == 0

    def test_exposes_no_internal_fields(self, client, make_document):
        document = make_document()
        response = client.get(f"/documents/{document.id}")
        assert set(response.json()).isdisjoint(INTERNAL_FIELDS)
        assert "storage_key" not in response.text

    def test_card_has_no_attachments_or_links(self, client, make_document):
        document = make_document()
        body = client.get(f"/documents/{document.id}").json()
        assert "files" not in body
        assert "products" not in body
        assert "variants" not in body
        assert "batches" not in body


class TestReadOnlyGuarantees:
    def test_a_full_read_sequence_writes_no_history(
        self, client, db, make_document
    ):
        document = make_document()
        client.get("/documents")
        client.get(f"/documents/{document.id}")
        client.get("/documents", params={"limit": 100, "offset": 0})
        assert count_rows(db, DocumentVerificationEvent) == 0

    def test_reads_leave_the_row_count_unchanged(self, client, db, make_document):
        make_document()
        before = count_rows(db, Document)
        client.get("/documents")
        client.get("/documents/1")
        assert count_rows(db, Document) == before


class TestFileApiIntegration:
    def test_file_upload_still_works_for_a_new_document(
        self, client, db, document_type
    ):
        created = client.post("/documents", json=payload(document_type.id))
        document_id = created.json()["id"]

        # `attach` refuses a session that already has a transaction, and the
        # create above left a read transaction from its `refresh`.
        db.rollback()

        response = client.post(
            f"/documents/{document_id}/files",
            files={"file": ("scan.pdf", PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == 201
        assert response.json()["document_id"] == document_id

    def test_file_routes_are_still_declared(self):
        paths = app.openapi()["paths"]
        assert set(paths["/documents/{document_id}/files"]) == {"get", "post"}
        assert set(paths["/documents/{document_id}/files/{file_id}"]) == {
            "get",
            "delete",
        }
        assert set(paths["/documents/{document_id}/files/{file_id}/content"]) == {
            "get"
        }


class TestOpenApiContract:
    def test_documents_expose_exactly_four_operations(self):
        paths = app.openapi()["paths"]
        operations = {
            (path, method)
            for path, item in paths.items()
            if path == "/documents"
            or path == "/documents/{document_id}"
            for method in item
        }
        assert operations == {
            ("/documents", "get"),
            ("/documents", "post"),
            ("/documents/{document_id}", "get"),
            ("/documents/{document_id}", "patch"),
        }

    def test_verification_history_route_is_declared(self):
        paths = app.openapi()["paths"]
        assert set(paths["/documents/{document_id}/verification-history"]) == {"get"}

    def test_no_delete_for_documents(self):
        paths = app.openapi()["paths"]
        assert "delete" not in paths["/documents"]
        assert "delete" not in paths["/documents/{document_id}"]

    def test_document_out_schema_is_unchanged(self):
        props = app.openapi()["components"]["schemas"]["DocumentOut"]["properties"]
        assert set(props) == DOCUMENT_FIELDS
