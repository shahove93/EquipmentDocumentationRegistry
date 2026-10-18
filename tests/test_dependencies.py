from typing import Annotated

from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.config import Settings, get_settings
from app.database.connection import get_db
from app.dependencies import get_file_service
from app.services import transaction
from app.services.file_service import DEFAULT_MAX_UPLOAD_SIZE_BYTES, FileService

DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"


def build_settings(tmp_path, **overrides: object) -> Settings:
    """A Settings object with the storage fields pinned to the test directory.

    Explicit values win over `.env`, so the storage root and the size limit under
    test are never the ones a developer happens to have on disk.
    """
    values: dict[str, object] = {
        "DATABASE_URL": DATABASE_URL,
        "STORAGE_ROOT": str(tmp_path / "storage"),
        "MAX_UPLOAD_SIZE_BYTES": 1024,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


class TestGetFileServiceConstruction:
    def test_returns_a_file_service(self, db, tmp_path):
        service = get_file_service(db, build_settings(tmp_path))
        assert isinstance(service, FileService)

    def test_uses_the_session_it_was_given(self, db, tmp_path):
        service = get_file_service(db, build_settings(tmp_path))
        assert service._db is db

    def test_does_not_open_a_session_of_its_own(self, db, tmp_path):
        service = get_file_service(db, build_settings(tmp_path))
        assert service._db is db  # the very session handed in, not a copy

    def test_uses_the_configured_storage_root(self, db, tmp_path):
        service = get_file_service(db, build_settings(tmp_path))
        assert service._storage.root_path == (tmp_path / "storage").resolve()

    def test_uses_the_configured_upload_limit(self, db, tmp_path):
        service = get_file_service(db, build_settings(tmp_path))
        assert service.max_upload_size_bytes == 1024

    def test_limit_comes_from_settings_not_the_builtin_default(self, db, tmp_path):
        service = get_file_service(
            db, build_settings(tmp_path, MAX_UPLOAD_SIZE_BYTES=4242)
        )
        assert service.max_upload_size_bytes == 4242
        assert service.max_upload_size_bytes != DEFAULT_MAX_UPLOAD_SIZE_BYTES


class TestGetFileServiceIsSideEffectFree:
    def test_issues_no_sql(self, engine, db, tmp_path):
        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            get_file_service(db, build_settings(tmp_path))
        finally:
            event.remove(engine, "before_cursor_execute", record)

        assert statements == []

    def test_opens_no_transaction(self, db, tmp_path):
        assert db.in_transaction() is False
        get_file_service(db, build_settings(tmp_path))
        assert db.in_transaction() is False

    def test_leaves_the_session_as_the_attach_guard_expects(self, db, tmp_path):
        # attach and detach refuse a session that already has a transaction, so
        # the dependency must not start one. This is the exact question they ask.
        get_file_service(db, build_settings(tmp_path))
        assert transaction.transaction_existed_on_entry(db) is False


class TestDependencyOverrides:
    def test_get_file_service_can_be_replaced(self):
        app = FastAPI()
        sentinel = object()

        @app.get("/probe")
        def probe(service: Annotated[FileService, Depends(get_file_service)]):
            return {"replaced": service is sentinel}

        app.dependency_overrides[get_file_service] = lambda: sentinel
        try:
            with TestClient(app) as client:
                response = client.get("/probe")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json() == {"replaced": True}

    def test_service_uses_the_session_from_get_db(self, db):
        app = FastAPI()

        @app.get("/probe")
        def probe(service: Annotated[FileService, Depends(get_file_service)]):
            return {"same_session": service._db is db}

        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:
                response = client.get("/probe")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json() == {"same_session": True}

    def test_overridden_settings_reach_the_service(self, db, tmp_path):
        app = FastAPI()
        settings = build_settings(
            tmp_path,
            STORAGE_ROOT=str(tmp_path / "blobs"),
            MAX_UPLOAD_SIZE_BYTES=909,
        )

        @app.get("/probe")
        def probe(service: Annotated[FileService, Depends(get_file_service)]):
            return {
                "limit": service.max_upload_size_bytes,
                "root": str(service._storage.root_path),
            }

        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_settings] = lambda: settings
        try:
            with TestClient(app) as client:
                response = client.get("/probe")
        finally:
            app.dependency_overrides.clear()

        assert response.json() == {
            "limit": 909,
            "root": str((tmp_path / "blobs").resolve()),
        }


class TestMultipartSupport:
    def test_python_multipart_is_importable(self):
        # Import the canonical module name: the legacy `multipart` alias emits a
        # PendingDeprecationWarning and would add noise to the suite's warning
        # count without testing anything more.
        import python_multipart  # noqa: F401

    def test_a_route_can_declare_an_upload_file(self):
        app = FastAPI()

        @app.post("/upload")
        async def upload(file: UploadFile = File(...)):
            body = (await file.read()).decode()
            return {"filename": file.filename, "body": body}

        with TestClient(app) as client:
            response = client.post(
                "/upload", files={"file": ("note.txt", b"hello", "text/plain")}
            )

        assert response.status_code == 200
        assert response.json() == {"filename": "note.txt", "body": "hello"}

    def test_openapi_marks_the_upload_body_as_multipart(self):
        app = FastAPI()

        @app.post("/upload")
        async def upload(file: UploadFile = File(...)):
            return {}

        content = app.openapi()["paths"]["/upload"]["post"]["requestBody"]["content"]
        assert "multipart/form-data" in content
