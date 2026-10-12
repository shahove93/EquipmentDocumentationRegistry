import hashlib
import io
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.file import File
from app.services.file_service import (
    DocumentNotFoundError,
    FileService,
    FileServiceError,
    FileTooLargeError,
    FileValidationError,
    UnsupportedFileTypeError,
)
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
def document(db) -> Document:
    doc = Document(document_type=DocumentType(name="Паспорт"), number="D-1")
    db.add(doc)
    db.flush()
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

    def test_file_relationship_loaded(self, service, document):
        file = service.upload(document.id, "passport.pdf", io.BytesIO(PDF_BYTES))
        assert file.document is document
        assert document.files == [file]


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
        other = Document(document_type=DocumentType(name="Сертификат"), number="D-2")
        db.add(other)
        db.flush()
        mine = service.upload(document.id, "a.pdf", io.BytesIO(PDF_BYTES))
        theirs = service.upload(other.id, "b.pdf", io.BytesIO(PDF_BYTES))
        assert [f.id for f in service.list_for_document(document.id)] == [mine.id]
        assert [f.id for f in service.list_for_document(other.id)] == [theirs.id]