"""HTTP tests for `PATCH /documents/{document_id}`.

The route is a thin shell over `DocumentService.update`; these tests pin the
HTTP contract (statuses, body, error mapping) and the lifecycle consequences
that the service already owns: a real change to a significant requisite on a
`verified` or `rejected` document resets it to `pending` and records exactly one
`reopened` event, while `notes` and repeated values do not. The working database
and the project's `storage/` are never touched: sessions come from the shared
`engine` fixture (schema `test_file_service`) and file storage is rooted in
`tmp_path`.
"""

import io
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.api.document_types.schemas import DocumentTypeCreate
from app.api.documents.schemas import DocumentCreate
from app.api.issuers.schemas import IssuerCreate
from app.config import Settings, get_settings
from app.database.connection import get_db
from app.main import app
from app.models.document import Document
from app.models.document_verification_event import DocumentVerificationEvent
from app.services.document_service import DocumentService
from app.services.document_type_service import DocumentTypeService
from app.services.file_service import FileService
from app.services.issuer_service import IssuerService
from app.services.local_storage import LocalStorageBackend

DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"

# A minimal but real PDF: the service identifies the type by signature.
PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"

UNKNOWN_ID = 10_000_000

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
    """HTTP client wired to the test session and a scratch storage root."""
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
def other_document_type(db):
    return DocumentTypeService.create(
        db, DocumentTypeCreate(name=f"Type {uuid.uuid4().hex[:12]}")
    )


@pytest.fixture
def issuer(db):
    return IssuerService.create(
        db, IssuerCreate(name=f"Issuer {uuid.uuid4().hex[:12]}")
    )


@pytest.fixture
def other_issuer(db):
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


@pytest.fixture
def file_service(db, tmp_path):
    return FileService(
        db,
        LocalStorageBackend(root_path=tmp_path / "storage"),
        max_upload_size_bytes=1024,
    )


@pytest.fixture
def attach(db, file_service):
    def _attach(document_id: int):
        # `attach` refuses a session that already has a transaction.
        db.rollback()
        return file_service.attach(document_id, "scan.pdf", io.BytesIO(PDF_BYTES))

    return _attach


@pytest.fixture
def make_verified(db, make_document, attach):
    """A `verified` document, reached through the real file and verify paths."""

    def _make(**overrides) -> Document:
        document = make_document(**overrides)
        attach(document.id)
        db.rollback()
        return DocumentService.verify(db, document.id)

    return _make


@pytest.fixture
def make_rejected(db, make_document):
    def _make(**overrides) -> Document:
        document = make_document(**overrides)
        db.rollback()
        return DocumentService.reject(db, document.id, "Повреждённый скан")

    return _make


def events_for(db, document_id: int) -> list[DocumentVerificationEvent]:
    db.expire_all()
    return list(
        db.scalars(
            select(DocumentVerificationEvent)
            .where(DocumentVerificationEvent.document_id == document_id)
            .order_by(DocumentVerificationEvent.id)
        )
    )


def reopened_events(db, document_id: int) -> list[DocumentVerificationEvent]:
    return [e for e in events_for(db, document_id) if e.event_type == "reopened"]


def status_of(db, document_id: int) -> str:
    db.expire_all()
    return db.get(Document, document_id).verification_status


def count_events(db, document_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(DocumentVerificationEvent)
        .where(DocumentVerificationEvent.document_id == document_id)
    )


