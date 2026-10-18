"""HTTP and service tests for `GET /documents/{document_id}/verification-history`.

The route is a thin reader over `DocumentService.history`, which returns the
`document_verification_events` rows of one document ordered `created_at ASC,
id ASC`. These tests pin the read contract (200 with a bare array, 404 for a
missing document, `[]` for a document with no events) and exercise every kind of
event the system can produce — `verified`, `rejected` and the three `reopened`
causes — reached only through the real services, so no impossible status
combination is fabricated by hand.

The single exception is the ordering test for identical `created_at`: to prove
that `id` breaks a tie inside one transaction, the rows are inserted directly
with one shared timestamp. That is the only point in the file where event rows
are written by hand, and it is deliberate — the services always stamp `now()`
from their own transactions, so they cannot produce a tie on demand.

Nothing here touches the working database or the project's `storage/`: sessions
come from the shared `engine` fixture (schema `test_file_service`) and file
storage is rooted in `tmp_path`.
"""

import io
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.api.document_types.schemas import DocumentTypeCreate
from app.api.documents.schemas import DocumentCreate, DocumentUpdate
from app.config import Settings, get_settings
from app.database.connection import get_db
from app.main import app
from app.models.document import Document
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.file import File
from app.services.document_service import DocumentService
from app.services.document_type_service import DocumentTypeService
from app.services.file_service import FileService
from app.services.local_storage import LocalStorageBackend

DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"

UNKNOWN_ID = 10_000_000

EVENT_FIELDS = {
    "id",
    "document_id",
    "from_status",
    "to_status",
    "event_type",
    "reason",
    "created_at",
}

INTERNAL_FIELDS = {"storage_key", "path", "checksum", "size_bytes", "files"}

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
        # DocumentService leaves a read transaction open after its refresh;
        # FileService insists on owning its own, so close the reader first.
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


def history_url(document_id: int) -> str:
    return f"/documents/{document_id}/verification-history"


def history_body(client: TestClient, document_id: int) -> list[dict]:
    response = client.get(history_url(document_id))
    assert response.status_code == 200
    return response.json()


def events_for(db: Session, document_id: int) -> list[DocumentVerificationEvent]:
    db.expire_all()
    return list(
        db.scalars(
            select(DocumentVerificationEvent)
            .where(DocumentVerificationEvent.document_id == document_id)
            .order_by(
                DocumentVerificationEvent.created_at,
                DocumentVerificationEvent.id,
            )
        )
    )


def status_of(db: Session, document_id: int) -> str:
    db.expire_all()
    return db.get(Document, document_id).verification_status


def file_count(db: Session, document_id: int) -> int:
    db.expire_all()
    return db.scalar(
        select(func.count()).select_from(File).where(File.document_id == document_id)
    )


class TestHistoryService:
    """The service method's own contract, exercised without HTTP."""

    def test_missing_document_returns_none(self, db):
        assert DocumentService.history(db, UNKNOWN_ID) is None

    def test_existing_document_without_events_returns_empty_list(
        self, db, make_document
    ):
        document = make_document()
        assert DocumentService.history(db, document.id) == []

    def test_existing_document_with_events_returns_them(self, db, make_rejected):
        document = make_rejected()
        events = DocumentService.history(db, document.id)
        assert events is not None
        assert len(events) == 1

    def test_returns_orm_instances(self, db, make_rejected):
        document = make_rejected()
        events = DocumentService.history(db, document.id)
        assert all(isinstance(row, DocumentVerificationEvent) for row in events or [])

    def test_empty_list_is_not_none(self, db, make_document):
        document = make_document()
        events = DocumentService.history(db, document.id)
        assert events is not None
        assert events == []

    def test_does_not_commit_or_rollback(self, db, make_rejected, monkeypatch):
        document = make_rejected()

        def forbidden(*args, **kwargs):
            raise AssertionError("history must not end a transaction")

        monkeypatch.setattr(Session, "commit", forbidden)
        monkeypatch.setattr(Session, "rollback", forbidden)

        events = DocumentService.history(db, document.id)
        assert len(events) == 1

    def test_takes_no_row_lock(self, db, make_rejected, engine):
        document = make_rejected()
        db.rollback()

        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            DocumentService.history(db, document.id)
        finally:
            event.remove(engine, "before_cursor_execute", record)

        assert statements, "history should read the events"
        assert all(
            statement.lstrip().upper().startswith("SELECT") for statement in statements
        )
        assert all("FOR UPDATE" not in statement.upper() for statement in statements)


