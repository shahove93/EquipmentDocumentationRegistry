from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.api.files.schemas import FileListOut, FileOut
from app.models.file import File

UPLOADED_AT = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
STORAGE_KEY = "8f14e45fceea167a5a36dedd4bea2543"
SHA256 = "a" * 64

PUBLIC_FIELDS = {
    "id",
    "document_id",
    "original_filename",
    "mime_type",
    "size_bytes",
    "sha256",
    "uploaded_at",
}


def make_file(**overrides: object) -> File:
    """An in-memory File row, including the storage_key that must never leak."""
    values: dict[str, object] = {
        "id": 7,
        "document_id": 3,
        "original_filename": "passport.pdf",
        "storage_key": STORAGE_KEY,
        "mime_type": "application/pdf",
        "size_bytes": 12345,
        "sha256": SHA256,
        "uploaded_at": UPLOADED_AT,
    }
    values.update(overrides)
    return File(**values)  # type: ignore[arg-type]


def payload(**overrides: object) -> dict[str, object]:
    """A plain mapping of the public fields, for validation tests."""
    values: dict[str, object] = {
        "id": 7,
        "document_id": 3,
        "original_filename": "passport.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 12345,
        "sha256": SHA256,
        "uploaded_at": UPLOADED_AT,
    }
    values.update(overrides)
    return values


class TestFileOutDefinition:
    def test_exposes_exactly_the_public_fields(self):
        assert set(FileOut.model_fields) == PUBLIC_FIELDS

    def test_does_not_declare_storage_key(self):
        assert "storage_key" not in FileOut.model_fields

    def test_every_field_is_required(self):
        optional = [n for n, f in FileOut.model_fields.items() if not f.is_required()]
        assert optional == []

    def test_reads_attributes_from_orm_objects(self):
        assert FileOut.model_config.get("from_attributes") is True


class TestFileOutFromOrmObject:
    def test_serialises_a_file_row(self):
        out = FileOut.model_validate(make_file())
        assert out.id == 7
        assert out.document_id == 3
        assert out.original_filename == "passport.pdf"
        assert out.mime_type == "application/pdf"
        assert out.size_bytes == 12345
        assert out.sha256 == SHA256
        assert out.uploaded_at == UPLOADED_AT

    def test_document_id_is_independent_of_id(self):
        out = FileOut.model_validate(make_file(id=11, document_id=42))
        assert (out.id, out.document_id) == (11, 42)

    def test_uploaded_at_stays_a_datetime(self):
        assert isinstance(FileOut.model_validate(make_file()).uploaded_at, datetime)

    def test_size_bytes_stays_an_int(self):
        assert isinstance(FileOut.model_validate(make_file()).size_bytes, int)


class TestFileOutDoesNotLeakStorageKey:
    def test_dump_has_no_storage_key_field(self):
        assert "storage_key" not in FileOut.model_validate(make_file()).model_dump()

    def test_dump_has_exactly_the_public_keys(self):
        assert set(FileOut.model_validate(make_file()).model_dump()) == PUBLIC_FIELDS

    def test_json_never_contains_the_storage_key_value(self):
        json_body = FileOut.model_validate(make_file()).model_dump_json()
        assert STORAGE_KEY not in json_body
        assert "storage_key" not in json_body

    def test_schema_properties_have_no_storage_key(self):
        assert "storage_key" not in FileOut.model_json_schema()["properties"]

    def test_an_extra_storage_key_in_a_mapping_is_ignored(self):
        out = FileOut.model_validate(payload(storage_key=STORAGE_KEY))
        assert "storage_key" not in out.model_dump()


class TestFileOutValidation:
    def test_rejects_a_missing_required_field(self):
        for name in PUBLIC_FIELDS:
            incomplete = payload()
            del incomplete[name]
            with pytest.raises(ValidationError):
                FileOut.model_validate(incomplete)

    def test_rejects_a_non_integer_id(self):
        with pytest.raises(ValidationError):
            FileOut.model_validate(payload(id="abc"))

    def test_rejects_a_non_integer_size(self):
        with pytest.raises(ValidationError):
            FileOut.model_validate(payload(size_bytes="abc"))

    def test_rejects_a_non_datetime_uploaded_at(self):
        with pytest.raises(ValidationError):
            FileOut.model_validate(payload(uploaded_at="not-a-date"))


class TestFileOutOpenApi:
    @pytest.fixture
    def schema(self) -> dict:
        app = FastAPI()

        @app.get("/files/{file_id}", response_model=FileOut)
        def get_file(file_id: int) -> FileOut:
            return FileOut.model_validate(make_file())

        return app.openapi()

    def test_component_lists_exactly_the_public_properties(self, schema):
        component = schema["components"]["schemas"]["FileOut"]
        assert set(component["properties"]) == PUBLIC_FIELDS

    def test_component_does_not_mention_storage_key(self, schema):
        component = schema["components"]["schemas"]["FileOut"]
        assert "storage_key" not in component["properties"]
        assert "storage_key" not in component.get("required", [])


class TestFileListOut:
    def test_is_a_list_of_file_out(self):
        page = FileListOut.model_validate(
            [make_file(), make_file(id=8, document_id=3)]
        )
        assert isinstance(page.root, list)
        assert all(isinstance(item, FileOut) for item in page.root)
        assert [item.id for item in page.root] == [7, 8]

    def test_empty_page_is_valid(self):
        assert FileListOut.model_validate([]).root == []

    def test_json_is_a_bare_array_without_storage_key(self):
        json_body = FileListOut.model_validate([make_file()]).model_dump_json()
        assert json_body.startswith("[")
        assert "storage_key" not in json_body
        assert STORAGE_KEY not in json_body

    def test_items_still_carry_the_public_fields(self):
        item = FileListOut.model_validate([make_file()]).root[0]
        assert set(item.model_dump()) == PUBLIC_FIELDS