class TestUpdateRequisites:
    def test_returns_200_and_updates_number(self, client, make_document):
        document = make_document(number="CERT-1")
        response = client.patch(f"/documents/{document.id}", json={"number": "CERT-2"})
        assert response.status_code == 200
        assert response.json()["number"] == "CERT-2"

    def test_content_type_is_json(self, client, make_document):
        document = make_document()
        response = client.patch(f"/documents/{document.id}", json={"number": "X"})
        assert response.headers["content-type"].startswith("application/json")

    def test_body_is_document_out(self, client, make_document):
        document = make_document()
        response = client.patch(f"/documents/{document.id}", json={"number": "X"})
        assert set(response.json()) == DOCUMENT_FIELDS

    def test_issue_date_is_updated(self, client, db, make_document):
        document = make_document()
        response = client.patch(
            f"/documents/{document.id}", json={"issue_date": "2026-02-20"}
        )
        assert response.json()["issue_date"] == "2026-02-20"
        assert db.get(Document, document.id).issue_date.isoformat() == "2026-02-20"

    def test_validity_window_is_updated(self, client, make_document):
        document = make_document()
        response = client.patch(
            f"/documents/{document.id}",
            json={"valid_from": "2026-01-01", "valid_to": "2027-01-01"},
        )
        body = response.json()
        assert body["valid_from"] == "2026-01-01"
        assert body["valid_to"] == "2027-01-01"

    def test_single_validity_bound_is_merged_with_stored(
        self, client, make_document
    ):
        document = make_document(valid_from="2026-01-01", valid_to="2026-12-31")
        body = client.patch(
            f"/documents/{document.id}", json={"valid_from": "2026-06-01"}
        ).json()
        assert body["valid_from"] == "2026-06-01"
        assert body["valid_to"] == "2026-12-31"

    def test_issuer_is_set(self, client, make_document, issuer):
        document = make_document()
        body = client.patch(
            f"/documents/{document.id}", json={"issuer_id": issuer.id}
        ).json()
        assert body["issuer_id"] == issuer.id

    def test_issuer_is_replaced(self, client, make_document, issuer, other_issuer):
        document = make_document(issuer_id=issuer.id)
        body = client.patch(
            f"/documents/{document.id}", json={"issuer_id": other_issuer.id}
        ).json()
        assert body["issuer_id"] == other_issuer.id

    def test_issuer_can_be_cleared(self, client, make_document, issuer):
        document = make_document(issuer_id=issuer.id)
        body = client.patch(
            f"/documents/{document.id}", json={"issuer_id": None}
        ).json()
        assert body["issuer_id"] is None

    def test_document_type_is_replaced(
        self, client, make_document, other_document_type
    ):
        document = make_document()
        body = client.patch(
            f"/documents/{document.id}",
            json={"document_type_id": other_document_type.id},
        ).json()
        assert body["document_type_id"] == other_document_type.id

    def test_notes_is_updated(self, client, make_document):
        document = make_document()
        body = client.patch(
            f"/documents/{document.id}", json={"notes": "Проверено вручную"}
        ).json()
        assert body["notes"] == "Проверено вручную"

    def test_notes_can_be_cleared(self, client, make_document):
        document = make_document(notes="старое")
        body = client.patch(f"/documents/{document.id}", json={"notes": None}).json()
        assert body["notes"] is None

    def test_number_is_stripped(self, client, make_document):
        document = make_document()
        body = client.patch(
            f"/documents/{document.id}", json={"number": "  CERT-9  "}
        ).json()
        assert body["number"] == "CERT-9"

    def test_id_never_changes(self, client, make_document):
        document = make_document()
        body = client.patch(f"/documents/{document.id}", json={"number": "X"}).json()
        assert body["id"] == document.id

    def test_absent_field_is_not_touched(self, client, db, make_document):
        document = make_document(number="CERT-1", notes="keep")
        client.patch(f"/documents/{document.id}", json={"notes": "changed"})
        db.expire_all()
        stored = db.get(Document, document.id)
        assert stored.number == "CERT-1"
        assert stored.notes == "changed"

    def test_persisted_in_database(self, client, db, make_document):
        document = make_document()
        client.patch(f"/documents/{document.id}", json={"number": "PERSISTED"})
        db.expire_all()
        assert db.get(Document, document.id).number == "PERSISTED"

    def test_exposes_no_internal_fields(self, client, make_document):
        document = make_document()
        response = client.patch(f"/documents/{document.id}", json={"number": "X"})
        assert set(response.json()).isdisjoint(INTERNAL_FIELDS)
        assert "storage_key" not in response.text