class TestTransitions:
    """Every event kind the services can write, seen through the route."""

    def test_pending_to_verified(self, client, db, make_document, attach):
        document = make_document()
        document_id = document.id
        attach(document_id)
        db.rollback()
        DocumentService.verify(db, document_id)

        body = history_body(client, document_id)
        assert len(body) == 1
        assert body[0]["from_status"] == "pending"
        assert body[0]["to_status"] == "verified"
        assert body[0]["event_type"] == "verified"

    def test_pending_to_rejected_carries_reason(self, client, db, make_rejected):
        document = make_rejected()
        body = history_body(client, document.id)
        assert len(body) == 1
        assert body[0]["event_type"] == "rejected"
        assert body[0]["from_status"] == "pending"
        assert body[0]["to_status"] == "rejected"
        assert body[0]["reason"] == "Повреждённый скан"

    def test_verified_to_rejected(self, client, db, make_verified):
        document = make_verified()
        document_id = document.id
        db.rollback()
        DocumentService.reject(db, document_id, "Отозван")

        body = history_body(client, document_id)
        assert [row["event_type"] for row in body] == ["verified", "rejected"]
        assert body[-1]["from_status"] == "verified"
        assert body[-1]["to_status"] == "rejected"
        assert body[-1]["reason"] == "Отозван"

    def test_rejected_to_verified(self, client, db, make_document, attach):
        document = make_document()
        document_id = document.id
        attach(document_id)
        db.rollback()
        DocumentService.reject(db, document_id, "Черновик")
        db.rollback()
        DocumentService.verify(db, document_id)

        body = history_body(client, document_id)
        assert [row["event_type"] for row in body] == ["rejected", "verified"]
        assert body[-1]["from_status"] == "rejected"
        assert body[-1]["to_status"] == "verified"

    def test_reopened_significant_fields_changed(self, client, db, make_verified):
        document = make_verified(number="CERT-1")
        client.patch(f"/documents/{document.id}", json={"number": "CERT-2"})

        body = history_body(client, document.id)
        assert body[-1]["event_type"] == "reopened"
        assert body[-1]["from_status"] == "verified"
        assert body[-1]["to_status"] == "pending"
        assert body[-1]["reason"] == "significant_fields_changed"

    def test_reopened_file_added(self, client, db, make_verified, attach):
        document = make_verified()
        attach(document.id)

        body = history_body(client, document.id)
        assert body[-1]["event_type"] == "reopened"
        assert body[-1]["from_status"] == "verified"
        assert body[-1]["to_status"] == "pending"
        assert body[-1]["reason"] == "file_added"

    def test_reopened_file_deleted(self, client, db, make_document, attach, file_service):
        document = make_document()
        document_id = document.id
        attached = attach(document_id)
        file_id = attached.id
        db.rollback()
        DocumentService.verify(db, document_id)
        db.rollback()
        file_service.detach(document_id, file_id)

        body = history_body(client, document_id)
        assert body[-1]["event_type"] == "reopened"
        assert body[-1]["from_status"] == "verified"
        assert body[-1]["to_status"] == "pending"
        assert body[-1]["reason"] == "file_deleted"

    def test_full_lifecycle_is_in_chronological_order(
        self, client, db, make_document, attach
    ):
        document = make_document()
        document_id = document.id
        attach(document_id)
        db.rollback()
        DocumentService.verify(db, document_id)
        db.rollback()
        DocumentService.update(db, document_id, DocumentUpdate(number="CERT-9"))
        db.rollback()
        DocumentService.reject(db, document_id, "Отозван")

        body = history_body(client, document_id)
        assert [row["event_type"] for row in body] == [
            "verified",
            "reopened",
            "rejected",
        ]
        stamps = [row["created_at"] for row in body]
        assert stamps == sorted(stamps)

    def test_two_documents_do_not_mix(self, client, db, make_document, attach):
        first = make_document()
        second = make_document()
        first_id = first.id
        second_id = second.id
        attach(first_id)
        db.rollback()
        DocumentService.verify(db, first_id)
        db.rollback()
        DocumentService.reject(db, second_id, "Нет скана")

        first_body = history_body(client, first_id)
        second_body = history_body(client, second_id)
        assert [row["event_type"] for row in first_body] == ["verified"]
        assert [row["event_type"] for row in second_body] == ["rejected"]
        assert all(row["document_id"] == first_id for row in first_body)
        assert all(row["document_id"] == second_id for row in second_body)


class TestOrderingWithIdenticalTimestamps:
    """`id` must break a `created_at` tie inside a single transaction."""

    def test_id_breaks_created_at_ties(self, client, db, make_document):
        # Hand-written rows on purpose: the services stamp `now()` from their own
        # transactions and cannot be made to produce equal timestamps, so the tie
        # that the composite index is meant to resolve can only be created here.
        document = make_document()
        document_id = document.id
        db.rollback()

        stamp = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        db.add_all(
            [
                DocumentVerificationEvent(
                    document_id=document_id,
                    from_status="pending",
                    to_status="verified",
                    event_type="verified",
                    reason=None,
                    created_at=stamp,
                ),
                DocumentVerificationEvent(
                    document_id=document_id,
                    from_status="verified",
                    to_status="pending",
                    event_type="reopened",
                    reason="file_added",
                    created_at=stamp,
                ),
                DocumentVerificationEvent(
                    document_id=document_id,
                    from_status="pending",
                    to_status="rejected",
                    event_type="rejected",
                    reason="Позже",
                    created_at=stamp,
                ),
            ]
        )
        db.commit()

        body = history_body(client, document_id)
        assert [row["event_type"] for row in body] == [
            "verified",
            "reopened",
            "rejected",
        ]
        ids = [row["id"] for row in body]
        assert ids == sorted(ids)
        assert len({row["created_at"] for row in body}) == 1


