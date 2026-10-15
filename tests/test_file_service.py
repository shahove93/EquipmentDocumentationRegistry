import ast
import hashlib
import io
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.file import File
from app.services.document_service import DocumentService
from app.services.file_service import (
    AttachmentNotFoundError,
    DocumentNotFoundError,
    FileService,
    FileServiceError,
    FileTooLargeError,
    FileValidationError,
    PendingDocumentChangesError,
    StorageWrittenError,
    TransactionAlreadyOpenError,
    UnsupportedFileTypeError,
)
from app.services.transaction import UncommittedChangesInSession
from app.services.storage import StorageError

PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n" + b"pdf-body" * 4
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"jpeg-body" * 4
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"png-body" * 4
SHA_PDF = hashlib.sha256(PDF_BYTES).hexdigest()


class CountingStream:
    """Non-seekable stream that records how it was read."""

    def __init__(self, payload: bytes, chunk_size: int = 1024) -> None:
        self._buffer = io.BytesIO(payload)
        self._chunk_size = chunk_size
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if size is None or size < 0:
            return self._buffer.read()
        return self._buffer.read(min(size, self._chunk_size))


@pytest.fixture
def service(db, storage):
    return FileService(db=db, storage=storage)


@pytest.fixture
def document(db, engine) -> Document:
    """A committed document, created without leaving `db` in a transaction.

    `attach` refuses to start inside a transaction that belongs to the caller,
    so a fixture that merely flushed would make every test using it fail on a
    rule the fixture itself had caused. The document is made through a session
    of its own and handed back detached, so `document.id` still reads without
    a query.
    """
    creator = Session(engine, future=True, expire_on_commit=False)
    try:
        doc = Document(document_type=DocumentType(name="Паспорт"), number="D-1")
        creator.add(doc)
        creator.commit()
    finally:
        creator.close()
    return doc


def make_service(db, storage, **kwargs):
    return FileService(db=db, storage=storage, **kwargs)