class TestUpdateErrors:
    def test_unknown_document_is_404(self, client):
        response = client.patch(f"/documents/{UNKNOWN_ID}", json={"number": "X"})
        assert response.status_code == 404

    def test_zero_is_404(self, client):
        assert client.patch("/documents/0", json={"number": "X"}).status_code == 404

    def test_negative_is_404(self, client):
        assert client.patch("/documents/-1", json={"number": "X"}).status_code == 404

    def test_error_is_a_json_detail(self, client):
        response = client.patch(f"/documents/{UNKNOWN_ID}", json={"number": "X"})
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == {"detail": f"Document {UNKNOWN_ID} not found"}

    def test_missing_document_type_is_422(self, client, make_document):
        document = make_document()
        response = client.patch(
            f"/documents/{document.id}", json={"document_type_id": UNKNOWN_ID}
        )
        assert response.status_code == 422

    def test_missing_issuer_is_422(self, client, make_document):
        document = make_document()
        response = client.patch(
            f"/documents/{document.id}", json={"issuer_id": UNKNOWN_ID}
        )
        assert response.status_code == 422

    def test_inverted_pair_is_422(self, client, make_document):
        document = make_document()
        response = client.patch(
            f"/documents/{document.id}",
            json={"valid_from": "2026-06-01", "valid_to": "2026-01-01"},
        )
        assert response.status_code == 422

    def test_inverted_merged_window_is_422(self, client, make_document):
        document = make_document(valid_from="2026-01-01", valid_to="2026-06-01")
        response = client.patch(
            f"/documents/{document.id}", json={"valid_from": "2026-07-01"}
        )
        assert response.status_code == 422

    def test_explicit_null_for_number_is_422(self, client, make_document):
        document = make_document()
        response = client.patch(f"/documents/{document.id}", json={"number": None})
        assert response.status_code == 422

    def test_explicit_null_for_document_type_is_422(self, client, make_document):
        document = make_document()
        response = client.patch(
            f"/documents/{document.id}", json={"document_type_id": None}
        )
        assert response.status_code == 422

    def test_unknown_field_is_422(self, client, make_document):
        document = make_document()
        response = client.patch(
            f"/documents/{document.id}", json={"unknown": "value"}
        )
        assert response.status_code == 422

    def test_verification_status_is_422(self, client, make_document):
        document = make_document()
        response = client.patch(
            f"/documents/{document.id}", json={"verification_status": "verified"}
        )
        assert response.status_code == 422

    def test_boolean_document_type_id_is_422(self, client, make_document):
        document = make_document()
        response = client.patch(
            f"/documents/{document.id}", json={"document_type_id": True}
        )
        assert response.status_code == 422

    def test_empty_number_is_422(self, client, make_document):
        document = make_document()
        response = client.patch(f"/documents/{document.id}", json={"number": "   "})
        assert response.status_code == 422

    def test_error_body_leaks_no_internals(self, client, make_document):
        document = make_document()
        response = client.patch(
            f"/documents/{document.id}", json={"document_type_id": UNKNOWN_ID}
        )
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

    def test_missing_type_writes_nothing(self, client, db, make_document):
        document = make_document(number="CERT-1")
        client.patch(
            f"/documents/{document.id}",
            json={"document_type_id": UNKNOWN_ID, "number": "CERT-2"},
        )
        db.expire_all()
        assert db.get(Document, document.id).number == "CERT-1"
        assert count_events(db, document.id) == 0

    def test_inverted_window_writes_nothing(self, client, db, make_document):
        document = make_document(valid_from="2026-01-01", valid_to="2026-06-01")
        client.patch(
            f"/documents/{document.id}", json={"valid_from": "2026-07-01"}
        )
        db.expire_all()
        stored = db.get(Document, document.id)
        assert stored.valid_from.isoformat() == "2026-01-01"
        assert count_events(db, document.id) == 0


class TestUpdateNoOp:
    def test_empty_patch_is_200(self, client, make_document):
        document = make_document()
        response = client.patch(f"/documents/{document.id}", json={})
        assert response.status_code == 200

    def test_empty_patch_leaves_row_untouched(self, client, db, make_document):
        document = make_document(number="CERT-1", notes="keep")
        body = client.patch(f"/documents/{document.id}", json={}).json()
        assert body["number"] == "CERT-1"
        assert body["notes"] == "keep"

    def test_empty_patch_writes_no_event(self, client, db, make_document):
        document = make_document()
        client.patch(f"/documents/{document.id}", json={})
        assert count_events(db, document.id) == 0

    def test_repeating_the_same_values_writes_no_event(
        self, client, db, make_document
    ):
        document = make_document(
            number="CERT-1",
            valid_from="2026-01-01",
            valid_to="2026-12-31",
        )
        response = client.patch(
            f"/documents/{document.id}",
            json={
                "number": "CERT-1",
                "valid_from": "2026-01-01",
                "valid_to": "2026-12-31",
            },
        )
        assert response.status_code == 200
        assert count_events(db, document.id) == 0

    def test_repeating_the_same_values_keeps_verified(
        self, client, db, make_verified
    ):
        document = make_verified(number="CERT-1")
        before = count_events(db, document.id)
        response = client.patch(
            f"/documents/{document.id}", json={"number": "CERT-1"}
        )
        assert response.json()["verification_status"] == "verified"
        assert status_of(db, document.id) == "verified"
        assert count_events(db, document.id) == before

    def test_repeating_the_same_values_keeps_rejected(
        self, client, db, make_rejected
    ):
        document = make_rejected(number="CERT-1")
        before = count_events(db, document.id)
        response = client.patch(
            f"/documents/{document.id}", json={"number": "CERT-1"}
        )
        assert response.json()["verification_status"] == "rejected"
        assert status_of(db, document.id) == "rejected"
        assert count_events(db, document.id) == before


