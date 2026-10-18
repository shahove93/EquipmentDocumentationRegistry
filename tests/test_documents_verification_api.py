"""HTTP tests for `POST /documents/{document_id}/verification`.

The route is a dispatcher over `DocumentService.verify` and
`DocumentService.reject`. These tests pin the HTTP contract and the lifecycle
rules those methods own: a confirmation needs an attachment, a rejection needs
a reason, both verdicts are idempotent, and each real transition writes exactly
one history event. Nothing touches the working database or the project's
`storage/` — sessions come from the shared `engine` fixture (schema
`test_file_service`) and file storage is rooted in `tmp_path`.
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


@pytest.fixture
def make_rejected_with_file(db, make_document, attach):
    """A `rejected` document that already carries an attachment.

    The file is attached while the document is still `pending`, so ADR-009 adds
    no `reopened` event; the rejection then records a single `rejected` event.
    This is the only honest way to reach `rejected → verified` directly, since
    attaching a file to an already decided document would reopen it first.
    """

    def _make(**overrides) -> Document:
        document = make_document(**overrides)
        attach(document.id)
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


def count_events(db, document_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(DocumentVerificationEvent)
        .where(DocumentVerificationEvent.document_id == document_id)
    )


def status_of(db, document_id: int) -> str:
    db.expire_all()
    return db.get(Document, document_id).verification_status


def verify_url(document_id: int) -> str:
    return f"/documents/{document_id}/verification"


class TestVerify:
    def test_pending_with_file_becomes_verified(self, client, make_document, attach):
        document = make_document()
        attach(document.id)
        response = client.post(verify_url(document.id), json={"decision": "verified"})
        assert response.status_code == 200
        assert response.json()["verification_status"] == "verified"

    def test_pending_with_file_writes_one_verified_event(
        self, client, db, make_document, attach
    ):
        document = make_document()
        attach(document.id)
        client.post(verify_url(document.id), json={"decision": "verified"})
        events = events_for(db, document.id)
        assert len(events) == 1
        assert events[0].from_status == "pending"
        assert events[0].to_status == "verified"
        assert events[0].event_type == "verified"

    def test_reason_is_stored_when_given(self, client, db, make_document, attach):
        document = make_document()
        attach(document.id)
        client.post(
            verify_url(document.id),
            json={"decision": "verified", "reason": "Проверено"},
        )
        assert events_for(db, document.id)[0].reason == "Проверено"

    def test_reason_is_none_when_omitted(self, client, db, make_document, attach):
        document = make_document()
        attach(document.id)
        client.post(verify_url(document.id), json={"decision": "verified"})
        assert events_for(db, document.id)[0].reason is None

    def test_explicit_null_reason_is_accepted_for_verification(
        self, client, make_document, attach
    ):
        document = make_document()
        attach(document.id)
        response = client.post(
            verify_url(document.id), json={"decision": "verified", "reason": None}
        )
        assert response.status_code == 200

    def test_reason_is_passed_through_verbatim(self, client, db, make_document, attach):
        document = make_document()
        attach(document.id)
        client.post(
            verify_url(document.id),
            json={"decision": "verified", "reason": "  spaced  "},
        )
        assert events_for(db, document.id)[0].reason == "  spaced  "

    def test_pending_without_file_is_422(self, client, make_document):
        document = make_document()
        response = client.post(verify_url(document.id), json={"decision": "verified"})
        assert response.status_code == 422

    def test_pending_without_file_keeps_status(self, client, db, make_document):
        document = make_document()
        client.post(verify_url(document.id), json={"decision": "verified"})
        assert status_of(db, document.id) == "pending"

    def test_pending_without_file_writes_no_event(self, client, db, make_document):
        document = make_document()
        client.post(verify_url(document.id), json={"decision": "verified"})
        assert count_events(db, document.id) == 0

    def test_rejected_to_verified_directly(
        self, client, db, make_rejected_with_file
    ):
        document = make_rejected_with_file()
        response = client.post(verify_url(document.id), json={"decision": "verified"})
        assert response.status_code == 200
        assert response.json()["verification_status"] == "verified"
        assert status_of(db, document.id) == "verified"

    def test_rejected_to_verified_writes_one_event(
        self, client, db, make_rejected_with_file
    ):
        document = make_rejected_with_file()
        client.post(verify_url(document.id), json={"decision": "verified"})
        events = events_for(db, document.id)
        assert len(events) == 2  # rejected, then verified
        assert events[-1].from_status == "rejected"
        assert events[-1].to_status == "verified"
        assert events[-1].event_type == "verified"

    def test_repeated_verify_writes_no_new_event(self, client, db, make_verified):
        document = make_verified()
        before = count_events(db, document.id)
        response = client.post(verify_url(document.id), json={"decision": "verified"})
        assert response.status_code == 200
        assert response.json()["verification_status"] == "verified"
        assert count_events(db, document.id) == before

    def test_unknown_document_is_404(self, client):
        response = client.post(verify_url(UNKNOWN_ID), json={"decision": "verified"})
        assert response.status_code == 404

    def test_body_is_document_out(self, client, make_document, attach):
        document = make_document()
        attach(document.id)
        response = client.post(verify_url(document.id), json={"decision": "verified"})
        assert set(response.json()) == DOCUMENT_FIELDS

    def test_content_type_is_json(self, client, make_document, attach):
        document = make_document()
        attach(document.id)
        response = client.post(verify_url(document.id), json={"decision": "verified"})
        assert response.headers["content-type"].startswith("application/json")

    def test_exposes_no_internal_fields(self, client, make_document, attach):
        document = make_document()
        attach(document.id)
        response = client.post(verify_url(document.id), json={"decision": "verified"})
        assert set(response.json()).isdisjoint(INTERNAL_FIELDS)
        assert "storage_key" not in response.text

    def test_error_body_leaks_no_internals(self, client, make_document):
        document = make_document()
        response = client.post(verify_url(document.id), json={"decision": "verified"})
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


class TestReject:
    def test_pending_becomes_rejected_with_reason(self, client, db, make_document):
        document = make_document()
        response = client.post(
            verify_url(document.id),
            json={"decision": "rejected", "reason": "Нет скана"},
        )
        assert response.status_code == 200
        assert response.json()["verification_status"] == "rejected"

    def test_rejected_event_fields(self, client, db, make_document):
        document = make_document()
        client.post(
            verify_url(document.id),
            json={"decision": "rejected", "reason": "Нет скана"},
        )
        events = events_for(db, document.id)
        assert len(events) == 1
        assert events[0].from_status == "pending"
        assert events[0].to_status == "rejected"
        assert events[0].event_type == "rejected"
        assert events[0].reason == "Нет скана"

    def test_reason_is_passed_through_verbatim(self, client, db, make_document):
        document = make_document()
        client.post(
            verify_url(document.id),
            json={"decision": "rejected", "reason": "  spaced reason  "},
        )
        assert events_for(db, document.id)[0].reason == "  spaced reason  "

    def test_verified_to_rejected_directly(self, client, db, make_verified):
        document = make_verified()
        response = client.post(
            verify_url(document.id),
            json={"decision": "rejected", "reason": "Отозван"},
        )
        assert response.status_code == 200
        assert response.json()["verification_status"] == "rejected"
        assert status_of(db, document.id) == "rejected"

    def test_verified_to_rejected_writes_one_event(self, client, db, make_verified):
        document = make_verified()
        before = count_events(db, document.id)
        client.post(
            verify_url(document.id),
            json={"decision": "rejected", "reason": "Отозван"},
        )
        assert count_events(db, document.id) == before + 1
        assert events_for(db, document.id)[-1].from_status == "verified"

    def test_missing_reason_is_422(self, client, make_document):
        document = make_document()
        response = client.post(verify_url(document.id), json={"decision": "rejected"})
        assert response.status_code == 422

    def test_empty_reason_is_422(self, client, make_document):
        document = make_document()
        response = client.post(
            verify_url(document.id), json={"decision": "rejected", "reason": ""}
        )
        assert response.status_code == 422

    def test_whitespace_reason_is_422(self, client, make_document):
        document = make_document()
        response = client.post(
            verify_url(document.id), json={"decision": "rejected", "reason": "   "}
        )
        assert response.status_code == 422

    def test_null_reason_is_422(self, client, make_document):
        document = make_document()
        response = client.post(
            verify_url(document.id), json={"decision": "rejected", "reason": None}
        )
        assert response.status_code == 422

    def test_rejection_without_reason_changes_nothing(self, client, db, make_document):
        document = make_document()
        client.post(verify_url(document.id), json={"decision": "rejected"})
        assert status_of(db, document.id) == "pending"
        assert count_events(db, document.id) == 0

    def test_unknown_document_is_404(self, client):
        response = client.post(
            verify_url(UNKNOWN_ID),
            json={"decision": "rejected", "reason": "Нет скана"},
        )
        assert response.status_code == 404

    def test_repeated_reject_writes_no_new_event(self, client, db, make_rejected):
        document = make_rejected()
        before = count_events(db, document.id)
        response = client.post(
            verify_url(document.id),
            json={"decision": "rejected", "reason": "Другая причина"},
        )
        assert response.status_code == 200
        assert count_events(db, document.id) == before

    def test_repeated_reject_keeps_the_first_reason(self, client, db, make_rejected):
        document = make_rejected()
        client.post(
            verify_url(document.id),
            json={"decision": "rejected", "reason": "Другая причина"},
        )
        events = events_for(db, document.id)
        assert len(events) == 1
        assert events[0].reason == "Повреждённый скан"

    def test_body_is_document_out(self, client, make_document):
        document = make_document()
        response = client.post(
            verify_url(document.id),
            json={"decision": "rejected", "reason": "Нет скана"},
        )
        assert set(response.json()) == DOCUMENT_FIELDS


class TestRequestValidation:
    def test_missing_decision_is_422(self, client, make_document):
        document = make_document()
        response = client.post(verify_url(document.id), json={"reason": "x"})
        assert response.status_code == 422

    def test_invalid_decision_is_422(self, client, make_document):
        document = make_document()
        response = client.post(
            verify_url(document.id), json={"decision": "pending"}
        )
        assert response.status_code == 422

    def test_numeric_decision_is_422(self, client, make_document):
        document = make_document()
        response = client.post(verify_url(document.id), json={"decision": 1})
        assert response.status_code == 422

    def test_extra_field_is_422(self, client, make_document):
        document = make_document()
        response = client.post(
            verify_url(document.id),
            json={"decision": "verified", "extra": "x"},
        )
        assert response.status_code == 422

    def test_verification_status_field_is_422(self, client, make_document):
        document = make_document()
        response = client.post(
            verify_url(document.id),
            json={"decision": "verified", "verification_status": "verified"},
        )
        assert response.status_code == 422

    def test_non_string_reason_is_422(self, client, make_document):
        document = make_document()
        response = client.post(
            verify_url(document.id), json={"decision": "rejected", "reason": 123}
        )
        assert response.status_code == 422

    def test_object_reason_is_422(self, client, make_document):
        document = make_document()
        response = client.post(
            verify_url(document.id),
            json={"decision": "rejected", "reason": {"text": "x"}},
        )
        assert response.status_code == 422

    def test_empty_body_is_422(self, client, make_document):
        document = make_document()
        assert client.post(verify_url(document.id), json={}).status_code == 422


class TestLifecycle:
    def test_successful_transition_writes_exactly_one_event(
        self, client, db, make_document, attach
    ):
        document = make_document()
        attach(document.id)
        client.post(verify_url(document.id), json={"decision": "verified"})
        assert count_events(db, document.id) == 1

    def test_patch_significant_after_verify_returns_to_pending(
        self, client, db, make_verified
    ):
        document = make_verified(number="CERT-1")
        response = client.patch(
            f"/documents/{document.id}", json={"number": "CERT-2"}
        )
        assert response.json()["verification_status"] == "pending"
        reopened = [e for e in events_for(db, document.id) if e.event_type == "reopened"]
        assert len(reopened) == 1
        assert reopened[0].reason == "significant_fields_changed"

    def test_other_documents_are_not_touched(
        self, client, db, make_document, attach
    ):
        target = make_document()
        other = make_document()
        attach(target.id)
        client.post(verify_url(target.id), json={"decision": "verified"})
        assert status_of(db, target.id) == "verified"
        assert status_of(db, other.id) == "pending"
        assert count_events(db, other.id) == 0


class TestConflict:
    def test_uncommitted_changes_are_409(self, client, db, make_document):
        document = make_document()
        document_id = document.id
        db.rollback()
        dirty = db.get(Document, document_id)
        dirty.number = "DIRTY"
        try:
            response = client.post(
                verify_url(document_id), json={"decision": "verified"}
            )
            assert response.status_code == 409
        finally:
            db.rollback()


class TestRouterBoundaries:
    def test_the_router_runs_no_sql_of_its_own(
        self, client, db, engine, monkeypatch
    ):
        calls: list[tuple[int, str | None]] = []

        def fake_verify(session, document_id, reason=None):
            calls.append((document_id, reason))
            return None

        monkeypatch.setattr(DocumentService, "verify", staticmethod(fake_verify))
        db.rollback()

        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            response = client.post(
                verify_url(1), json={"decision": "verified"}
            )
        finally:
            event.remove(engine, "before_cursor_execute", record)

        assert response.status_code == 404
        assert calls == [(1, None)]
        assert statements == []

    def test_the_router_neither_commits_nor_rolls_back(
        self, client, document_type, monkeypatch
    ):
        stub = Document(
            id=1,
            document_type_id=document_type.id,
            number="CERT-1",
            verification_status="verified",
        )
        monkeypatch.setattr(
            DocumentService, "verify", staticmethod(lambda *a, **k: stub)
        )

        def forbidden(*args, **kwargs):
            raise AssertionError("the verification route must not end a transaction")

        monkeypatch.setattr(Session, "commit", forbidden)
        monkeypatch.setattr(Session, "rollback", forbidden)

        response = client.post(verify_url(1), json={"decision": "verified"})

        assert response.status_code == 200
        assert response.json()["verification_status"] == "verified"

    def test_the_router_delegates_both_decisions(
        self, client, document_type, monkeypatch
    ):
        calls: list[tuple[str, int, str | None]] = []
        stub = Document(
            id=1,
            document_type_id=document_type.id,
            number="CERT-1",
            verification_status="verified",
        )

        def fake_verify(session, document_id, reason=None):
            calls.append(("verify", document_id, reason))
            return stub

        def fake_reject(session, document_id, reason):
            calls.append(("reject", document_id, reason))
            return stub

        monkeypatch.setattr(DocumentService, "verify", staticmethod(fake_verify))
        monkeypatch.setattr(DocumentService, "reject", staticmethod(fake_reject))

        client.post(
            verify_url(5), json={"decision": "verified", "reason": "ok"}
        )
        client.post(
            verify_url(6), json={"decision": "rejected", "reason": "bad"}
        )

        assert calls == [("verify", 5, "ok"), ("reject", 6, "bad")]


class TestOpenApiAndNeighbours:
    def test_verification_route_is_documented(self):
        paths = app.openapi()["paths"]
        assert set(paths["/documents/{document_id}/verification"]) == {"post"}

    def test_verification_returns_document_out(self):
        operation = app.openapi()["paths"]["/documents/{document_id}/verification"][
            "post"
        ]
        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/DocumentOut"}

    def test_no_get_verification(self):
        paths = app.openapi()["paths"]
        assert "get" not in paths["/documents/{document_id}/verification"]

    def test_verification_history_route_is_declared(self):
        paths = app.openapi()["paths"]
        assert set(paths["/documents/{document_id}/verification-history"]) == {"get"}

    def test_no_delete_for_documents(self):
        paths = app.openapi()["paths"]
        assert "delete" not in paths["/documents"]
        assert "delete" not in paths["/documents/{document_id}"]

    def test_create_read_and_patch_still_work(self, client, document_type):
        created = client.post(
            "/documents",
            json={"document_type_id": document_type.id, "number": "CERT-1"},
        )
        assert created.status_code == 201
        document_id = created.json()["id"]
        assert client.get("/documents").status_code == 200
        assert client.get(f"/documents/{document_id}").status_code == 200
        assert client.patch(
            f"/documents/{document_id}", json={"notes": "x"}
        ).status_code == 200

    def test_file_routes_still_declared(self):
        paths = app.openapi()["paths"]
        assert set(paths["/documents/{document_id}/files"]) == {"get", "post"}
        assert set(paths["/documents/{document_id}/files/{file_id}"]) == {
            "get",
            "delete",
        }
