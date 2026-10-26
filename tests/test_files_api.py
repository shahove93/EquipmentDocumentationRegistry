import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.document_types.schemas import DocumentTypeCreate
from app.api.documents.schemas import DocumentCreate
from app.config import Settings, get_settings
from app.database.connection import get_db
from app.main import app
from app.models.document import Document
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.file import File
from app.services.document_service import DocumentService
from app.services.document_type_service import DocumentTypeService

DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"
UPLOADED_AT = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
SHA256 = "c" * 64
STORAGE_KEY_PREFIX = "attachments/"
_MISSING = object()

PUBLIC_FIELDS = {
    "id",
    "document_id",
    "original_filename",
    "mime_type",
    "size_bytes",
    "sha256",
    "uploaded_at",
}


@pytest.fixture
def client(db, tmp_path):
    """HTTP client whose sessions point at the isolated test schema.

    `get_db` is replaced with the same session the test uses, and `get_settings`
    with storage rooted in `tmp_path`, so nothing reaches the working database or
    the project's `storage/` directory. Both overrides that may already exist are
    saved and restored, so a failing test cannot leak them.
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
def make_document(db):
    def _make(status: str | None = None) -> Document:
        document_type = DocumentTypeService.create(
            db, DocumentTypeCreate(name=f"Type {uuid.uuid4().hex[:12]}")
        )
        document = DocumentService.create(
            db,
            DocumentCreate(
                document_type_id=document_type.id,
                number=f"DOC-{uuid.uuid4().hex[:8]}",
            ),
        )
        if status is not None:
            document.verification_status = status
            db.commit()
        return document

    return _make


@pytest.fixture
def make_file(db):
    def _make(document_id: int, **overrides: object) -> File:
        values: dict[str, object] = {
            "document_id": document_id,
            "original_filename": "scan.pdf",
            "storage_key": f"{STORAGE_KEY_PREFIX}{uuid.uuid4().hex}",
            "mime_type": "application/pdf",
            "size_bytes": 2048,
            "sha256": SHA256,
            "uploaded_at": UPLOADED_AT,
        }
        values.update(overrides)
        file = File(**values)  # type: ignore[arg-type]
        db.add(file)
        db.commit()
        db.refresh(file)
        return file

    return _make


class TestListDocumentFiles:
    def test_returns_200_for_a_document_with_files(
        self, client, make_document, make_file
    ):
        document = make_document()
        make_file(document.id)
        response = client.get(f"/documents/{document.id}/files")
        assert response.status_code == 200

    def test_content_type_is_json(self, client, make_document, make_file):
        document = make_document()
        make_file(document.id)
        response = client.get(f"/documents/{document.id}/files")
        assert response.headers["content-type"].startswith("application/json")

    def test_body_is_an_array_of_the_document_files(
        self, client, make_document, make_file
    ):
        document = make_document()
        first = make_file(document.id)
        second = make_file(document.id)
        body = client.get(f"/documents/{document.id}/files").json()
        assert isinstance(body, list)
        assert [item["id"] for item in body] == [first.id, second.id]

    def test_empty_document_returns_an_empty_list(self, client, make_document):
        document = make_document()
        response = client.get(f"/documents/{document.id}/files")
        assert response.status_code == 200
        assert response.json() == []

    def test_unknown_document_returns_404(self, client):
        assert client.get("/documents/999999/files").status_code == 404

    def test_unknown_document_is_not_reported_as_an_empty_list(self, client):
        response = client.get("/documents/999999/files")
        assert response.json() != []

    def test_only_the_requested_document_files_are_returned(
        self, client, make_document, make_file
    ):
        mine = make_document()
        other = make_document()
        wanted = make_file(mine.id)
        make_file(other.id)
        make_file(other.id)
        body = client.get(f"/documents/{mine.id}/files").json()
        assert [item["id"] for item in body] == [wanted.id]

    def test_order_is_by_ascending_id(self, client, make_document, make_file):
        document = make_document()
        created = [make_file(document.id).id for _ in range(5)]
        body = client.get(f"/documents/{document.id}/files").json()
        ids = [item["id"] for item in body]
        assert ids == sorted(ids)
        assert ids == created


class TestGetDocumentFile:
    def test_returns_200_for_an_existing_file(self, client, make_document, make_file):
        document = make_document()
        file = make_file(document.id)
        response = client.get(f"/documents/{document.id}/files/{file.id}")
        assert response.status_code == 200

    def test_returns_the_file_metadata(self, client, make_document, make_file):
        document = make_document()
        file = make_file(
            document.id,
            original_filename="passport.pdf",
            mime_type="application/pdf",
            size_bytes=4096,
        )
        body = client.get(f"/documents/{document.id}/files/{file.id}").json()
        assert body["id"] == file.id
        assert body["document_id"] == document.id
        assert body["original_filename"] == "passport.pdf"
        assert body["mime_type"] == "application/pdf"
        assert body["size_bytes"] == 4096
        assert body["sha256"] == SHA256

    def test_unknown_file_returns_404(self, client, make_document):
        document = make_document()
        assert client.get(f"/documents/{document.id}/files/999999").status_code == 404

    def test_file_of_another_document_returns_404(
        self, client, make_document, make_file
    ):
        mine = make_document()
        other = make_document()
        foreign = make_file(other.id)
        response = client.get(f"/documents/{mine.id}/files/{foreign.id}")
        assert response.status_code == 404

    def test_unknown_document_returns_404(self, client, make_document, make_file):
        document = make_document()
        file = make_file(document.id)
        assert client.get(f"/documents/999999/files/{file.id}").status_code == 404

    def test_a_foreign_file_is_not_distinguishable_from_a_missing_one(
        self, client, make_document, make_file
    ):
        mine = make_document()
        other = make_document()
        foreign = make_file(other.id)
        foreign_response = client.get(f"/documents/{mine.id}/files/{foreign.id}")
        missing_response = client.get(f"/documents/{mine.id}/files/999999")
        assert foreign_response.status_code == missing_response.status_code == 404
        # Both answers are the same template and name only what the caller
        # already put in the path. The ids differ because the caller asked about
        # different ids; what matters is that neither answer carries anything
        # else — in particular, the foreign answer never hints that the file
        # exists under `other`.
        assert foreign_response.json() == {
            "detail": f"File {foreign.id} not found for document {mine.id}"
        }
        assert missing_response.json() == {
            "detail": f"File 999999 not found for document {mine.id}"
        }
        assert set(foreign_response.json()) == {"detail"}
        assert set(missing_response.json()) == {"detail"}

    def test_a_foreign_file_does_not_disclose_the_owning_document(
        self, client, make_document, make_file
    ):
        mine = make_document()
        other = make_document()
        foreign = make_file(other.id)
        body = client.get(f"/documents/{mine.id}/files/{foreign.id}").json()
        assert "document_id" not in body
        assert "storage_key" not in body
        assert foreign.storage_key not in str(body)


class TestNoInternalFieldsLeak:
    def test_list_item_exposes_exactly_the_public_fields(
        self, client, make_document, make_file
    ):
        document = make_document()
        make_file(document.id)
        body = client.get(f"/documents/{document.id}/files").json()
        assert set(body[0]) == PUBLIC_FIELDS

    def test_detail_exposes_exactly_the_public_fields(
        self, client, make_document, make_file
    ):
        document = make_document()
        file = make_file(document.id)
        body = client.get(f"/documents/{document.id}/files/{file.id}").json()
        assert set(body) == PUBLIC_FIELDS

    def test_storage_key_value_never_appears_in_the_list(
        self, client, make_document, make_file
    ):
        document = make_document()
        file = make_file(document.id)
        text = client.get(f"/documents/{document.id}/files").text
        assert "storage_key" not in text
        assert file.storage_key not in text

    def test_storage_key_value_never_appears_in_the_detail(
        self, client, make_document, make_file
    ):
        document = make_document()
        file = make_file(document.id)
        text = client.get(f"/documents/{document.id}/files/{file.id}").text
        assert "storage_key" not in text
        assert file.storage_key not in text

    def test_storage_key_prefix_never_appears(self, client, make_document, make_file):
        document = make_document()
        make_file(document.id)
        text = client.get(f"/documents/{document.id}/files").text
        assert STORAGE_KEY_PREFIX not in text


class TestSerialisation:
    def test_uploaded_at_is_an_iso_datetime(self, client, make_document, make_file):
        document = make_document()
        file = make_file(document.id)
        body = client.get(f"/documents/{document.id}/files/{file.id}").json()
        parsed = datetime.fromisoformat(body["uploaded_at"])
        assert parsed == UPLOADED_AT

    def test_size_bytes_is_an_integer(self, client, make_document, make_file):
        document = make_document()
        file = make_file(document.id, size_bytes=123456)
        body = client.get(f"/documents/{document.id}/files/{file.id}").json()
        assert body["size_bytes"] == 123456
        assert isinstance(body["size_bytes"], int)

    def test_identifiers_are_integers(self, client, make_document, make_file):
        document = make_document()
        file = make_file(document.id)
        body = client.get(f"/documents/{document.id}/files/{file.id}").json()
        assert isinstance(body["id"], int)
        assert isinstance(body["document_id"], int)
        assert isinstance(body["original_filename"], str)
        assert isinstance(body["sha256"], str)


class TestErrorsRevealNothingInternal:
    def test_404_body_has_only_the_document_message(self, client):
        body = client.get("/documents/999999/files").json()
        assert body == {"detail": "Document 999999 not found"}

    def test_404_detail_is_not_a_traceback(self, client, make_document):
        document = make_document()
        text = client.get(f"/documents/{document.id}/files/999999").text
        assert "Traceback" not in text
        assert "sqlalchemy" not in text.lower()
        assert "SELECT" not in text

    def test_missing_file_message_mentions_only_the_requested_ids(
        self, client, make_document
    ):
        document = make_document()
        body = client.get(f"/documents/{document.id}/files/424242").json()
        assert body == {
            "detail": f"File 424242 not found for document {document.id}"
        }


class TestReadOnly:
    def test_listing_does_not_change_status_or_history(
        self, client, db, make_document, make_file
    ):
        document = make_document(status="verified")
        make_file(document.id)
        events_before = db.scalar(
            select(func.count()).select_from(DocumentVerificationEvent)
        )

        client.get(f"/documents/{document.id}/files")

        db.expire_all()
        assert db.get(Document, document.id).verification_status == "verified"
        assert (
            db.scalar(select(func.count()).select_from(DocumentVerificationEvent))
            == events_before
        )

    def test_reading_metadata_does_not_change_status_or_history(
        self, client, db, make_document, make_file
    ):
        document = make_document(status="rejected")
        file = make_file(document.id)

        client.get(f"/documents/{document.id}/files/{file.id}")

        db.expire_all()
        assert db.get(Document, document.id).verification_status == "rejected"
        assert (
            db.scalar(select(func.count()).select_from(DocumentVerificationEvent)) == 0
        )

    def test_no_file_rows_are_added_or_removed(
        self, client, db, make_document, make_file
    ):
        document = make_document()
        make_file(document.id)
        files_before = db.scalar(select(func.count()).select_from(File))

        client.get(f"/documents/{document.id}/files")

        assert db.scalar(select(func.count()).select_from(File)) == files_before


class TestOpenApi:
    @pytest.fixture
    def paths(self):
        return app.openapi()["paths"]

    def test_both_routes_are_documented(self, paths):
        assert "/documents/{document_id}/files" in paths
        assert "/documents/{document_id}/files/{file_id}" in paths

    def test_the_collection_path_offers_get_and_post(self, paths):
        # `GET` lists; `POST` uploads. ADR-009 puts both on the collection.
        assert set(paths["/documents/{document_id}/files"]) == {"get", "post"}

    def test_detail_route_is_get_and_delete(self, paths):
        # TASK-DOC-005T added DELETE next to the metadata GET.
        assert set(paths["/documents/{document_id}/files/{file_id}"]) == {
            "get",
            "delete",
        }

    def test_the_content_route_is_get_only(self, paths):
        # TASK-DOC-005S added the download route; what stays pinned is that it
        # is the only `/content` path and that it reads.
        content_routes = [path for path in paths if path.endswith("/content")]
        assert content_routes == [
            "/documents/{document_id}/files/{file_id}/content"
        ]
        assert set(paths[content_routes[0]]) == {"get"}

    def test_the_write_methods_under_files_are_post_and_delete(self, paths):
        # TASK-DOC-005T added DELETE; there is still no PUT or PATCH.
        write_methods = {"post", "put", "patch", "delete"}
        found = {
            method
            for path in paths
            if "/files" in path
            for method in paths[path]
            if method in write_methods
        }
        assert found == {"post", "delete"}

    def test_file_out_component_has_no_storage_key(self):
        component = app.openapi()["components"]["schemas"]["FileOut"]
        assert "storage_key" not in component["properties"]

    def test_the_collection_is_an_array_of_file_out(self, paths):
        schema = paths["/documents/{document_id}/files"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/FileListOut"}
        component = app.openapi()["components"]["schemas"]["FileListOut"]
        assert component["type"] == "array"
        assert component["items"] == {"$ref": "#/components/schemas/FileOut"}

    def test_the_single_attachment_is_a_file_out(self, paths):
        schema = paths["/documents/{document_id}/files/{file_id}"]["get"]["responses"][
            "200"
        ]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/FileOut"}


class TestForbiddenOperations:
    def test_the_upload_route_is_wired_and_validates_its_body(
        self, client, make_document
    ):
        # TASK-DOC-005R made upload available, so the old 405 is gone. What is
        # still worth pinning is that the path is served and that a request
        # without the required field is refused by validation, not by routing.
        document = make_document()
        response = client.post(f"/documents/{document.id}/files")
        assert response.status_code == 422

    def test_the_delete_route_is_served(
        self, client, db, make_document, make_file
    ):
        # TASK-DOC-005T made the method available, so the old 405 is gone. What
        # stays pinned is that it removes the row and answers with no body.
        document = make_document()
        file = make_file(document.id)
        document_id = document.id
        file_id = file.id
        # The ids are read before the rollback: touching an expired attribute
        # afterwards would start the very transaction `detach` refuses.
        db.rollback()

        response = client.delete(f"/documents/{document_id}/files/{file_id}")

        assert response.status_code == 204
        assert response.content == b""
        assert db.get(File, file_id) is None

    def test_the_download_route_is_served_and_a_row_without_a_blob_is_a_500(
        self, client, make_document, make_file
    ):
        # TASK-DOC-005S made the route available, so the old 404 is gone.
        # `make_file` writes the row but no blob, which is exactly the case
        # 005S maps to a controlled 500 rather than a false "file not found".
        document = make_document()
        file = make_file(document.id)
        response = client.get(f"/documents/{document.id}/files/{file.id}/content")
        assert response.status_code == 500
        assert response.json() == {"detail": "Stored file content is unavailable"}


class TestExistingApisStillWork:
    def test_health_is_unchanged(self, client):
        assert client.get("/health").json() == {"status": "ok"}

    def test_previous_collections_are_still_documented(self, client):
        paths = app.openapi()["paths"]
        for path in ("/issuers", "/manufacturers", "/products", "/document-types"):
            assert path in paths

    def test_operation_count_includes_upload_download_and_delete(self, client):
        paths = app.openapi()["paths"]
        operations = sum(
            len([m for m in v if m in ("get", "post", "put", "patch", "delete")])
            for v in paths.values()
        )
        assert operations == 38
