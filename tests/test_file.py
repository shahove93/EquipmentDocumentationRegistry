from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
)

from app.models import Base, Document, DocumentType, File

EXPECTED_COLUMNS = [
    "id",
    "document_id",
    "original_filename",
    "storage_key",
    "mime_type",
    "size_bytes",
    "sha256",
    "uploaded_at",
]


def make_file(document=None, name="passport.pdf", key="docs/2026/01/passport.pdf"):
    if document is None:
        document = Document(document_type=DocumentType(name="Паспорт"), number="D-1")
    return File(
        document=document,
        original_filename=name,
        storage_key=key,
        mime_type="application/pdf",
        size_bytes=102400,
        sha256="a" * 64,
        uploaded_at=datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
    )


class TestFileTable:
    def test_table_name(self):
        assert File.__tablename__ == "files"

    def test_registered_in_metadata(self):
        assert "files" in Base.metadata.tables

    def test_all_eight_columns_present(self):
        assert list(File.__table__.columns.keys()) == EXPECTED_COLUMNS

    def test_no_extra_columns(self):
        assert len(File.__table__.columns) == 8
        for forbidden in ("is_primary", "file_type", "extension", "updated_at"):
            assert forbidden not in File.__table__.columns


class TestFileColumns:
    def test_id_is_integer_primary_key(self):
        col = File.__table__.c.id
        assert isinstance(col.type, Integer)
        assert col.primary_key is True

    def test_document_id_is_not_null(self):
        col = File.__table__.c.document_id
        assert isinstance(col.type, Integer)
        assert col.nullable is False

    def test_document_id_foreign_key_cascade(self):
        fks = list(File.__table__.c.document_id.foreign_keys)
        assert len(fks) == 1
        assert isinstance(fks[0], ForeignKey)
        assert fks[0].column.table.name == "documents"
        assert fks[0].column.name == "id"
        assert fks[0].ondelete == "CASCADE"

    def test_original_filename_string_255_not_null(self):
        col = File.__table__.c.original_filename
        assert isinstance(col.type, String)
        assert col.type.length == 255
        assert col.nullable is False

    def test_storage_key_string_500_not_null(self):
        col = File.__table__.c.storage_key
        assert isinstance(col.type, String)
        assert col.type.length == 500
        assert col.nullable is False

    def test_storage_key_is_unique(self):
        assert File.__table__.c.storage_key.unique is True
        unique_columns = [
            [c.name for c in uc.columns]
            for uc in File.__table__.constraints
            if type(uc).__name__ == "UniqueConstraint"
        ]
        assert ["storage_key"] in unique_columns

    def test_sha256_is_string_64_not_null(self):
        col = File.__table__.c.sha256
        assert isinstance(col.type, String)
        assert col.type.length == 64
        assert col.nullable is False

    def test_sha256_is_not_unique(self):
        assert not File.__table__.c.sha256.unique
        unique_columns = [
            [c.name for c in uc.columns]
            for uc in File.__table__.constraints
            if type(uc).__name__ == "UniqueConstraint"
        ]
        assert ["sha256"] not in unique_columns

    def test_only_storage_key_is_unique(self):
        unique_columns = [
            [c.name for c in uc.columns]
            for uc in File.__table__.constraints
            if type(uc).__name__ == "UniqueConstraint"
        ]
        assert unique_columns == [["storage_key"]]

    def test_mime_type_string_100_not_null(self):
        col = File.__table__.c.mime_type
        assert isinstance(col.type, String)
        assert col.type.length == 100
        assert col.nullable is False

    def test_size_bytes_bigint_not_null(self):
        col = File.__table__.c.size_bytes
        assert isinstance(col.type, BigInteger)
        assert col.nullable is False

    def test_uploaded_at_datetime_timezone_not_null(self):
        col = File.__table__.c.uploaded_at
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True
        assert col.nullable is False


class TestFileChecks:
    def test_size_bytes_non_negative_check_present(self):
        checks = {
            c.name: str(c.sqltext)
            for c in File.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        assert "ck_files_size_bytes_non_negative" in checks
        assert "size_bytes >= 0" in checks["ck_files_size_bytes_non_negative"]

    def test_no_sha256_check_constraint(self):
        check_names = [
            c.name
            for c in File.__table__.constraints
            if isinstance(c, CheckConstraint) and c.name is not None
        ]
        assert len(check_names) == 1
        assert all("sha256" not in (name or "") for name in check_names)


class TestFileIndexes:
    def test_document_id_id_index_is_declared_in_metadata(self):
        indexes = {index.name: index for index in File.__table__.indexes}
        index = indexes["ix_files_document_id_id"]
        assert [column.name for column in index.columns] == ["document_id", "id"]

    def test_the_index_is_not_unique(self):
        indexes = {index.name: index for index in File.__table__.indexes}
        assert indexes["ix_files_document_id_id"].unique is False

    def test_the_index_is_a_plain_index_without_dialect_options(self):
        indexes = {index.name: index for index in File.__table__.indexes}
        index = indexes["ix_files_document_id_id"]
        assert dict(index.dialect_kwargs) == {}
        assert len(index.expressions) == 2
        for expression in index.expressions:
            assert type(expression).__name__ == "Column"

    def test_no_other_index_is_declared(self):
        assert sorted(index.name for index in File.__table__.indexes) == [
            "ix_files_document_id_id"
        ]


class TestFileRelationships:
    def test_file_to_document(self):
        relationship = File.__mapper__.relationships["document"]
        assert relationship.mapper.class_ is Document
        assert relationship.uselist is False

    def test_document_to_files(self):
        relationship = Document.__mapper__.relationships["files"]
        assert relationship.mapper.class_ is File
        assert relationship.uselist is True

    def test_file_in_memory_preserves_values(self):
        document = Document(document_type=DocumentType(name="Паспорт"), number="D-1")
        file = make_file(document)
        assert file.id is None
        assert file.original_filename == "passport.pdf"
        assert file.storage_key == "docs/2026/01/passport.pdf"
        assert file.mime_type == "application/pdf"
        assert file.size_bytes == 102400
        assert file.sha256 == "a" * 64
        assert file.uploaded_at == datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc)
        assert file.document is document

    def test_document_has_multiple_files(self):
        document = Document(document_type=DocumentType(name="Паспорт"), number="D-1")
        first = make_file(document, name="passport.pdf", key="docs/1/passport.pdf")
        second = make_file(document, name="certificate.jpg", key="docs/2/cert.jpg")
        # присваивание file.document уже наполнило document.files через backref
        assert document.files == [first, second]
        assert first.document is document
        assert second.document is document

    def test_same_sha256_allowed_on_different_files(self):
        document = Document(document_type=DocumentType(name="Паспорт"), number="D-1")
        first = make_file(document, name="a.pdf", key="docs/a.pdf")
        second = make_file(document, name="b.pdf", key="docs/b.pdf")
        assert first.sha256 == second.sha256
        assert first.storage_key != second.storage_key

    def test_duplicate_storage_key_is_representable_in_metadata_only(self):
        # на уровне Python два объекта создать можно;
        # запрет обеспечивает UNIQUE на уровне БД
        document = Document(document_type=DocumentType(name="Паспорт"), number="D-1")
        first = make_file(document, name="a.pdf", key="docs/same.pdf")
        second = make_file(document, name="b.pdf", key="docs/same.pdf")
        assert first.storage_key == second.storage_key
        assert File.__table__.c.storage_key.unique is True

    def test_zero_size_bytes_allowed(self):
        file = make_file()
        file.size_bytes = 0
        assert file.size_bytes >= 0