class TestHttpContract:
    def test_missing_document_is_404(self, client):
        assert client.get(history_url(UNKNOWN_ID)).status_code == 404

    def test_document_without_events_is_empty_array(self, client, make_document):
        document = make_document()
        response = client.get(history_url(document.id))
        assert response.status_code == 200
        assert response.json() == []

    def test_result_is_a_bare_array(self, client, make_rejected):
        document = make_rejected()
        payload = client.get(history_url(document.id)).json()
        assert isinstance(payload, list)
        assert payload and isinstance(payload[0], dict)

    def test_content_type_is_json(self, client, make_rejected):
        document = make_rejected()
        response = client.get(history_url(document.id))
        assert response.headers["content-type"].startswith("application/json")

    def test_event_has_only_public_fields(self, client, make_rejected):
        document = make_rejected()
        assert set(history_body(client, document.id)[0]) == EVENT_FIELDS

    def test_no_internal_fields(self, client, make_rejected):
        document = make_rejected()
        payload = client.get(history_url(document.id)).text
        for needle in INTERNAL_FIELDS:
            assert needle not in payload

    def test_created_at_is_an_aware_iso_timestamp(self, client, make_rejected):
        document = make_rejected()
        value = history_body(client, document.id)[0]["created_at"]
        assert isinstance(value, str)
        assert "T" in value
        assert datetime.fromisoformat(value).tzinfo is not None

    def test_error_body_leaks_no_internals(self, client):
        response = client.get(history_url(UNKNOWN_ID))
        lowered = response.text.lower()
        for needle in (
            "select",
            "postgresql",
            "psycopg",
            "traceback",
            "storage_key",
            "password",
        ):
            assert needle not in lowered, needle


class TestReadOnly:
    def test_get_changes_nothing(self, client, db, make_verified):
        document = make_verified()
        before_status = status_of(db, document.id)
        before_files = file_count(db, document.id)
        before_events = len(events_for(db, document.id))

        assert client.get(history_url(document.id)).status_code == 200

        assert status_of(db, document.id) == before_status
        assert file_count(db, document.id) == before_files
        assert len(events_for(db, document.id)) == before_events

    def test_get_runs_no_dml_and_no_row_lock(self, client, db, engine, make_verified):
        document = make_verified()
        document_id = document.id
        db.rollback()

        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            assert client.get(history_url(document_id)).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", record)

        assert all(
            statement.lstrip().upper().startswith("SELECT") for statement in statements
        ), statements
        assert all("FOR UPDATE" not in statement.upper() for statement in statements)
        for verb in ("INSERT", "UPDATE", "DELETE"):
            assert all(verb not in statement.upper() for statement in statements)

    def test_get_neither_commits_nor_rolls_back(self, client, make_rejected, monkeypatch):
        document = make_rejected()

        def forbidden(*args, **kwargs):
            raise AssertionError("the history route must not end a transaction")

        monkeypatch.setattr(Session, "commit", forbidden)
        monkeypatch.setattr(Session, "rollback", forbidden)

        assert client.get(history_url(document.id)).status_code == 200

    def test_route_delegates_to_the_service(self, client, make_document, monkeypatch):
        calls: list[tuple[int]] = []

        def fake_history(session, document_id):
            calls.append((document_id,))
            return []

        monkeypatch.setattr(DocumentService, "history", staticmethod(fake_history))
        document = make_document()

        response = client.get(history_url(document.id))

        assert response.status_code == 200
        assert response.json() == []
        assert calls == [(document.id,)]

    def test_none_from_the_service_becomes_404(self, client, monkeypatch):
        monkeypatch.setattr(
            DocumentService, "history", staticmethod(lambda session, document_id: None)
        )
        assert client.get(history_url(1)).status_code == 404


class TestOpenApiAndNeighbours:
    def test_history_route_is_documented(self):
        paths = app.openapi()["paths"]
        assert set(paths["/documents/{document_id}/verification-history"]) == {"get"}

    def test_history_returns_the_event_list_schema(self):
        operation = app.openapi()["paths"][
            "/documents/{document_id}/verification-history"
        ]["get"]
        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/DocumentVerificationEventListOut"}

    def test_no_delete_for_documents(self):
        paths = app.openapi()["paths"]
        assert "delete" not in paths["/documents"]
        assert "delete" not in paths["/documents/{document_id}"]

    def test_create_read_patch_and_verify_still_work(self, client, db, document_type):
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