class TestUploadPdf:
    def test_creates_file_row(self, service, db, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert file.id is not None
        assert db.get(File, file.id) is not None

    def test_physical_file_exists(self, service, storage, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert storage.exists(file.storage_key) is True

    def test_content_matches(self, service, storage, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        with storage.open(file.storage_key) as stream:
            assert stream.read() == PDF_BYTES

    def test_mime_type(self, service, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert file.mime_type == "application/pdf"

    def test_extension_is_pdf(self, service, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert file.storage_key.endswith(".pdf")

    def test_size_bytes(self, service, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert file.size_bytes == len(PDF_BYTES)

    def test_sha256_exact_value(self, service, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert file.sha256 == SHA_PDF

    def test_sha256_is_lowercase_hex_64(self, service, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert len(file.sha256) == 64
        assert file.sha256 == file.sha256.lower()
        assert all(c in "0123456789abcdef" for c in file.sha256)

    def test_uploaded_at_is_timezone_aware(self, service, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert file.uploaded_at.tzinfo is not None

    def test_uploaded_at_matches_utc_instant(self, service, document):
        before = datetime.now(timezone.utc)
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        after = datetime.now(timezone.utc)
        # PostgreSQL returns timestamptz in the session timezone, so compare
        # the instant rather than the tzinfo identity
        assert before <= file.uploaded_at.astimezone(timezone.utc) <= after

    def test_storage_key_contains_document_id(self, service, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert file.storage_key.startswith(f"documents/{document.id}/")

    def test_document_id_stored(self, service, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert file.document_id == document.id

    def test_file_relationship_loaded(self, service, db, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert file.document_id == document.id
        managed = db.get(Document, document.id)
        assert [f.id for f in managed.files] == [file.id]


class TestUploadJpeg:
    def test_detects_jpeg_mime(self, service, document):
        file = service.upload(document.id, "photo.jpg", io.BytesIO(JPEG_BYTES))
        assert file.mime_type == "image/jpeg"

    def test_storage_key_ends_with_jpg(self, service, document):
        file = service.upload(document.id, "photo.jpg", io.BytesIO(JPEG_BYTES))
        assert file.storage_key.endswith(".jpg")


class TestUploadPng:
    def test_detects_png_mime(self, service, document):
        file = service.upload(document.id, "scan.png", io.BytesIO(PNG_BYTES))
        assert file.mime_type == "image/png"

    def test_storage_key_ends_with_png(self, service, document):
        file = service.upload(document.id, "scan.png", io.BytesIO(PNG_BYTES))
        assert file.storage_key.endswith(".png")


class TestMimeIgnoresExtension:
    def test_pdf_filename_with_jpeg_content(self, service, document):
        file = service.upload(document.id, "test.pdf", io.BytesIO(JPEG_BYTES))
        assert file.mime_type == "image/jpeg"
        assert file.storage_key.endswith(".jpg")

    def test_original_filename_kept_untouched(self, service, document):
        file = service.upload(document.id, "test.pdf", io.BytesIO(JPEG_BYTES))
        assert file.original_filename == "test.pdf"

    def test_jpg_filename_with_pdf_content(self, service, document):
        file = service.upload(document.id, "wrong.jpg", io.BytesIO(PDF_BYTES))
        assert file.mime_type == "application/pdf"
        assert file.storage_key.endswith(".pdf")

    def test_png_filename_with_pdf_content(self, service, document):
        file = service.upload(document.id, "wrong.png", io.BytesIO(PDF_BYTES))
        assert file.mime_type == "application/pdf"


class TestUnsupportedType:
    def test_plain_text_rejected(self, service, document):
        with pytest.raises(UnsupportedFileTypeError):
            service.upload(document.id, "notes.txt", io.BytesIO(b"just plain text"))

    def test_random_bytes_rejected(self, service, document):
        with pytest.raises(UnsupportedFileTypeError):
            service.upload(document.id, "blob.bin", io.BytesIO(b"\x01\x02\x03\x04\x05"))

    def test_zip_rejected(self, service, document):
        with pytest.raises(UnsupportedFileTypeError):
            service.upload(document.id, "archive.zip", io.BytesIO(b"PK\x03\x04payload"))

    def test_gif_rejected(self, service, document):
        with pytest.raises(UnsupportedFileTypeError):
            service.upload(document.id, "anim.gif", io.BytesIO(b"GIF89a"))

    def test_no_file_in_db(self, service, db, document):
        with pytest.raises(UnsupportedFileTypeError):
            service.upload(document.id, "notes.txt", io.BytesIO(b"text"))
        assert list(db.scalars(select(File))) == []

    def test_no_physical_file(self, service, storage, document):
        before = list(storage.root_path.rglob("*")) if storage.root_path.exists() else []
        with pytest.raises(UnsupportedFileTypeError):
            service.upload(document.id, "notes.txt", io.BytesIO(b"text"))
        after = list(storage.root_path.rglob("*")) if storage.root_path.exists() else []
        assert len(after) == len(before)

    def test_error_is_file_service_error(self, service, document):
        with pytest.raises(FileServiceError):
            service.upload(document.id, "notes.txt", io.BytesIO(b"text"))


class TestEmptyFile:
    def test_empty_stream_rejected(self, service, document):
        with pytest.raises(FileValidationError):
            service.upload(document.id, "empty.pdf", io.BytesIO(b""))

    def test_nothing_saved_to_db(self, service, db, document):
        with pytest.raises(FileValidationError):
            service.upload(document.id, "empty.pdf", io.BytesIO(b""))
        assert list(db.scalars(select(File))) == []

    def test_no_physical_file(self, service, storage, document):
        with pytest.raises(FileValidationError):
            service.upload(document.id, "empty.pdf", io.BytesIO(b""))
        files = [p for p in storage.root_path.rglob("*") if p.is_file()]
        assert files == []

    def test_whitespace_only_is_not_empty_but_unsupported(self, service, document):
        # not zero bytes, so it fails on type detection rather than emptiness
        with pytest.raises(UnsupportedFileTypeError):
            service.upload(document.id, "blank.pdf", io.BytesIO(b"   \n"))

    def test_prefix_without_signature_is_unsupported(self, service, document):
        with pytest.raises(UnsupportedFileTypeError):
            service.upload(document.id, "short.pdf", io.BytesIO(b"%PD"))


class TestTooLarge:
    def test_raises_too_large(self, db, storage, document):
        service = make_service(db, storage, max_upload_size_bytes=1024)
        with pytest.raises(FileTooLargeError):
            service.upload(
                document.id, "big.pdf", CountingStream(PDF_BYTES + b"x" * 4096)
            )

    def test_just_over_limit_rejected(self, db, storage, document):
        service = make_service(db, storage, max_upload_size_bytes=64)
        with pytest.raises(FileTooLargeError):
            service.upload(document.id, "big.pdf", io.BytesIO(PDF_BYTES + b"x" * 128))

    def test_exactly_at_limit_accepted(self, db, storage, document):
        service = make_service(db, storage, max_upload_size_bytes=len(PDF_BYTES))
        file = service.upload(document.id, "exact.pdf", io.BytesIO(PDF_BYTES))
        assert file.size_bytes == len(PDF_BYTES)

    def test_one_byte_under_limit_accepted(self, db, storage, document):
        service = make_service(db, storage, max_upload_size_bytes=len(PDF_BYTES) + 1)
        file = service.upload(document.id, "exact.pdf", io.BytesIO(PDF_BYTES))
        assert file.size_bytes == len(PDF_BYTES)

    def test_no_file_row_in_db(self, db, storage, document):
        service = make_service(db, storage, max_upload_size_bytes=128)
        with pytest.raises(FileTooLargeError):
            service.upload(document.id, "big.pdf", io.BytesIO(PDF_BYTES + b"x" * 4096))
        assert list(db.scalars(select(File))) == []

    def test_partial_file_removed_from_storage(self, db, storage, document):
        service = make_service(db, storage, max_upload_size_bytes=128)
        with pytest.raises(FileTooLargeError):
            service.upload(document.id, "big.pdf", io.BytesIO(PDF_BYTES + b"x" * 4096))
        files = [p for p in storage.root_path.rglob("*") if p.is_file()]
        assert files == [], f"partial file left behind: {files}"

    def test_default_limit_is_100_mib(self, db, storage):
        service = make_service(db, storage)
        assert service.max_upload_size_bytes == 100 * 1024 * 1024

    def test_error_is_file_service_error(self, db, storage, document):
        service = make_service(db, storage, max_upload_size_bytes=64)
        with pytest.raises(FileServiceError):
            service.upload(document.id, "big.pdf", io.BytesIO(PDF_BYTES + b"y" * 512))


class TestDocumentNotFound:
    def test_raises_not_found(self, service):
        with pytest.raises(DocumentNotFoundError):
            service.upload(999_999, "passport.pdf", io.BytesIO(PDF_BYTES))

    def test_no_physical_file(self, service, storage):
        with pytest.raises(DocumentNotFoundError):
            service.upload(999_999, "passport.pdf", io.BytesIO(PDF_BYTES))
        files = [p for p in storage.root_path.rglob("*") if p.is_file()]
        assert files == []

    def test_no_file_row(self, service, db):
        with pytest.raises(DocumentNotFoundError):
            service.upload(999_999, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert list(db.scalars(select(File))) == []

    def test_error_is_file_service_error(self, service):
        with pytest.raises(FileServiceError):
            service.upload(999_999, "passport.pdf", io.BytesIO(PDF_BYTES))


class TestOriginalFilenameValidation:
    def test_valid_name_stored_as_is(self, service, document):
        file = service.upload(document.id, "Паспорт качества.pdf", io.BytesIO(PDF_BYTES))
        assert file.original_filename == "Паспорт качества.pdf"

    def test_name_not_used_in_storage_key(self, service, document):
        file = service.upload(
            document.id, "unique-name-12345.pdf", io.BytesIO(PDF_BYTES)
        )
        assert "unique-name-12345" not in file.storage_key

    def test_too_long_rejected(self, service, document):
        name = "a" * 256
        with pytest.raises(FileValidationError):
            service.upload(document.id, name, io.BytesIO(PDF_BYTES))

    def test_max_length_accepted(self, service, document):
        name = "a" * 255
        file = service.upload(document.id, name, io.BytesIO(PDF_BYTES))
        assert file.original_filename == name

    def test_empty_name_rejected(self, service, document):
        with pytest.raises(FileValidationError):
            service.upload(document.id, "", io.BytesIO(PDF_BYTES))

    def test_whitespace_name_rejected(self, service, document):
        with pytest.raises(FileValidationError):
            service.upload(document.id, "   ", io.BytesIO(PDF_BYTES))

    def test_nul_rejected(self, service, document):
        with pytest.raises(FileValidationError):
            service.upload(document.id, "bad\x00name.pdf", io.BytesIO(PDF_BYTES))

    def test_non_string_rejected(self, service, document):
        with pytest.raises(FileValidationError):
            service.upload(document.id, 12345, io.BytesIO(PDF_BYTES))

    def test_none_rejected(self, service, document):
        with pytest.raises(FileValidationError):
            service.upload(document.id, None, io.BytesIO(PDF_BYTES))

    def test_nothing_saved_on_invalid_name(self, service, db, document):
        with pytest.raises(FileValidationError):
            service.upload(document.id, "", io.BytesIO(PDF_BYTES))
        assert list(db.scalars(select(File))) == []


class TestDuplicates:
    def test_same_content_twice_creates_two_files(self, service, db, document):
        first = service.upload(document.id, "a.pdf", io.BytesIO(PDF_BYTES))
        second = service.upload(document.id, "b.pdf", io.BytesIO(PDF_BYTES))
        assert first.id != second.id
        assert len(list(db.scalars(select(File)))) == 2

    def test_same_sha256_allowed(self, service, document):
        first = service.upload(document.id, "a.pdf", io.BytesIO(PDF_BYTES))
        second = service.upload(document.id, "b.pdf", io.BytesIO(PDF_BYTES))
        assert first.sha256 == second.sha256 == SHA_PDF

    def test_storage_keys_differ(self, service, document):
        first = service.upload(document.id, "a.pdf", io.BytesIO(PDF_BYTES))
        second = service.upload(document.id, "b.pdf", io.BytesIO(PDF_BYTES))
        assert first.storage_key != second.storage_key

    def test_both_physical_files_exist(self, service, storage, document):
        first = service.upload(document.id, "a.pdf", io.BytesIO(PDF_BYTES))
        second = service.upload(document.id, "b.pdf", io.BytesIO(PDF_BYTES))
        assert storage.exists(first.storage_key)
        assert storage.exists(second.storage_key)


class TestTransactionSemantics:
    def test_commit_failure_removes_physical_file(self, db, storage, document):
        class FailingSession:
            def __init__(self, inner):
                self._inner = inner

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def execute(self, *args, **kwargs):
                return self._inner.execute(*args, **kwargs)

            def in_transaction(self):
                # the double stands for a caller that has not started anything
                return False

            def scalar(self, *args, **kwargs):
                # the evidence lookup goes to the real session on purpose:
                # deciding a commit outcome needs a session that can still answer
                return self._inner.scalar(*args, **kwargs)

            def add(self, instance):
                self._inner.add(instance)

            def flush(self):
                self._inner.flush()

            def commit(self):
                raise RuntimeError("database is unavailable")

            def rollback(self):
                self._inner.rollback()

        service = make_service(FailingSession(db), storage)
        with pytest.raises(RuntimeError):
            service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        files = [p for p in storage.root_path.rglob("*") if p.is_file()]
        assert files == [], f"orphaned file after commit failure: {files}"

    def test_flush_failure_removes_physical_file(self, db, storage, document):
        class FailingSession:
            def __init__(self, inner):
                self._inner = inner

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def execute(self, *args, **kwargs):
                return self._inner.execute(*args, **kwargs)

            def in_transaction(self):
                # the double stands for a caller that has not started anything
                return False

            def scalar(self, *args, **kwargs):
                # the evidence lookup goes to the real session on purpose:
                # deciding a commit outcome needs a session that can still answer
                return self._inner.scalar(*args, **kwargs)

            def add(self, instance):
                self._inner.add(instance)

            def flush(self):
                raise RuntimeError("flush failed")

            def commit(self):
                self._inner.commit()

            def rollback(self):
                self._inner.rollback()

        service = make_service(FailingSession(db), storage)
        with pytest.raises(RuntimeError):
            service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        files = [p for p in storage.root_path.rglob("*") if p.is_file()]
        assert files == []

    def test_commit_failure_leaves_no_row(self, db, storage, document):
        class FailingSession:
            def __init__(self, inner):
                self._inner = inner

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def execute(self, *args, **kwargs):
                return self._inner.execute(*args, **kwargs)

            def in_transaction(self):
                # the double stands for a caller that has not started anything
                return False

            def scalar(self, *args, **kwargs):
                # the evidence lookup goes to the real session on purpose:
                # deciding a commit outcome needs a session that can still answer
                return self._inner.scalar(*args, **kwargs)

            def add(self, instance):
                self._inner.add(instance)

            def flush(self):
                self._inner.flush()

            def commit(self):
                raise RuntimeError("commit failed")

            def rollback(self):
                self._inner.rollback()

        service = make_service(FailingSession(db), storage)
        with pytest.raises(RuntimeError):
            service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert list(db.scalars(select(File))) == []

    def test_original_error_not_masked_by_cleanup_failure(self, db, storage, document):
        class ExplodingDeleteStorage:
            """Real storage for save(), but cleanup always fails."""

            def __init__(self, inner):
                self._inner = inner

            def save(self, storage_key, source):
                return self._inner.save(storage_key, source)

            def exists(self, storage_key):
                return self._inner.exists(storage_key)

            def open(self, storage_key):
                return self._inner.open(storage_key)

            def delete(self, storage_key):
                raise RuntimeError("cleanup exploded")

        class FailingSession:
            def __init__(self, inner):
                self._inner = inner

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def execute(self, *args, **kwargs):
                return self._inner.execute(*args, **kwargs)

            def in_transaction(self):
                # the double stands for a caller that has not started anything
                return False

            def scalar(self, *args, **kwargs):
                # the evidence lookup goes to the real session on purpose:
                # deciding a commit outcome needs a session that can still answer
                return self._inner.scalar(*args, **kwargs)

            def add(self, instance):
                self._inner.add(instance)

            def flush(self):
                self._inner.flush()

            def commit(self):
                raise ValueError("original database error")

            def rollback(self):
                self._inner.rollback()

        service = make_service(FailingSession(db), ExplodingDeleteStorage(storage))
        with pytest.raises(ValueError, match="original database error"):
            service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert list(db.scalars(select(File))) == []

    def test_storage_failure_leaves_no_row(self, db, document):
        class FailingStorage:
            def save(self, storage_key, source):
                raise StorageError("disk full")

            def exists(self, storage_key):
                return False

            def open(self, storage_key):
                raise FileNotFoundError

            def delete(self, storage_key):
                pass

        service = make_service(db, FailingStorage())
        with pytest.raises(StorageError):
            service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert list(db.scalars(select(File))) == []

    def test_source_failure_leaves_no_row(self, db, storage, document):
        class BrokenStream:
            def read(self, size=-1):
                if size and size > 4:
                    raise OSError("stream broke")
                return b"%PDF-1.7"

        service = make_service(db, storage)
        with pytest.raises(OSError):
            service.upload(document.id, "passport.pdf", BrokenStream())
        assert list(db.scalars(select(File))) == []
        files = [p for p in storage.root_path.rglob("*") if p.is_file()]
        assert files == []


class TestStreaming:
    def test_source_read_in_chunks(self, service, document):
        payload = PDF_BYTES + b"y" * (300 * 1024)
        stream = CountingStream(payload)
        service.upload(document.id, "big.pdf", stream)
        full_reads = [s for s in stream.read_sizes if s is None or s < 0]
        assert full_reads == [], "whole-file read() without size was used"

    def test_prefix_read_is_bounded(self, service, document):
        stream = CountingStream(PDF_BYTES)
        service.upload(document.id, "passport.pdf", stream)
        assert all(size != -1 for size in stream.read_sizes)
        assert min(stream.read_sizes) <= 8

    def test_large_file_streamed_correctly(self, db, storage, document):
        payload = b"%PDF-1.7" + b"z" * (2 * 1024 * 1024)
        service = make_service(db, storage)
        file = service.upload(document.id, "large.pdf", CountingStream(payload))
        assert file.size_bytes == len(payload)
        assert file.sha256 == hashlib.sha256(payload).hexdigest()
        with storage.open(file.storage_key) as stream:
            assert stream.read() == payload

    def test_content_preserved_with_non_seekable_source(self, service, storage, document):
        stream = CountingStream(JPEG_BYTES)
        file = service.upload(document.id, "photo.bin", stream)
        with storage.open(file.storage_key) as stored:
            assert stored.read() == JPEG_BYTES

    def test_no_seek_call_on_source(self, service, document):
        class NoSeekStream:
            def __init__(self, payload):
                self._buffer = io.BytesIO(payload)

            def read(self, size=-1):
                return self._buffer.read(size)

            def seek(self, *args, **kwargs):
                raise AssertionError("seek() must not be called")

        stream = NoSeekStream(PDF_BYTES)
        file = service.upload(document.id, "passport.pdf", stream)
        assert file.size_bytes == len(PDF_BYTES)


class TestPathSafety:
    def test_traversal_filename_stays_inside_root(self, service, storage, document):
        file = service.upload(
            document.id, "../../secret.pdf", io.BytesIO(PDF_BYTES)
        )
        assert file.original_filename == "../../secret.pdf"
        assert "secret" not in file.storage_key.replace(".pdf", "")
        assert file.storage_key.startswith(f"documents/{document.id}/")
        resolved = (storage.root_path / file.storage_key).resolve()
        assert storage.root_path.resolve() in resolved.parents

    def test_absolute_filename_stays_inside_root(self, service, storage, document):
        file = service.upload(document.id, "/etc/passwd", io.BytesIO(PDF_BYTES))
        assert file.storage_key.startswith(f"documents/{document.id}/")
        resolved = (storage.root_path / file.storage_key).resolve()
        assert storage.root_path.resolve() in resolved.parents

    def test_windows_traversal_filename(self, service, storage, document):
        file = service.upload(
            document.id, "..\\..\\secret.pdf", io.BytesIO(PDF_BYTES)
        )
        assert file.storage_key.startswith(f"documents/{document.id}/")

    def test_storage_key_format(self, service, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        directory, _, filename = file.storage_key.rpartition("/")
        assert directory == f"documents/{document.id}"
        stem, _, extension = filename.rpartition(".")
        assert len(stem) == 36  # uuid4 hex with dashes
        assert stem.count("-") == 4
        assert extension == "pdf"

    def test_nothing_written_outside_root(self, service, storage, document, tmp_path):
        service.upload(document.id, "../../escape.pdf", io.BytesIO(PDF_BYTES))
        assert not (tmp_path / "escape.pdf").exists()


class TestListForDocument:
    def test_lists_files_of_document(self, service, db, document):
        first = service.upload(document.id, "a.pdf", io.BytesIO(PDF_BYTES))
        second = service.upload(document.id, "b.jpg", io.BytesIO(JPEG_BYTES))
        files = service.list_for_document(document.id)
        assert [f.id for f in files] == [first.id, second.id]

    def test_excludes_other_documents(self, service, db, document):
        # committed through a session of its own: reading `other.id` between
        # the two attaches would otherwise reopen a transaction
        creator = Session(db.get_bind(), future=True, expire_on_commit=False)
        other = Document(document_type=DocumentType(name="Сертификат"), number="D-2")
        creator.add(other)
        creator.commit()
        other_id = other.id
        creator.close()

        mine = service.upload(document.id, "a.pdf", io.BytesIO(PDF_BYTES))
        theirs = service.upload(other_id, "b.pdf", io.BytesIO(PDF_BYTES))
        assert [f.id for f in service.list_for_document(document.id)] == [mine.id]
        assert [f.id for f in service.list_for_document(other_id)] == [theirs.id]

# ---------------------------------------------------------------------------
# TASK-DOC-005K: the staging stage and the transaction boundary it leaves open
# ---------------------------------------------------------------------------


@pytest.fixture
def other_session(engine):
    """An independent session, to see what the database itself can see."""
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    opened = []

    def _open():
        session = factory()
        opened.append(session)
        return session

    yield _open
    for session in opened:
        session.rollback()
        session.close()


def files_on_disk(storage):
    return [p for p in storage.root_path.rglob("*") if p.is_file()]


class NoCommitSession:
    """Delegates everything except `commit`, which must never be reached."""

    def __init__(self, inner):
        self._inner = inner
        self.commits = 0

    def get(self, *args, **kwargs):
        return self._inner.get(*args, **kwargs)

    def in_transaction(self):
        return False

    def add(self, instance):
        self._inner.add(instance)

    def flush(self):
        self._inner.flush()

    def commit(self):
        self.commits += 1
        raise AssertionError("_stage_upload must not commit")

    def rollback(self):
        self._inner.rollback()


class TestStageUploadDoesNotCommit:
    def test_it_never_calls_commit(self, db, storage, document):
        watched = NoCommitSession(db)
        file = FileService(db=watched, storage=storage)._stage_upload(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        assert watched.commits == 0
        assert file.storage_key

    def test_it_never_rolls_back_the_callers_session(self, db, storage, document, monkeypatch):
        service = FileService(db=db, storage=storage)
        rollbacks = []
        monkeypatch.setattr(db, "rollback", lambda: rollbacks.append(1))

        service._stage_upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert rollbacks == []

    def test_the_row_exists_in_the_staging_session(self, db, storage, document):
        file = FileService(db=db, storage=storage)._stage_upload(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        assert file.id is not None
        assert db.get(File, file.id) is not None

    def test_the_row_is_invisible_to_an_independent_transaction(
        self, db, storage, document, other_session
    ):
        FileService(db=db, storage=storage)._stage_upload(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        assert list(db.scalars(select(File))) != []

        observer = other_session()
        assert list(observer.scalars(select(File))) == [], (
            "uncommitted metadata became visible to another transaction"
        )

    def test_the_blob_is_written_to_storage(self, db, storage, document):
        file = FileService(db=db, storage=storage)._stage_upload(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        assert storage.exists(file.storage_key)
        assert files_on_disk(storage) != []

    def test_the_staged_metadata_is_correct(self, db, storage, document):
        file = FileService(db=db, storage=storage)._stage_upload(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        assert file.document_id == document.id
        assert file.original_filename == "passport.pdf"
        assert file.mime_type == "application/pdf"
        assert file.size_bytes == len(PDF_BYTES)
        assert file.sha256 == SHA_PDF
        assert isinstance(file.uploaded_at, datetime)

    def test_the_storage_key_is_a_fresh_uuid_under_the_document(
        self, db, storage, document
    ):
        service = FileService(db=db, storage=storage)
        first = service._stage_upload(document.id, "a.pdf", io.BytesIO(PDF_BYTES))
        second = service._stage_upload(document.id, "b.pdf", io.BytesIO(PDF_BYTES))

        for file in (first, second):
            assert file.storage_key.startswith(f"documents/{document.id}/")
            assert file.storage_key.endswith(".pdf")
        assert first.storage_key != second.storage_key


class TestStageUploadLeavesTheDecisionStatusAlone:
    def test_a_verified_document_stays_verified(self, db, storage):
        document = Document(
            document_type=DocumentType(name="Паспорт"), number="V-1",
            verification_status="verified",
        )
        db.add(document)
        db.flush()

        FileService(db=db, storage=storage)._stage_upload(
            document.id, "new-scan.pdf", io.BytesIO(PDF_BYTES)
        )
        db.refresh(document)
        assert document.verification_status == "verified"

    def test_a_rejected_document_stays_rejected(self, db, storage):
        document = Document(
            document_type=DocumentType(name="Паспорт"), number="R-1",
            verification_status="rejected",
        )
        db.add(document)
        db.flush()

        FileService(db=db, storage=storage)._stage_upload(
            document.id, "new-scan.pdf", io.BytesIO(PDF_BYTES)
        )
        db.refresh(document)
        assert document.verification_status == "rejected"

    def test_no_verification_event_is_written(self, db, storage):
        from app.models.document_verification_event import (
            DocumentVerificationEvent,
        )

        document = Document(
            document_type=DocumentType(name="Паспорт"), number="V-2",
            verification_status="verified",
        )
        db.add(document)
        db.flush()

        FileService(db=db, storage=storage)._stage_upload(
            document.id, "new-scan.pdf", io.BytesIO(PDF_BYTES)
        )
        assert list(db.scalars(select(DocumentVerificationEvent))) == []


class TestStageUploadReportsWhoOwnsTheBlob:
    class FailingFlushSession:
        def __init__(self, inner):
            self._inner = inner

        def get(self, *args, **kwargs):
            return self._inner.get(*args, **kwargs)

        def add(self, instance):
            self._inner.add(instance)

        def flush(self):
            raise RuntimeError("flush failed")

        def rollback(self):
            self._inner.rollback()

    def test_a_flush_failure_names_the_written_blob(self, db, storage, document):
        service = FileService(db=self.FailingFlushSession(db), storage=storage)

        with pytest.raises(StorageWrittenError) as info:
            service._stage_upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))

        assert storage.exists(info.value.storage_key), (
            "the reported key must point at the file that is actually on disk"
        )

    def test_the_original_failure_is_kept_as_the_cause(self, db, storage, document):
        service = FileService(db=self.FailingFlushSession(db), storage=storage)

        with pytest.raises(StorageWrittenError) as info:
            service._stage_upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))

        assert isinstance(info.value.__cause__, RuntimeError)
        assert str(info.value.__cause__) == "flush failed"

    def test_the_stage_does_not_delete_the_blob_itself(self, db, storage, document):
        service = FileService(db=self.FailingFlushSession(db), storage=storage)

        with pytest.raises(StorageWrittenError):
            service._stage_upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))

        assert len(files_on_disk(storage)) == 1, (
            "the stage must leave the choice of compensation to its caller"
        )

    def test_the_reported_key_is_the_one_the_stage_chose(self, db, storage, document):
        service = FileService(db=self.FailingFlushSession(db), storage=storage)
        with pytest.raises(StorageWrittenError) as info:
            service._stage_upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert info.value.storage_key.startswith(f"documents/{document.id}/")


class TestErrorsBeforeAnythingIsWritten:
    """Failures decided before a byte reaches disk, so nothing needs undoing."""

    def test_a_bad_name_is_refused_before_storage(self, db, storage, document):
        service = FileService(db=db, storage=storage)
        with pytest.raises(FileValidationError) as info:
            service._stage_upload(document.id, "", io.BytesIO(PDF_BYTES))
        assert not isinstance(info.value, StorageWrittenError), (
            "a failure before the write must not claim a blob exists"
        )
        assert files_on_disk(storage) == []

    def test_an_empty_file_is_refused_before_storage(self, db, storage, document):
        service = FileService(db=db, storage=storage)
        with pytest.raises(FileValidationError) as info:
            service._stage_upload(document.id, "passport.pdf", io.BytesIO(b""))
        assert not isinstance(info.value, StorageWrittenError)
        assert files_on_disk(storage) == []

    def test_an_unsupported_signature_is_refused_before_storage(
        self, db, storage, document
    ):
        service = FileService(db=db, storage=storage)
        with pytest.raises(UnsupportedFileTypeError) as info:
            service._stage_upload(document.id, "passport.pdf", io.BytesIO(b"GIF89a\x00"))
        assert not isinstance(info.value, StorageWrittenError)
        assert files_on_disk(storage) == []

    def test_an_oversized_file_leaves_nothing_behind(self, db, storage, document):
        # the limit is enforced while streaming, so this also proves that a
        # half-written blob is not left on disk
        service = FileService(db=db, storage=storage, max_upload_size_bytes=1)
        with pytest.raises(FileTooLargeError) as info:
            service._stage_upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))

        assert not isinstance(info.value, StorageWrittenError)
        assert files_on_disk(storage) == []

    def test_a_missing_document_is_refused_before_storage(self, db, storage):
        service = FileService(db=db, storage=storage)
        with pytest.raises(DocumentNotFoundError) as info:
            service._stage_upload(999_999, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert not isinstance(info.value, StorageWrittenError)
        assert files_on_disk(storage) == []

    def test_a_storage_failure_leaves_nothing_behind(self, db, document):
        class FailingStorage:
            def save(self, storage_key, source):
                raise StorageError("disk full")

            def exists(self, storage_key):
                return False

            def open(self, storage_key):
                raise FileNotFoundError

            def delete(self, storage_key):
                pass

        service = FileService(db=db, storage=FailingStorage())
        with pytest.raises(StorageError) as info:
            service._stage_upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert not isinstance(info.value, StorageWrittenError)
        assert list(db.scalars(select(File))) == []



class TestTheCallersRollbackDecides:
    def test_a_caller_rollback_removes_the_row(self, db, storage, document):
        FileService(db=db, storage=storage)._stage_upload(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        db.rollback()
        assert list(db.scalars(select(File))) == []

    def test_a_caller_rollback_does_not_touch_the_blob(self, db, storage, document):
        file = FileService(db=db, storage=storage)._stage_upload(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        db.rollback()
        assert storage.exists(file.storage_key), (
            "undoing the row must not silently undo the file too"
        )

    def test_the_caller_can_compensate_after_a_rollback(self, db, storage, document):
        file = FileService(db=db, storage=storage)._stage_upload(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        db.rollback()
        storage.delete(file.storage_key)
        assert files_on_disk(storage) == []

    def test_the_caller_can_commit_what_was_staged(self, db, storage, document, other_session):
        file = FileService(db=db, storage=storage)._stage_upload(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        db.commit()

        observer = other_session()
        assert [f.storage_key for f in observer.scalars(select(File))] == [file.storage_key]

    def test_the_caller_may_stage_several_files_in_one_transaction(
        self, db, storage, document
    ):
        # this is what a future attach() needs: one transaction carrying the
        # file rows, the status change and the history event
        service = FileService(db=db, storage=storage)
        service._stage_upload(document.id, "a.pdf", io.BytesIO(PDF_BYTES))
        service._stage_upload(document.id, "b.png", io.BytesIO(PNG_BYTES))
        db.commit()

        assert len(list(db.scalars(select(File)))) == 2

    def test_rolling_back_several_staged_files_leaves_every_blob_to_the_caller(
        self, db, storage, document
    ):
        service = FileService(db=db, storage=storage)
        first = service._stage_upload(document.id, "a.pdf", io.BytesIO(PDF_BYTES))
        second = service._stage_upload(document.id, "b.png", io.BytesIO(PNG_BYTES))
        db.rollback()

        assert list(db.scalars(select(File))) == []
        assert len(files_on_disk(storage)) == 2
        for blob in (first.storage_key, second.storage_key):
            assert storage.exists(blob)
class TestCommitOutcomesAreNotInterchangeable:
    """ADR-009 rule 10: the outcome of a commit is not in its exception class.

    `rollback()` does not undo a transaction the server already accepted, so no
    kind of error is proof that nothing was written. The only witness is the
    database, asked about this operation's own `storage_key` — a UUID generated
    here, which nothing else could have written. These tests pin the decision to
    that witness rather than to the exception, including the case where the two
    disagree.
    """

    class CommitFails:
        def __init__(self, inner, error):
            self._inner = inner
            self._error = error

        def get(self, *args, **kwargs):
            return self._inner.get(*args, **kwargs)

        def execute(self, *args, **kwargs):
            return self._inner.execute(*args, **kwargs)

        def in_transaction(self):
            return False

        def scalar(self, *args, **kwargs):
            return self._inner.scalar(*args, **kwargs)

        def add(self, instance):
            self._inner.add(instance)

        def flush(self):
            self._inner.flush()

        def commit(self):
            raise self._error

        def rollback(self):
            self._inner.rollback()

    class UnreadableOutcome(CommitFails):
        """The commit failed and the session can no longer answer anything."""

        def scalar(self, *args, **kwargs):
            raise OperationalError("SELECT", {}, Exception("connection is gone"))

    class LandedThenReportedAsFailed(CommitFails):
        """The server accepted the transaction and only then did the client fail."""

        def commit(self):
            self._inner.commit()
            raise self._error

    @staticmethod
    def _operational():
        return OperationalError("COMMIT", {}, Exception("server closed the connection"))

    @staticmethod
    def _interface():
        return InterfaceError("COMMIT", {}, Exception("connection already closed"))

    @staticmethod
    def _integrity():
        return IntegrityError("COMMIT", {}, Exception("duplicate key value"))

    def _attach_with(self, db, storage, document, double, error=None):
        service = FileService(db=double(db, error), storage=storage)
        with pytest.raises(Exception):
            service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))

    def test_a_connection_error_the_session_can_still_answer_is_a_rollback(
        self, db, storage, document
    ):
        self._attach_with(db, storage, document, self.CommitFails, self._operational())
        assert files_on_disk(storage) == []

    def test_a_closed_interface_is_decided_the_same_way(self, db, storage, document):
        self._attach_with(db, storage, document, self.CommitFails, self._interface())
        assert files_on_disk(storage) == []

    def test_a_refused_transaction_removes_the_blob(self, db, storage, document):
        self._attach_with(db, storage, document, self.CommitFails, self._integrity())
        assert files_on_disk(storage) == []

    def test_a_refused_transaction_of_any_other_kind_removes_the_blob(
        self, db, storage, document
    ):
        self._attach_with(db, storage, document, self.CommitFails, RuntimeError("no"))
        assert files_on_disk(storage) == []

    @pytest.mark.parametrize(
        "make_error",
        [_operational, _interface, _integrity, lambda: RuntimeError("plain")],
        ids=["operational", "interface", "integrity", "runtime"],
    )
    def test_the_error_class_alone_does_not_decide(
        self, db, storage, document, make_error
    ):
        # same evidence, four different exceptions, one outcome: the decision
        # follows the database, not the error
        self._attach_with(db, storage, document, self.CommitFails, make_error())
        assert files_on_disk(storage) == []

    def test_an_unreadable_session_keeps_the_blob_and_names_it(
        self, db, storage, document, caplog
    ):
        self._attach_with(
            db, storage, document, self.UnreadableOutcome, self._operational()
        )

        assert len(files_on_disk(storage)) == 1, (
            "an outcome nobody can establish must leave the file alone"
        )
        record = caplog.records[-1]
        assert record.storage_key.startswith(f"documents/{document.id}/")
        assert record.document_id == document.id
        assert record.failure_category == "unknown_commit_outcome"
        assert record.operation == "file.attach"

    def test_a_landed_transaction_is_reported_rather_than_deleted(
        self, db, storage, document, caplog
    ):
        self._attach_with(
            db,
            storage,
            document,
            self.LandedThenReportedAsFailed,
            self._operational(),
        )

        assert len(files_on_disk(storage)) == 1, (
            "the row is in the database, so the blob it points at must stay"
        )
        record = caplog.records[-1]
        assert record.failure_category == "commit_landed_despite_failure"

    def test_a_landed_transaction_keeps_its_row(self, db, storage, document):
        self._attach_with(
            db, storage, document, self.LandedThenReportedAsFailed, self._operational()
        )
        assert len(list(db.scalars(select(File)))) == 1

    def test_an_unknown_outcome_leaves_no_row_from_this_session(self, db, storage, document):
        self._attach_with(db, storage, document, self.CommitFails, self._operational())
        assert list(db.scalars(select(File))) == []

    def test_a_failed_compensation_still_surfaces_the_original_error(
        self, db, storage, document, caplog
    ):
        class ExplodingDeleteStorage:
            def __init__(self, inner):
                self._inner = inner

            def save(self, storage_key, source):
                return self._inner.save(storage_key, source)

            def exists(self, storage_key):
                return self._inner.exists(storage_key)

            def open(self, storage_key):
                return self._inner.open(storage_key)

            def delete(self, storage_key):
                raise RuntimeError("cleanup exploded")

        service = FileService(
            db=self.CommitFails(db, RuntimeError("commit failed")),
            storage=ExplodingDeleteStorage(storage),
        )
        with pytest.raises(RuntimeError, match="commit failed"):
            service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))

        assert len(files_on_disk(storage)) == 1
        record = caplog.records[-1]
        assert record.failure_category == "compensation_failed:commit_refused"

    def test_upload_still_commits_on_success(self, db, storage, document, other_session):
        file = FileService(db=db, storage=storage).upload(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        observer = other_session()
        assert [f.id for f in observer.scalars(select(File))] == [file.id]


# ---------------------------------------------------------------------------
# TASK-DOC-005L: attach() as a finished unit of work
# ---------------------------------------------------------------------------


@pytest.fixture
def decided(db, engine):
    """A committed document already carrying a verdict, detached and readable.

    Created through a session of its own so the caller of `attach` is left
    without a transaction, which `attach` requires and refuses to work around.
    """
    creator = Session(engine, future=True, expire_on_commit=False)
    counter = {"n": 0}

    def _make(status: str, reason: str = "проверено вручную"):
        counter["n"] += 1
        doc = Document(
            document_type=DocumentType(name=f"Тип-{counter['n']}"),
            number=f"D-{counter['n']}",
            verification_status=status,
        )
        creator.add(doc)
        creator.flush()
        creator.add(
            DocumentVerificationEvent(
                document_id=doc.id,
                from_status="pending",
                to_status=status,
                event_type=status,
                reason=reason,
            )
        )
        creator.commit()
        creator.expunge_all()
        return doc

    try:
        yield _make
    finally:
        creator.close()


def events_of(session, document_id):
    return list(
        session.scalars(
            select(DocumentVerificationEvent)
            .where(DocumentVerificationEvent.document_id == document_id)
            .order_by(DocumentVerificationEvent.id)
        )
    )


class TestAttachToAPendingDocument:
    def test_the_file_is_stored_and_committed(self, db, storage, document, other_session):
        file = FileService(db=db, storage=storage).attach(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        observer = other_session()
        assert [f.id for f in observer.scalars(select(File))] == [file.id]

    def test_the_status_does_not_move(self, db, storage, document):
        FileService(db=db, storage=storage).attach(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        assert db.get(Document, document.id).verification_status == "pending"

    def test_no_history_is_written(self, db, storage, document):
        FileService(db=db, storage=storage).attach(
            document.id, "passport.pdf", io.BytesIO(PDF_BYTES)
        )
        assert events_of(db, document.id) == []


class TestAttachWithdrawsAVerdict:
    @pytest.mark.parametrize(
        "was", ["verified", "rejected"], ids=["verified", "rejected"]
    )
    def test_the_document_returns_to_pending(self, db, storage, decided, was):
        document = decided(was)
        FileService(db=db, storage=storage).attach(
            document.id, "new-scan.pdf", io.BytesIO(PDF_BYTES)
        )
        assert db.get(Document, document.id).verification_status == "pending"

    @pytest.mark.parametrize(
        "was", ["verified", "rejected"], ids=["verified", "rejected"]
    )
    def test_exactly_one_reopened_event_is_written(self, db, storage, decided, was):
        document = decided(was)
        FileService(db=db, storage=storage).attach(
            document.id, "new-scan.pdf", io.BytesIO(PDF_BYTES)
        )
        written = events_of(db, document.id)
        assert len(written) == 2, "the earlier verdict must survive the reopen"

        reopened = [e for e in written if e.event_type == "reopened"]
        assert len(reopened) == 1
        assert reopened[0].reason == "file_added"
        assert reopened[0].from_status == was
        assert reopened[0].to_status == "pending"

    def test_the_reopen_and_the_file_are_one_transaction(
        self, db, storage, decided, other_session
    ):
        document = decided("verified")
        file = FileService(db=db, storage=storage).attach(
            document.id, "new-scan.pdf", io.BytesIO(PDF_BYTES)
        )

        observer = other_session()
        assert observer.get(Document, document.id).verification_status == "pending"
        assert [f.id for f in observer.scalars(select(File))] == [file.id]
        assert len(events_of(observer, document.id)) == 2

    def test_only_the_first_upload_reopens(self, db, storage, decided):
        document = decided("verified")
        service = FileService(db=db, storage=storage)

        service.attach(document.id, "first.pdf", io.BytesIO(PDF_BYTES))
        service.attach(document.id, "second.pdf", io.BytesIO(PDF_BYTES))
        service.attach(document.id, "third.png", io.BytesIO(PNG_BYTES))

        assert len(list(db.scalars(select(File)))) == 3
        assert db.get(Document, document.id).verification_status == "pending"
        reopened = [e for e in events_of(db, document.id) if e.event_type == "reopened"]
        assert len(reopened) == 1, "a second upload found nothing left to withdraw"

    def test_a_second_round_of_files_reopens_again(self, db, storage, decided):
        document = decided("verified")
        service = FileService(db=db, storage=storage)
        service.attach(document.id, "first.pdf", io.BytesIO(PDF_BYTES))

        DocumentService.verify(db, document.id, "повторная проверка")
        # `verify` finishes with a refresh, which leaves a transaction open;
        # in production these are two separate requests with two sessions
        db.rollback()

        service.attach(document.id, "second.pdf", io.BytesIO(PDF_BYTES))
        reopened = [e for e in events_of(db, document.id) if e.event_type == "reopened"]
        assert len(reopened) == 2
        assert [e.reason for e in reopened] == ["file_added", "file_added"]


class TestAFailedAttachChangesNothing:
    def test_an_invalid_file_leaves_the_verdict_alone(self, db, storage, decided):
        document = decided("verified")
        with pytest.raises(UnsupportedFileTypeError):
            FileService(db=db, storage=storage).attach(
                document.id, "scan.gif", io.BytesIO(b"GIF89a-not-allowed")
            )

        assert db.get(Document, document.id).verification_status == "verified"
        assert len(events_of(db, document.id)) == 1
        assert list(db.scalars(select(File))) == []
        assert files_on_disk(storage) == []

    def test_an_oversized_file_leaves_the_verdict_alone(self, db, storage, decided):
        document = decided("verified")
        service = FileService(db=db, storage=storage, max_upload_size_bytes=1)
        with pytest.raises(FileTooLargeError):
            service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES))

        assert db.get(Document, document.id).verification_status == "verified"
        assert files_on_disk(storage) == []

    def test_a_flush_failure_rolls_back_metadata_and_history(self, db, storage, decided):
        class FlushFails:
            def __init__(self, inner):
                self._inner = inner

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def execute(self, *args, **kwargs):
                return self._inner.execute(*args, **kwargs)

            def add(self, instance):
                self._inner.add(instance)

            def flush(self):
                # only once the file row is staged: an earlier autoflush inside
                # the locking read would fail the call for the wrong reason
                if any(isinstance(o, File) for o in self._inner.new):
                    raise RuntimeError("flush failed")
                self._inner.flush()

            def in_transaction(self):
                return False

            def scalar(self, *args, **kwargs):
                return self._inner.scalar(*args, **kwargs)

            def commit(self):
                self._inner.commit()

            def rollback(self):
                self._inner.rollback()

        document = decided("verified")
        service = FileService(db=FlushFails(db), storage=storage)

        # what the caller sees is the failure itself; the storage wrapper is
        # still reachable in the chain, so nothing about the handover is lost
        with pytest.raises(RuntimeError, match="flush failed") as info:
            service.attach(document.id, "new-scan.pdf", io.BytesIO(PDF_BYTES))

        assert isinstance(info.value.__context__, StorageWrittenError)
        assert files_on_disk(storage) == [], "the blob must be compensated"
        assert list(db.scalars(select(File))) == []
        assert len(events_of(db, document.id)) == 1
        assert db.get(Document, document.id).verification_status == "verified"

    def test_a_history_flush_failure_inside_the_commit_is_compensated(
        self, db, storage, decided
    ):
        class HistoryFlushFails:
            """Accepts the file row, then fails while writing the event."""

            def __init__(self, inner):
                self._inner = inner

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def execute(self, *args, **kwargs):
                return self._inner.execute(*args, **kwargs)

            def add(self, instance):
                self._inner.add(instance)

            def flush(self):
                self._inner.flush()

            def in_transaction(self):
                return False

            def scalar(self, *args, **kwargs):
                return self._inner.scalar(*args, **kwargs)

            def commit(self):
                # the commit flushes the pending event; that is where the
                # database refuses, so the whole transaction dies here
                self._inner.flush()
                raise RuntimeError("event could not be written")

            def rollback(self):
                self._inner.rollback()

        document = decided("verified")
        service = FileService(db=HistoryFlushFails(db), storage=storage)

        with pytest.raises(RuntimeError, match="event could not be written"):
            service.attach(document.id, "new-scan.pdf", io.BytesIO(PDF_BYTES))

        assert files_on_disk(storage) == []
        assert list(db.scalars(select(File))) == []
        assert len(events_of(db, document.id)) == 1
        assert db.get(Document, document.id).verification_status == "verified"

    def test_a_storage_failure_leaves_the_verdict_alone(self, db, decided):
        class FailingStorage:
            def save(self, storage_key, source):
                raise StorageError("disk full")

            def exists(self, storage_key):
                return False

            def open(self, storage_key):
                raise FileNotFoundError

            def delete(self, storage_key):
                pass

        document = decided("rejected")
        with pytest.raises(StorageError):
            FileService(db=db, storage=FailingStorage()).attach(
                document.id, "new-scan.pdf", io.BytesIO(PDF_BYTES)
            )

        assert db.get(Document, document.id).verification_status == "rejected"
        assert len(events_of(db, document.id)) == 1

    def test_a_missing_document_is_refused(self, db, storage):
        with pytest.raises(DocumentNotFoundError):
            FileService(db=db, storage=storage).attach(
                999_999, "passport.pdf", io.BytesIO(PDF_BYTES)
            )
        assert files_on_disk(storage) == []


class TestTheTransactionGuard:
    def test_an_open_transaction_is_refused(self, db, storage, document):
        db.execute(text("SELECT 1"))
        service = FileService(db=db, storage=storage)

        with pytest.raises(TransactionAlreadyOpenError):
            service.attach(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))

        assert files_on_disk(storage) == [], "the guard must run before any write"
        assert list(db.scalars(select(File))) == []

    def test_the_caller_transaction_is_left_open(self, db, storage, document):
        db.execute(text("SELECT 1"))
        service = FileService(db=db, storage=storage)

        with pytest.raises(TransactionAlreadyOpenError):
            service.attach(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))

        assert db.in_transaction(), "the caller's transaction must not be ended"

    def test_the_caller_staged_work_is_not_committed(self, db, storage, document, other_session):
        db.add(Document(document_type=DocumentType(name="Чужой"), number="FOREIGN"))
        service = FileService(db=db, storage=storage)

        with pytest.raises(TransactionAlreadyOpenError):
            service.attach(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))

        observer = other_session()
        assert observer.scalars(
            select(Document.number).where(Document.number == "FOREIGN")
        ).all() == [], "a refused call must not commit what the caller had staged"

    def test_the_refusal_leaves_the_documents_untouched(self, db, storage, decided):
        document = decided("verified")
        db.execute(text("SELECT 1"))
        service = FileService(db=db, storage=storage)

        with pytest.raises(TransactionAlreadyOpenError):
            service.attach(document.id, "new-scan.pdf", io.BytesIO(PDF_BYTES))

        assert db.get(Document, document.id).verification_status == "verified"
        assert len(events_of(db, document.id)) == 1

    def test_the_refusal_carries_no_document_details(self, db, storage, document):
        db.execute(text("SELECT 1"))
        service = FileService(db=db, storage=storage)
        with pytest.raises(TransactionAlreadyOpenError) as info:
            service.attach(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert "passport.pdf" not in str(info.value)


class TestAPendingDocumentIsNotOverwritten:
    """Defence in depth for the guard the locking read itself applies.

    Reaching it requires a session that reports no transaction while holding a
    modified document. In ordinary use the outer guard catches that first,
    because changing an attached object opens a transaction — which is why this
    test drives the inner guard directly instead of pretending a normal caller
    could get there.
    """

    def test_a_modified_document_is_refused(self, db, storage, document):
        loaded = db.get(Document, document.id)
        loaded.notes = "черновик"

        class HidesItsTransaction:
            def __init__(self, inner):
                self._inner = inner

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def execute(self, *args, **kwargs):
                return self._inner.execute(*args, **kwargs)

            def in_transaction(self):
                return False

            def add(self, instance):
                self._inner.add(instance)

            def flush(self):
                self._inner.flush()

            def commit(self):
                self._inner.commit()

            def scalar(self, *args, **kwargs):
                return self._inner.scalar(*args, **kwargs)

            def rollback(self):
                self._inner.rollback()

        service = FileService(db=HidesItsTransaction(db), storage=storage)
        with pytest.raises(PendingDocumentChangesError) as info:
            service.attach(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))

        assert info.value.document_id == document.id
        assert isinstance(info.value.__cause__, UncommittedChangesInSession)
        assert files_on_disk(storage) == []

    def test_the_draft_is_not_discarded(self, db, storage, document):
        loaded = db.get(Document, document.id)
        loaded.notes = "черновик"

        class HidesItsTransaction:
            def __init__(self, inner):
                self._inner = inner

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def execute(self, *args, **kwargs):
                return self._inner.execute(*args, **kwargs)

            def in_transaction(self):
                return False

            def add(self, instance):
                self._inner.add(instance)

            def flush(self):
                self._inner.flush()

            def commit(self):
                self._inner.commit()

            def scalar(self, *args, **kwargs):
                return self._inner.scalar(*args, **kwargs)

            def rollback(self):
                self._inner.rollback()

        service = FileService(db=HidesItsTransaction(db), storage=storage)
        with pytest.raises(PendingDocumentChangesError):
            service.attach(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))

        assert loaded.notes == "черновик"


class TestUploadIsTheSameOperation:
    def test_upload_reopens_a_verdict_too(self, db, storage, decided):
        document = decided("verified")
        FileService(db=db, storage=storage).upload(
            document.id, "new-scan.pdf", io.BytesIO(PDF_BYTES)
        )
        assert db.get(Document, document.id).verification_status == "pending"
        reopened = [e for e in events_of(db, document.id) if e.event_type == "reopened"]
        assert len(reopened) == 1
        assert reopened[0].reason == "file_added"

    def test_upload_cannot_bypass_the_transaction_guard(self, db, storage, document):
        db.execute(text("SELECT 1"))
        service = FileService(db=db, storage=storage)
        with pytest.raises(TransactionAlreadyOpenError):
            service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert files_on_disk(storage) == []

    def test_upload_takes_the_same_lock(self, db, storage, document):
        service = FileService(db=db, storage=storage)
        statements = []
        sa_event.listen(
            db.get_bind(),
            "before_cursor_execute",
            lambda conn, cursor, statement, *a: statements.append(statement),
        )
        try:
            service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        finally:
            sa_event.remove(
                db.get_bind(), "before_cursor_execute",
                lambda *a: None,
            ) if False else None

        assert any("FOR UPDATE" in s for s in statements), (
            "upload() must not be a way around the document lock"
        )

    def test_both_methods_produce_the_same_result(self, db, storage, decided, tmp_path):
        from app.services.local_storage import LocalStorageBackend

        first = decided("verified")
        second = decided("rejected")
        FileService(db=db, storage=storage).attach(
            first.id, "via-attach.pdf", io.BytesIO(PDF_BYTES)
        )
        FileService(
            db=db, storage=LocalStorageBackend(root_path=tmp_path / "second")
        ).upload(second.id, "via-upload.pdf", io.BytesIO(PDF_BYTES))

        assert db.get(Document, first.id).verification_status == "pending"
        assert db.get(Document, second.id).verification_status == "pending"
        assert [
            e.reason for d in (first, second) for e in events_of(db, d.id)
            if e.event_type == "reopened"
        ] == ["file_added", "file_added"]


class TestTheLockIsAlwaysReleased:
    """A refusal must not keep the document locked.

    The lock is taken before the file is looked at, so every early refusal has
    to hand it back. Otherwise one rejected upload makes every other operation
    on that document wait for as long as the caller's session lives.
    """

    def test_an_invalid_file_releases_the_lock(self, db, storage, document, other_session):
        service = FileService(db=db, storage=storage)
        with pytest.raises(UnsupportedFileTypeError):
            service.attach(document.id, "scan.gif", io.BytesIO(b"GIF89a-no"))

        assert not db.in_transaction(), "the service must end its own transaction"
        probe = other_session()
        probe.execute(text(f"SELECT 1 FROM documents WHERE id = {document.id} FOR UPDATE"))
        probe.rollback()

    def test_an_oversized_file_releases_the_lock(self, db, storage, document, other_session):
        service = FileService(db=db, storage=storage, max_upload_size_bytes=1)
        with pytest.raises(FileTooLargeError):
            service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES))

        probe = other_session()
        probe.execute(text(f"SELECT 1 FROM documents WHERE id = {document.id} FOR UPDATE"))
        probe.rollback()

    def test_a_storage_failure_releases_the_lock(self, db, decided, other_session):
        class FailingStorage:
            def save(self, storage_key, source):
                raise StorageError("disk full")

            def exists(self, storage_key):
                return False

            def open(self, storage_key):
                raise FileNotFoundError

            def delete(self, storage_key):
                pass

        document = decided("verified")
        with pytest.raises(StorageError):
            FileService(db=db, storage=FailingStorage()).attach(
                document.id, "scan.pdf", io.BytesIO(PDF_BYTES)
            )

        probe = other_session()
        probe.execute(text(f"SELECT 1 FROM documents WHERE id = {document.id} FOR UPDATE"))
        probe.rollback()

    def test_a_flush_failure_releases_the_lock(self, db, storage, decided, other_session):
        class FlushFails:
            def __init__(self, inner):
                self._inner = inner

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def execute(self, *args, **kwargs):
                return self._inner.execute(*args, **kwargs)

            def add(self, instance):
                self._inner.add(instance)

            def flush(self):
                if any(isinstance(o, File) for o in self._inner.new):
                    raise RuntimeError("flush failed")
                self._inner.flush()

            def in_transaction(self):
                return False

            def scalar(self, *args, **kwargs):
                return self._inner.scalar(*args, **kwargs)

            def commit(self):
                self._inner.commit()

            def rollback(self):
                self._inner.rollback()

        document = decided("verified")
        with pytest.raises(RuntimeError):
            FileService(db=FlushFails(db), storage=storage).attach(
                document.id, "scan.pdf", io.BytesIO(PDF_BYTES)
            )

        probe = other_session()
        probe.execute(text(f"SELECT 1 FROM documents WHERE id = {document.id} FOR UPDATE"))
        probe.rollback()

    def test_a_missing_document_leaves_nothing_locked(self, db, storage, other_session):
        with pytest.raises(DocumentNotFoundError):
            FileService(db=db, storage=storage).attach(
                999_999, "scan.pdf", io.BytesIO(PDF_BYTES)
            )
        assert not db.in_transaction()

    def test_another_document_is_not_blocked_by_a_refusal(self, db, storage, decided, other_session):
        first = decided("verified")
        second = decided("verified")

        with pytest.raises(UnsupportedFileTypeError):
            FileService(db=db, storage=storage).attach(
                first.id, "scan.gif", io.BytesIO(b"GIF89a-no")
            )

        probe = other_session()
        probe.execute(text(f"SELECT 1 FROM documents WHERE id = {second.id} FOR UPDATE"))
        probe.rollback()


# ---------------------------------------------------------------------------
# TASK-DOC-005M: detach() as a finished unit of work
# ---------------------------------------------------------------------------


@pytest.fixture
def attached(engine, storage):
    """A committed document with committed blobs, readable while detached.

    Built through a session of its own so the caller is left without a
    transaction, which `detach` requires. The blobs are written through the
    same backend the service will delete them from, so `files_on_disk` counts
    what the operation actually left behind.
    """

    def _make(status="pending", count=1, with_event=None):
        if with_event is None:
            with_event = status != "pending"

        creator = Session(engine, future=True, expire_on_commit=False)
        try:
            # `document_types.name` is unique in the database, so the name has
            # to be unique per call rather than per status
            label = uuid.uuid4().hex[:12]
            document = Document(
                document_type=DocumentType(name=f"Тип-{label}"),
                number=f"E-{label}",
                verification_status=status,
            )
            creator.add(document)
            creator.flush()

            if with_event:
                creator.add(
                    DocumentVerificationEvent(
                        document_id=document.id,
                        from_status="pending",
                        to_status=status,
                        event_type=status,
                        reason="решение, принятое до теста",
                    )
                )

            keys = []
            for index in range(count):
                key = f"documents/{document.id}/existing-{index}.pdf"
                storage.save(key, io.BytesIO(PDF_BYTES))
                creator.add(
                    File(
                        document_id=document.id,
                        original_filename=f"existing-{index}.pdf",
                        storage_key=key,
                        mime_type="application/pdf",
                        size_bytes=len(PDF_BYTES),
                        sha256=SHA_PDF,
                        uploaded_at=datetime.now(timezone.utc),
                    )
                )
                keys.append(key)

            creator.commit()
            creator.expire_all()
            file_ids = [
                row.id
                for row in creator.scalars(
                    select(File)
                    .where(File.document_id == document.id)
                    .order_by(File.id)
                )
            ]
            creator.expunge_all()
        finally:
            creator.close()
        return document, file_ids, keys

    return _make


class TestDetachFromAPendingDocument:
    def test_the_file_row_is_gone(self, db, storage, attached, other_session):
        document, (file_id,), (key,) = attached("pending")
        FileService(db=db, storage=storage).detach(document.id, file_id)

        observer = other_session()
        assert observer.get(File, file_id) is None
        assert not storage.exists(key)

    def test_the_status_does_not_move(self, db, storage, attached):
        document, (file_id,), _ = attached("pending")
        FileService(db=db, storage=storage).detach(document.id, file_id)
        assert db.get(Document, document.id).verification_status == "pending"

    def test_no_history_is_written(self, db, storage, attached):
        document, (file_id,), _ = attached("pending")
        FileService(db=db, storage=storage).detach(document.id, file_id)
        assert events_of(db, document.id) == []

    def test_the_blob_is_gone_from_storage(self, db, storage, attached):
        document, file_ids, keys = attached("pending", count=2)
        FileService(db=db, storage=storage).detach(document.id, file_ids[0])

        assert not storage.exists(keys[0])
        assert storage.exists(keys[1])
        assert len(files_on_disk(storage)) == 1

    def test_it_returns_nothing(self, db, storage, attached):
        document, (file_id,), _ = attached("pending")
        assert FileService(db=db, storage=storage).detach(document.id, file_id) is None

    def test_it_ends_its_own_transaction(self, db, storage, attached):
        document, (file_id,), _ = attached("pending")
        FileService(db=db, storage=storage).detach(document.id, file_id)
        assert not db.in_transaction()


class TestDetachWithdrawsAVerdict:
    @pytest.mark.parametrize(
        "was", ["verified", "rejected"], ids=["verified", "rejected"]
    )
    def test_the_document_returns_to_pending(self, db, storage, attached, was):
        document, (file_id,), _ = attached(was)
        FileService(db=db, storage=storage).detach(document.id, file_id)
        assert db.get(Document, document.id).verification_status == "pending"

    @pytest.mark.parametrize(
        "was", ["verified", "rejected"], ids=["verified", "rejected"]
    )
    def test_exactly_one_reopened_event_is_written(self, db, storage, attached, was):
        document, (file_id,), _ = attached(was)
        FileService(db=db, storage=storage).detach(document.id, file_id)

        written = events_of(db, document.id)
        assert len(written) == 2, "the earlier verdict must survive the reopen"

        reopened = [e for e in written if e.event_type == "reopened"]
        assert len(reopened) == 1
        assert reopened[0].reason == "file_deleted"
        assert reopened[0].from_status == was
        assert reopened[0].to_status == "pending"

    def test_the_row_and_the_event_are_one_transaction(
        self, db, storage, attached, other_session
    ):
        document, (file_id,), (key,) = attached("verified")
        FileService(db=db, storage=storage).detach(document.id, file_id)

        observer = other_session()
        assert observer.get(File, file_id) is None
        assert observer.get(Document, document.id).verification_status == "pending"
        assert len(events_of(observer, document.id)) == 2
        assert not storage.exists(key)

    def test_the_last_file_may_go(self, db, storage, attached):
        document, (file_id,), _ = attached("verified", count=1)
        FileService(db=db, storage=storage).detach(document.id, file_id)

        assert list(db.scalars(select(File).where(File.document_id == document.id))) == []
        assert db.get(Document, document.id).verification_status == "pending"
        reopened = [e for e in events_of(db, document.id) if e.event_type == "reopened"]
        assert len(reopened) == 1

    def test_one_of_several_files_leaves_the_rest(self, db, storage, attached):
        document, file_ids, keys = attached("verified", count=3)
        FileService(db=db, storage=storage).detach(document.id, file_ids[1])

        remaining = list(
            db.scalars(
                select(File.id)
                .where(File.document_id == document.id)
                .order_by(File.id)
            )
        )
        assert remaining == [file_ids[0], file_ids[2]]
        assert not storage.exists(keys[1])
        assert storage.exists(keys[0]) and storage.exists(keys[2])

    def test_only_the_first_detach_reopens(self, db, storage, attached):
        document, file_ids, _ = attached("verified", count=2)
        service = FileService(db=db, storage=storage)

        service.detach(document.id, file_ids[0])
        service.detach(document.id, file_ids[1])

        assert db.get(Document, document.id).verification_status == "pending"
        reopened = [e for e in events_of(db, document.id) if e.event_type == "reopened"]
        assert len(reopened) == 1, "the second detach found nothing left to withdraw"

    def test_a_fresh_verdict_is_withdrawn_again(self, db, storage, attached):
        document, file_ids, _ = attached("verified", count=2)
        service = FileService(db=db, storage=storage)
        service.detach(document.id, file_ids[0])

        DocumentService.verify(db, document.id, "повторная проверка")
        db.rollback()  # `verify` finishes with a refresh, which opens a transaction

        service.detach(document.id, file_ids[1])
        reopened = [e for e in events_of(db, document.id) if e.event_type == "reopened"]
        assert [e.reason for e in reopened] == ["file_deleted", "file_deleted"]

    def test_a_file_added_by_attach_can_be_detached(self, db, storage, document):
        service = FileService(db=db, storage=storage)
        file = service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES))
        # reading the expired attributes reopens a transaction, and in
        # production these would be two requests with two sessions anyway
        file_id, key = file.id, file.storage_key
        db.rollback()

        service.detach(document.id, file_id)

        assert db.get(File, file_id) is None
        assert not storage.exists(key)
        assert db.get(Document, document.id).verification_status == "pending"


class TestDetachRefusals:
    def test_a_missing_file_is_refused(self, db, storage, attached):
        document, _, _ = attached("verified")
        with pytest.raises(AttachmentNotFoundError):
            FileService(db=db, storage=storage).detach(document.id, 999_999)

    def test_nothing_changes_when_the_file_is_missing(self, db, storage, attached):
        document, (file_id,), (key,) = attached("verified")
        with pytest.raises(AttachmentNotFoundError):
            FileService(db=db, storage=storage).detach(document.id, 999_999)

        assert db.get(File, file_id) is not None
        assert storage.exists(key)
        assert db.get(Document, document.id).verification_status == "verified"
        assert len(events_of(db, document.id)) == 1

    def test_a_file_of_another_document_is_refused(self, db, storage, attached):
        first, (first_file,), _ = attached("verified")
        second, (second_file,), _ = attached("verified")

        with pytest.raises(AttachmentNotFoundError):
            FileService(db=db, storage=storage).detach(first.id, second_file)

    def test_the_other_document_is_untouched_by_that_refusal(self, db, storage, attached):
        first, (first_file,), (first_key,) = attached("verified")
        second, (second_file,), (second_key,) = attached("verified")

        with pytest.raises(AttachmentNotFoundError):
            FileService(db=db, storage=storage).detach(first.id, second_file)

        assert db.get(File, second_file) is not None
        assert storage.exists(second_key)
        assert db.get(Document, second.id).verification_status == "verified"
        assert len(events_of(db, second.id)) == 1

    def test_the_refused_file_of_the_first_document_survives(self, db, storage, attached):
        first, (first_file,), (first_key,) = attached("verified")
        second, (second_file,), _ = attached("verified")

        with pytest.raises(AttachmentNotFoundError):
            FileService(db=db, storage=storage).detach(first.id, second_file)

        assert db.get(File, first_file) is not None
        assert storage.exists(first_key)

    def test_a_repeated_detach_is_refused(self, db, storage, attached):
        document, (file_id,), _ = attached("verified")
        service = FileService(db=db, storage=storage)
        service.detach(document.id, file_id)

        with pytest.raises(AttachmentNotFoundError):
            service.detach(document.id, file_id)

    def test_a_repeated_detach_adds_no_second_event(self, db, storage, attached):
        document, (file_id,), _ = attached("verified")
        service = FileService(db=db, storage=storage)
        service.detach(document.id, file_id)
        with pytest.raises(AttachmentNotFoundError):
            service.detach(document.id, file_id)

        reopened = [e for e in events_of(db, document.id) if e.event_type == "reopened"]
        assert len(reopened) == 1

    def test_a_missing_document_is_refused(self, db, storage):
        with pytest.raises(DocumentNotFoundError):
            FileService(db=db, storage=storage).detach(999_999, 1)

    def test_a_missing_document_does_not_touch_any_file(self, db, storage, attached):
        document, (file_id,), (key,) = attached("verified")
        with pytest.raises(DocumentNotFoundError):
            FileService(db=db, storage=storage).detach(999_999, file_id)

        assert db.get(File, file_id) is not None
        assert storage.exists(key)

    def test_a_missing_document_does_not_touch_the_named_document(self, db, storage, attached):
        document, (file_id,), _ = attached("verified")
        with pytest.raises(DocumentNotFoundError):
            FileService(db=db, storage=storage).detach(document.id + 1000, file_id)
        assert db.get(Document, document.id).verification_status == "verified"

    def test_a_refusal_ends_its_own_transaction(self, db, storage, attached):
        document, _, _ = attached("verified")
        with pytest.raises(AttachmentNotFoundError):
            FileService(db=db, storage=storage).detach(document.id, 999_999)
        assert not db.in_transaction()


class TestTheDetachTransactionGuard:
    def test_an_open_transaction_is_refused(self, db, storage, attached):
        document, (file_id,), (key,) = attached("verified")
        db.execute(text("SELECT 1"))

        with pytest.raises(TransactionAlreadyOpenError):
            FileService(db=db, storage=storage).detach(document.id, file_id)

        assert storage.exists(key)

    def test_the_caller_transaction_is_left_open(self, db, storage, attached):
        document, (file_id,), _ = attached("verified")
        db.execute(text("SELECT 1"))

        with pytest.raises(TransactionAlreadyOpenError):
            FileService(db=db, storage=storage).detach(document.id, file_id)

        assert db.in_transaction(), "the caller's transaction must not be ended"

    def test_the_caller_staged_work_is_not_committed(
        self, db, storage, attached, other_session
    ):
        document, (file_id,), _ = attached("verified")
        db.add(Document(document_type=DocumentType(name="Чужой"), number="FOREIGN"))

        with pytest.raises(TransactionAlreadyOpenError):
            FileService(db=db, storage=storage).detach(document.id, file_id)

        observer = other_session()
        assert observer.scalars(
            select(Document.number).where(Document.number == "FOREIGN")
        ).all() == []

    def test_the_refusal_changes_nothing(self, db, storage, attached):
        document, (file_id,), (key,) = attached("verified")
        db.execute(text("SELECT 1"))

        with pytest.raises(TransactionAlreadyOpenError):
            FileService(db=db, storage=storage).detach(document.id, file_id)

        assert db.get(File, file_id) is not None
        assert storage.exists(key)
        assert db.get(Document, document.id).verification_status == "verified"
        assert len(events_of(db, document.id)) == 1

    def test_the_refusal_names_no_file(self, db, storage, attached):
        document, (file_id,), _ = attached("verified")
        db.execute(text("SELECT 1"))
        with pytest.raises(TransactionAlreadyOpenError) as info:
            FileService(db=db, storage=storage).detach(document.id, file_id)
        assert "existing-0" not in str(info.value)


class TestDetachReleasesTheLock:
    """A refusal must not keep the document locked.

    The document lock is taken before the file is even looked at, so every early
    refusal has to hand it back. Otherwise one refused detach makes every other
    operation on that document wait for as long as the caller's session lives.
    """

    @staticmethod
    def _file_is_free(sessions, file_id):
        probe = sessions()
        probe.execute(text("SET lock_timeout = '400ms'"))
        probe.execute(
            text("SELECT 1 FROM files WHERE id = :i FOR UPDATE"), {"i": file_id}
        )
        probe.rollback()
        probe.close()

    @staticmethod
    def _document_is_free(sessions, document_id):
        probe = sessions()
        probe.execute(text("SET lock_timeout = '400ms'"))
        probe.execute(
            text("SELECT 1 FROM documents WHERE id = :i FOR UPDATE"),
            {"i": document_id},
        )
        probe.rollback()
        probe.close()

    def test_after_a_successful_detach(self, db, storage, attached, other_session):
        document, file_ids, _ = attached("verified", count=2)
        FileService(db=db, storage=storage).detach(document.id, file_ids[0])

        self._document_is_free(other_session, document.id)

    def test_after_a_missing_file(self, db, storage, attached, other_session):
        document, _, _ = attached("verified")
        with pytest.raises(AttachmentNotFoundError):
            FileService(db=db, storage=storage).detach(document.id, 999_999)

        self._document_is_free(other_session, document.id)

    def test_after_a_foreign_file(self, db, storage, attached, other_session):
        first, _, _ = attached("verified")
        second, (second_file,), _ = attached("verified")

        with pytest.raises(AttachmentNotFoundError):
            FileService(db=db, storage=storage).detach(first.id, second_file)

        self._document_is_free(other_session, first.id)
        self._file_is_free(other_session, second_file)

    def test_after_a_missing_document(self, db, storage, attached, other_session):
        document, (file_id,), _ = attached("verified")
        with pytest.raises(DocumentNotFoundError):
            FileService(db=db, storage=storage).detach(999_999, file_id)
        self._file_is_free(other_session, file_id)

    def test_another_document_can_still_be_locked(self, db, storage, attached, other_session):
        first, _, _ = attached("verified")
        second, (second_file,), _ = attached("verified")

        with pytest.raises(AttachmentNotFoundError):
            FileService(db=db, storage=storage).detach(first.id, 999_999)

        self._document_is_free(other_session, second.id)
        self._file_is_free(other_session, second_file)

    def test_after_a_failed_commit(self, db, storage, attached, other_session):
        document, (file_id,), _ = attached("verified")

        class CommitFails:
            def __init__(self, inner):
                self._inner = inner

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def execute(self, *args, **kwargs):
                return self._inner.execute(*args, **kwargs)

            def scalar(self, *args, **kwargs):
                return self._inner.scalar(*args, **kwargs)

            def add(self, instance):
                self._inner.add(instance)

            def delete(self, instance):
                self._inner.delete(instance)

            def flush(self):
                self._inner.flush()

            def in_transaction(self):
                return False

            def commit(self):
                raise OperationalError("COMMIT", {}, Exception("server went away"))

            def rollback(self):
                self._inner.rollback()

        service = FileService(db=CommitFails(db), storage=storage)
        with pytest.raises(OperationalError):
            service.detach(document.id, file_id)

        assert not db.in_transaction(), "the failed call must still end its transaction"
        self._document_is_free(other_session, document.id)
        self._file_is_free(other_session, file_id)


class TestCommitOutcomesForDetach:
    """A failed commit never authorises deleting the blob.

    `detach` cannot arbitrate the way `attach` does. There, a surviving row
    means the blob is still needed and a missing row means it is an orphan, so
    the database can be asked. Here the row's absence is exactly what a
    successful detach looks like, so the same question has two readings and only
    one safe answer: keep the blob. A leftover blob is recoverable by
    reconciliation; a blob deleted under a row that survived is gone.
    """

    class CommitFails:
        def __init__(self, inner, error):
            self._inner = inner
            self._error = error

        def get(self, *args, **kwargs):
            return self._inner.get(*args, **kwargs)

        def execute(self, *args, **kwargs):
            return self._inner.execute(*args, **kwargs)

        def scalar(self, *args, **kwargs):
            return self._inner.scalar(*args, **kwargs)

        def add(self, instance):
            self._inner.add(instance)

        def delete(self, instance):
            self._inner.delete(instance)

        def flush(self):
            self._inner.flush()

        def in_transaction(self):
            return False

        def commit(self):
            raise self._error

        def rollback(self):
            self._inner.rollback()

    class LandedThenReportedAsFailed(CommitFails):
        """The server accepted the transaction and only then did the client fail."""

        def commit(self):
            self._inner.commit()
            raise self._error

    @staticmethod
    def _operational():
        return OperationalError("COMMIT", {}, Exception("server closed the connection"))

    def _detach_with(self, db, storage, document, file_id, double, error):
        service = FileService(db=double(db, error), storage=storage)
        with pytest.raises(Exception):
            service.detach(document.id, file_id)

    def test_a_connection_error_keeps_the_blob_and_the_row(
        self, db, storage, attached
    ):
        document, (file_id,), (key,) = attached("verified")
        self._detach_with(
            db, storage, document, file_id, self.CommitFails, self._operational()
        )

        assert list(db.scalars(select(File).where(File.id == file_id))) != []
        assert storage.exists(key)
        assert db.get(Document, document.id).verification_status == "verified"
        assert len(events_of(db, document.id)) == 1

    def test_a_refused_transaction_is_treated_the_same_way(self, db, storage, attached):
        document, (file_id,), (key,) = attached("verified")
        self._detach_with(
            db,
            storage,
            document,
            file_id,
            self.CommitFails,
            IntegrityError("COMMIT", {}, Exception("duplicate key value")),
        )

        assert storage.exists(key)
        assert db.get(Document, document.id).verification_status == "verified"

    @pytest.mark.parametrize(
        "make_error",
        [
            _operational,
            lambda: IntegrityError("COMMIT", {}, Exception("dup")),
            lambda: InterfaceError("COMMIT", {}, Exception("closed")),
            lambda: RuntimeError("plain"),
        ],
        ids=["operational", "integrity", "interface", "runtime"],
    )
    def test_the_error_class_alone_does_not_decide(
        self, db, storage, attached, make_error
    ):
        document, (file_id,), (key,) = attached("verified")
        self._detach_with(db, storage, document, file_id, self.CommitFails, make_error())

        assert storage.exists(key), "no exception class proves the blob is an orphan"
        assert db.get(Document, document.id).verification_status == "verified"

    def test_an_unconfirmed_commit_is_reported_for_reconciliation(
        self, db, storage, attached, caplog
    ):
        document, (file_id,), _ = attached("verified")
        self._detach_with(
            db, storage, document, file_id, self.CommitFails, self._operational()
        )

        record = caplog.records[-1]
        assert record.failure_category == "unknown_commit_outcome"
        assert record.operation == "file.detach"
        assert record.document_id == document.id
        assert record.error_type == "OperationalError"

    def test_the_original_error_reaches_the_caller(self, db, storage, attached):
        document, (file_id,), _ = attached("verified")
        service = FileService(
            db=self.CommitFails(db, self._operational()), storage=storage
        )
        with pytest.raises(OperationalError, match="server closed the connection"):
            service.detach(document.id, file_id)

    def test_a_commit_that_landed_keeps_the_blob_too(self, db, storage, attached, caplog):
        document, (file_id,), (key,) = attached("verified")
        self._detach_with(
            db,
            storage,
            document,
            file_id,
            self.LandedThenReportedAsFailed,
            self._operational(),
        )

        # the row really did go, so the blob is now an orphan — deliberately not
        # deleted, because the caller cannot be told which way the commit went
        assert list(db.scalars(select(File).where(File.id == file_id))) == []
        assert storage.exists(key), "an unconfirmed outcome must not remove the blob"
        assert caplog.records[-1].failure_category == "unknown_commit_outcome"

    def test_second_commit_is_never_attempted(self, db, storage, attached):
        calls = {"n": 0}

        class CountsCommits(self.CommitFails):
            def commit(self):
                calls["n"] += 1
                super().commit()

        document, (file_id,), _ = attached("verified")
        self._detach_with(
            db, storage, document, file_id, CountsCommits, self._operational()
        )
        assert calls["n"] == 1


class TestTheBlobGoesOnlyAfterTheCommit:
    def test_a_failing_blob_removal_still_reports_success(self, db, storage, attached):
        document, (file_id,), (key,) = attached("verified")

        class RefusesToDelete:
            def __init__(self, inner):
                self._inner = inner

            def save(self, storage_key, source):
                return self._inner.save(storage_key, source)

            def exists(self, storage_key):
                return self._inner.exists(storage_key)

            def open(self, storage_key):
                return self._inner.open(storage_key)

            def delete(self, storage_key):
                raise StorageError("permission denied")

        service = FileService(db=db, storage=RefusesToDelete(storage))
        assert service.detach(document.id, file_id) is None, (
            "the database did what was asked; the blob is a reconciliation problem"
        )

        assert storage.exists(key), "the blob is left for a later sweep"
        assert db.get(Document, document.id).verification_status == "pending"

    def test_the_row_is_not_restored_by_a_failing_blob_removal(
        self, db, storage, attached, other_session
    ):
        document, (file_id,), _ = attached("verified")

        class RefusesToDelete:
            def __init__(self, inner):
                self._inner = inner

            def save(self, storage_key, source):
                return self._inner.save(storage_key, source)

            def exists(self, storage_key):
                return self._inner.exists(storage_key)

            def open(self, storage_key):
                return self._inner.open(storage_key)

            def delete(self, storage_key):
                raise StorageError("permission denied")

        FileService(db=db, storage=RefusesToDelete(storage)).detach(
            document.id, file_id
        )

        observer = other_session()
        assert observer.get(File, file_id) is None
        assert observer.get(Document, document.id).verification_status == "pending"

    def test_the_failure_is_logged_with_a_safe_category(self, db, storage, attached, caplog):
        document, (file_id,), _ = attached("verified")

        class RefusesToDelete:
            def __init__(self, inner):
                self._inner = inner

            def save(self, storage_key, source):
                return self._inner.save(storage_key, source)

            def exists(self, storage_key):
                return self._inner.exists(storage_key)

            def open(self, storage_key):
                return self._inner.open(storage_key)

            def delete(self, storage_key):
                raise StorageError("permission denied")

        FileService(db=db, storage=RefusesToDelete(storage)).detach(
            document.id, file_id
        )

        record = caplog.records[-1]
        assert record.failure_category == "blob_removal_failed"
        assert record.operation == "file.detach"
        assert record.storage_key.startswith(f"documents/{document.id}/")
        assert record.error_type == "StorageError"

    def test_the_blob_is_still_there_when_the_commit_fails(self, db, storage, attached):
        document, (file_id,), (key,) = attached("verified")

        class CommitFails(TestCommitOutcomesForDetach.CommitFails):
            pass

        service = FileService(
            db=CommitFails(db, RuntimeError("commit refused")), storage=storage
        )
        with pytest.raises(RuntimeError):
            service.detach(document.id, file_id)

        assert storage.exists(key)
        assert db.get(File, file_id) is not None


class TestDetachTouchesNothingElse:
    def test_another_document_keeps_its_files_and_status(self, db, storage, attached):
        first, (first_file,), _ = attached("verified")
        second, second_files, second_keys = attached("rejected", count=2)

        FileService(db=db, storage=storage).detach(first.id, first_file)

        assert db.get(Document, second.id).verification_status == "rejected"
        assert list(
            db.scalars(
                select(File.id)
                .where(File.document_id == second.id)
                .order_by(File.id)
            )
        ) == second_files
        assert all(storage.exists(k) for k in second_keys)
        assert len(events_of(db, second.id)) == 1

    def test_the_other_file_of_the_same_document_is_untouched(self, db, storage, attached):
        document, file_ids, keys = attached("pending", count=2)
        FileService(db=db, storage=storage).detach(document.id, file_ids[0])

        other = db.get(File, file_ids[1])
        assert other.storage_key == keys[1]
        assert other.original_filename == "existing-1.pdf"
        assert storage.exists(keys[1])


class TestTheLogRecordsCarryNoFreeText:
    """Section 7: never log arbitrary `str(error)`.

    A SQLAlchemy error string carries the failing statement and its parameters,
    and those parameters include the storage key, the original filename and the
    free-text reason of a human verdict. The record keeps the category and the
    error **type**, which is what recognition needs.
    """

    def _source(self):
        import pathlib

        return pathlib.Path("app/services/file_service.py").read_text()

    def test_report_carries_no_error_detail(self):
        record = FileService._report(
            "file.detach", "unknown_commit_outcome", 1, "documents/1/x.pdf",
            RuntimeError("SECRET-MARKER"),
        )
        assert "error_detail" not in record
        assert "SECRET-MARKER" not in repr(record)
        assert record["error_type"] == "RuntimeError"

    def test_the_helper_still_names_the_operation_and_the_category(self):
        record = FileService._report(
            "file.detach", "blob_removal_failed", 7, "documents/7/y.pdf", None
        )
        assert record == {
            "operation": "file.detach",
            "document_id": 7,
            "storage_key": "documents/7/y.pdf",
            "failure_category": "blob_removal_failed",
            "error_type": None,
        }

    def test_the_module_never_formats_an_exception_into_a_record(self):
        # parsed rather than searched: the helper's docstring says the words
        # "str(error)" while explaining why it never does that
        tree = ast.parse(self._source())
        calls = [
            ast.unparse(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "str"
            and node.args
            and any(
                isinstance(arg, ast.Name) and arg.id.endswith("error")
                for arg in node.args
            )
        ]
        assert calls == [], f"an exception is being formatted into a string: {calls}"
        assert "error_detail" not in self._source()

    def test_a_verdict_reason_never_reaches_a_record(self, db, storage, attached, caplog):
        document, (file_id,), _ = attached("verified")

        class RefusesToDelete:
            def __init__(self, inner):
                self._inner = inner

            def save(self, storage_key, source):
                return self._inner.save(storage_key, source)

            def exists(self, storage_key):
                return self._inner.exists(storage_key)

            def open(self, storage_key):
                return self._inner.open(storage_key)

            def delete(self, storage_key):
                raise StorageError("permission denied for documents/1/existing-0.pdf")

        FileService(db=db, storage=RefusesToDelete(storage)).detach(
            document.id, file_id
        )

        record = caplog.records[-1]
        assert "permission denied" not in record.getMessage()
        assert "existing-0.pdf" not in record.getMessage()

    def test_no_password_from_the_environment_appears_in_the_module(self):
        import os

        source = self._source()
        for name in ("POSTGRES_PASSWORD", "DATABASE_URL", "DB_PASSWORD"):
            secret = os.environ.get(name)
            assert not secret or secret not in source, f"{name} leaked into the module"


class TestAttachAndUploadStillBehave:
    def test_attach_still_reopens_a_verdict(self, db, storage, attached):
        document, _, _ = attached("verified")
        FileService(db=db, storage=storage).attach(
            document.id, "new.pdf", io.BytesIO(PDF_BYTES)
        )
        reopened = [e for e in events_of(db, document.id) if e.event_type == "reopened"]
        assert [e.reason for e in reopened] == ["file_added"]

    def test_upload_still_refuses_an_open_transaction(self, db, storage, document):
        db.execute(text("SELECT 1"))
        with pytest.raises(TransactionAlreadyOpenError):
            FileService(db=db, storage=storage).upload(
                document.id, "scan.pdf", io.BytesIO(PDF_BYTES)
            )

    def test_attach_log_records_still_carry_the_operation(self, db, storage, document, caplog):
        class CommitFails:
            def __init__(self, inner, error):
                self._inner = inner
                self._error = error

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def execute(self, *args, **kwargs):
                return self._inner.execute(*args, **kwargs)

            def scalar(self, *args, **kwargs):
                # the session cannot say whether the row landed, which is the
                # one attach outcome that has to be written down
                raise OperationalError("SELECT", {}, Exception("gone"))

            def add(self, instance):
                self._inner.add(instance)

            def flush(self):
                self._inner.flush()

            def in_transaction(self):
                return False

            def commit(self):
                raise RuntimeError("commit refused")

            def rollback(self):
                self._inner.rollback()

        with pytest.raises(RuntimeError):
            FileService(
                db=CommitFails(db, RuntimeError("x")), storage=storage
            ).attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES))

        record = caplog.records[-1]
        assert record.operation == "file.attach"
        assert record.failure_category == "unknown_commit_outcome"


class TestTheBuiltinFileNotFoundErrorIsNotShadowed:
    """Why the domain error is called `AttachmentNotFoundError`.

    It was once called `FileNotFoundError`, which is also the builtin raised by
    `open()`. Both names lived in the same module, so an `except
    FileNotFoundError` written in `file_service` later would have caught the
    domain error while reading like it caught the OS one — a mistake invisible
    at the point it was made. The rename removes the collision; these
    assertions keep it removed.
    """

    def test_the_module_no_longer_exports_the_shadowing_name(self):
        from app.services import file_service

        assert not hasattr(file_service, "FileNotFoundError"), (
            "the module must not publish a name that belongs to a builtin"
        )

    def test_no_builtin_exception_is_shadowed_by_a_domain_one(self):
        import builtins

        from app.services import file_service

        shadowed = [
            name
            for name, value in vars(file_service).items()
            if isinstance(value, type)
            and issubclass(value, BaseException)
            and getattr(builtins, name, None) is not None
            and getattr(builtins, name) is not value
        ]
        assert shadowed == [], f"builtin exceptions shadowed: {shadowed}"

    def test_the_two_errors_are_related_to_nothing_but_themselves(self):
        import builtins

        assert AttachmentNotFoundError is not builtins.FileNotFoundError
        assert not issubclass(AttachmentNotFoundError, builtins.FileNotFoundError)
        assert not issubclass(builtins.FileNotFoundError, AttachmentNotFoundError), (
            "catching the builtin must never catch the domain error"
        )

    def test_the_domain_error_is_still_a_file_service_error(self):
        assert issubclass(AttachmentNotFoundError, FileServiceError)

    def test_the_domain_error_is_what_detach_raises(self, db, storage, attached):
        document, _, _ = attached("verified")
        with pytest.raises(AttachmentNotFoundError) as info:
            FileService(db=db, storage=storage).detach(document.id, 999_999)
        assert type(info.value) is AttachmentNotFoundError

    def test_a_storage_raising_the_builtin_is_not_translated(
        self, db, storage, document
    ):
        """`open()` failing is an OS condition, not a statement about attachments.

        The proof uses a storage whose `save` raises the builtin: it has to come
        back to the caller as the builtin, not converted into the domain error.
        """

        class SaveRaisesTheBuiltin:
            def __init__(self, inner):
                self._inner = inner

            def save(self, storage_key, source):
                raise FileNotFoundError("no such file or directory")

            def exists(self, storage_key):
                return self._inner.exists(storage_key)

            def open(self, storage_key):
                return self._inner.open(storage_key)

            def delete(self, storage_key):
                return self._inner.delete(storage_key)

        service = FileService(db=db, storage=SaveRaisesTheBuiltin(storage))
        with pytest.raises(FileNotFoundError) as info:
            service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES))

        assert type(info.value) is FileNotFoundError, (
            "the builtin must not be translated into a domain error"
        )