class TestUpdateReopened:
    def test_pending_significant_change_writes_no_reopened(
        self, client, db, make_document
    ):
        document = make_document(number="CERT-1")
        client.patch(f"/documents/{document.id}", json={"number": "CERT-2"})
        assert status_of(db, document.id) == "pending"
        assert reopened_events(db, document.id) == []

    def test_pending_notes_change_writes_no_reopened(
        self, client, db, make_document
    ):
        document = make_document()
        client.patch(f"/documents/{document.id}", json={"notes": "x"})
        assert count_events(db, document.id) == 0

    def test_verified_significant_change_returns_to_pending(
        self, client, db, make_verified
    ):
        document = make_verified(number="CERT-1")
        response = client.patch(
            f"/documents/{document.id}", json={"number": "CERT-2"}
        )
        assert response.json()["verification_status"] == "pending"
        assert status_of(db, document.id) == "pending"

    def test_verified_significant_change_writes_one_reopened(
        self, client, db, make_verified
    ):
        document = make_verified(number="CERT-1")
        client.patch(f"/documents/{document.id}", json={"number": "CERT-2"})
        reopened = reopened_events(db, document.id)
        assert len(reopened) == 1

    def test_verified_reopened_event_matches_adr_008(
        self, client, db, make_verified
    ):
        document = make_verified(number="CERT-1")
        client.patch(f"/documents/{document.id}", json={"number": "CERT-2"})
        event = reopened_events(db, document.id)[0]
        assert event.from_status == "verified"
        assert event.to_status == "pending"
        assert event.event_type == "reopened"
        assert event.reason == "significant_fields_changed"

    def test_rejected_significant_change_returns_to_pending(
        self, client, db, make_rejected
    ):
        document = make_rejected(number="CERT-1")
        response = client.patch(
            f"/documents/{document.id}", json={"number": "CERT-2"}
        )
        assert response.json()["verification_status"] == "pending"
        assert status_of(db, document.id) == "pending"

    def test_rejected_significant_change_writes_one_reopened(
        self, client, db, make_rejected
    ):
        document = make_rejected(number="CERT-1")
        client.patch(f"/documents/{document.id}", json={"number": "CERT-2"})
        reopened = reopened_events(db, document.id)
        assert len(reopened) == 1

    def test_rejected_reopened_event_matches_adr_008(
        self, client, db, make_rejected
    ):
        document = make_rejected(number="CERT-1")
        client.patch(f"/documents/{document.id}", json={"number": "CERT-2"})
        event = reopened_events(db, document.id)[0]
        assert event.from_status == "rejected"
        assert event.to_status == "pending"
        assert event.reason == "significant_fields_changed"

    def test_every_significant_field_reopens(self, client, db, make_verified):
        cases = {
            "number": "CERT-NEW",
            "issue_date": "2026-05-05",
            "valid_from": "2026-01-01",
            "valid_to": "2027-01-01",
            "issuer_id": UNKNOWN_ID,  # replaced below for the valid case
        }
        for field, value in cases.items():
            document = make_verified()
            payload = {field: value}
            if field == "issuer_id":
                issuer = IssuerService.create(
                    db, IssuerCreate(name=f"Issuer {uuid.uuid4().hex[:8]}")
                )
                payload = {field: issuer.id}
            response = client.patch(f"/documents/{document.id}", json=payload)
            assert response.status_code == 200, field
            assert response.json()["verification_status"] == "pending", field
            assert len(reopened_events(db, document.id)) == 1, field

    def test_document_type_change_reopens(self, client, db, make_verified, other_document_type):
        document = make_verified()
        response = client.patch(
            f"/documents/{document.id}",
            json={"document_type_id": other_document_type.id},
        )
        assert response.json()["verification_status"] == "pending"
        assert len(reopened_events(db, document.id)) == 1

    def test_multiple_significant_fields_produce_one_event(
        self, client, db, make_verified
    ):
        document = make_verified(number="CERT-1")
        client.patch(
            f"/documents/{document.id}",
            json={"number": "CERT-2", "issue_date": "2026-03-03"},
        )
        assert len(reopened_events(db, document.id)) == 1

    def test_verified_notes_change_keeps_verified(
        self, client, db, make_verified
    ):
        document = make_verified()
        before = count_events(db, document.id)
        response = client.patch(
            f"/documents/{document.id}", json={"notes": "уточнение"}
        )
        assert response.json()["verification_status"] == "verified"
        assert status_of(db, document.id) == "verified"
        assert count_events(db, document.id) == before

    def test_rejected_notes_change_keeps_rejected(
        self, client, db, make_rejected
    ):
        document = make_rejected()
        before = count_events(db, document.id)
        response = client.patch(
            f"/documents/{document.id}", json={"notes": "уточнение"}
        )
        assert response.json()["verification_status"] == "rejected"
        assert status_of(db, document.id) == "rejected"
        assert count_events(db, document.id) == before

    def test_clearing_notes_keeps_verified(self, client, db, make_verified):
        document = make_verified(notes="старое")
        response = client.patch(f"/documents/{document.id}", json={"notes": None})
        assert response.json()["notes"] is None
        assert response.json()["verification_status"] == "verified"
        assert status_of(db, document.id) == "verified"

    def test_verified_issuer_clear_reopens(self, client, db, make_verified, issuer):
        document = make_verified(issuer_id=issuer.id)
        response = client.patch(
            f"/documents/{document.id}", json={"issuer_id": None}
        )
        assert response.json()["verification_status"] == "pending"
        assert len(reopened_events(db, document.id)) == 1


class TestUpdateIsolation:
    def test_other_documents_are_not_touched(self, client, db, make_document):
        first = make_document(number="CERT-1")
        second = make_document(number="CERT-2")
        client.patch(f"/documents/{first.id}", json={"number": "CERT-1-CHANGED"})
        db.expire_all()
        assert db.get(Document, second.id).number == "CERT-2"

    def test_history_of_other_documents_is_unchanged(
        self, client, db, make_verified, make_document
    ):
        verified = make_verified(number="CERT-1")
        other = make_document(number="CERT-2")
        before = count_events(db, other.id)
        client.patch(f"/documents/{verified.id}", json={"number": "CERT-3"})
        assert count_events(db, other.id) == before

    def test_only_the_target_document_changes_status(
        self, client, db, make_verified, make_document
    ):
        verified = make_verified(number="CERT-1")
        other = make_document(number="CERT-2")
        client.patch(f"/documents/{verified.id}", json={"number": "CERT-3"})
        assert status_of(db, other.id) == "pending"
        assert status_of(db, verified.id) == "pending"


class TestRouterBoundaries:
    def test_the_router_runs_no_sql_of_its_own(
        self, client, db, engine, monkeypatch
    ):
        calls: list[tuple[int, dict]] = []

        def fake_update(session, document_id, data):
            calls.append((document_id, data.model_dump(exclude_unset=True)))
            return None

        monkeypatch.setattr(DocumentService, "update", staticmethod(fake_update))
        db.rollback()

        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            response = client.patch("/documents/1", json={"number": "X"})
        finally:
            event.remove(engine, "before_cursor_execute", record)

        assert response.status_code == 404
        assert calls == [(1, {"number": "X"})]
        assert statements == []

    def test_the_router_neither_commits_nor_rolls_back(
        self, client, document_type, monkeypatch
    ):
        stub = Document(
            id=1,
            document_type_id=document_type.id,
            number="CERT-1",
            verification_status="pending",
        )
        monkeypatch.setattr(
            DocumentService, "update", staticmethod(lambda *args, **kwargs: stub)
        )

        def forbidden(*args, **kwargs):
            raise AssertionError("the update route must not end a transaction")

        monkeypatch.setattr(Session, "commit", forbidden)
        monkeypatch.setattr(Session, "rollback", forbidden)

        response = client.patch("/documents/1", json={"number": "X"})

        assert response.status_code == 200
        assert response.json()["number"] == "CERT-1"


class TestOpenApiAndNeighbours:
    def test_patch_is_documented(self):
        paths = app.openapi()["paths"]
        assert "patch" in paths["/documents/{document_id}"]

    def test_patch_returns_document_out(self):
        operation = app.openapi()["paths"]["/documents/{document_id}"]["patch"]
        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/DocumentOut"}

    def test_no_put_for_documents(self):
        paths = app.openapi()["paths"]
        assert "put" not in paths["/documents/{document_id}"]

    def test_no_delete_for_documents(self):
        paths = app.openapi()["paths"]
        assert "delete" not in paths["/documents"]
        assert "delete" not in paths["/documents/{document_id}"]

    def test_create_and_read_still_work(self, client, document_type):
        created = client.post(
            "/documents",
            json={"document_type_id": document_type.id, "number": "CERT-1"},
        )
        assert created.status_code == 201
        document_id = created.json()["id"]
        assert client.get("/documents").status_code == 200
        assert client.get(f"/documents/{document_id}").status_code == 200

    def test_file_routes_are_still_declared(self):
        paths = app.openapi()["paths"]
        assert set(paths["/documents/{document_id}/files"]) == {"get", "post"}
        assert set(paths["/documents/{document_id}/files/{file_id}"]) == {
            "get",
            "delete",
        }
