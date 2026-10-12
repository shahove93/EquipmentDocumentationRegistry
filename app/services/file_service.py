import hashlib
import uuid
from datetime import datetime, timezone
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.file import File
from app.services.storage import StorageBackend

CHUNK_SIZE = 64 * 1024
DEFAULT_MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024

SIGNATURES = (
    (b"%PDF-", "application/pdf", "pdf"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
)

MAX_ORIGINAL_FILENAME_LENGTH = 255


class FileServiceError(Exception):
    """Base error for FileService operations."""


class FileValidationError(FileServiceError):
    """Input file or its metadata failed validation."""


class UnsupportedFileTypeError(FileServiceError):
    """Detected content type is not allowed."""


class FileTooLargeError(FileServiceError):
    """Input file exceeds the configured size limit."""


class DocumentNotFoundError(FileServiceError):
    """Requested document does not exist."""


class _PrefixStream:
    """Replay an already-consumed prefix, then the rest of the source."""

    def __init__(self, prefix: bytes, source: BinaryIO) -> None:
        self._prefix = prefix
        self._source = source
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunks = []
            while True:
                chunk = self.read(CHUNK_SIZE)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)

        if self._offset < len(self._prefix):
            end = min(len(self._prefix), self._offset + size)
            chunk = self._prefix[self._offset : end]
            self._offset = end
            return chunk

        return self._source.read(size - (self._offset - len(self._prefix)))


class _HashingStream:
    """Pass-through stream that digests and measures on the fly."""

    def __init__(self, source: BinaryIO, limit: int) -> None:
        self._source = source
        self._limit = limit
        self._digest = hashlib.sha256()
        self.size_bytes = 0

    @property
    def hexdigest(self) -> str:
        return self._digest.hexdigest()

    def read(self, size: int = -1) -> bytes:
        chunk = self._source.read(size)
        if not chunk:
            return b""
        self.size_bytes += len(chunk)
        if self.size_bytes > self._limit:
            raise FileTooLargeError(
                f"file exceeds the maximum upload size of {self._limit} bytes"
            )
        self._digest.update(chunk)
        return chunk


class FileService:
    """Validate uploads, store blobs and register File rows."""

    def __init__(
        self,
        db: Session,
        storage: StorageBackend,
        max_upload_size_bytes: int = DEFAULT_MAX_UPLOAD_SIZE_BYTES,
    ) -> None:
        self._db = db
        self._storage = storage
        self._max_upload_size_bytes = max_upload_size_bytes

    @property
    def max_upload_size_bytes(self) -> int:
        return self._max_upload_size_bytes

    def upload(
        self, document_id: int, original_filename: str, source: BinaryIO
    ) -> File:
        document = self._db.get(Document, document_id)
        if document is None:
            raise DocumentNotFoundError(
                f"document {document_id!r} does not exist"
            )

        display_name = self._validate_filename(original_filename)

        prefix = source.read(max(len(sig) for sig, _, _ in SIGNATURES))
        if not prefix:
            raise FileValidationError("file is empty")

        mime_type, extension = self._detect_type(prefix)
        if mime_type is None:
            raise UnsupportedFileTypeError(
                "unsupported file content; allowed types are PDF, JPEG and PNG"
            )

        storage_key = f"documents/{document_id}/{uuid.uuid4()}.{extension}"

        replay = _PrefixStream(prefix, source)
        measured = _HashingStream(replay, self._max_upload_size_bytes)

        self._storage.save(storage_key, measured)

        try:
            self._assert_not_empty(measured.size_bytes)
        except Exception:
            self._cleanup(storage_key)
            raise

        return self._register(
            storage_key, display_name, mime_type, measured, document_id
        )

    def _validate_filename(self, original_filename: str) -> str:
        if not isinstance(original_filename, str):
            raise FileValidationError("original_filename must be a string")
        if not original_filename.strip():
            raise FileValidationError("original_filename must not be empty")
        if "\x00" in original_filename:
            raise FileValidationError("original_filename must not contain NUL")
        if len(original_filename) > MAX_ORIGINAL_FILENAME_LENGTH:
            raise FileValidationError(
                f"original_filename must not exceed "
                f"{MAX_ORIGINAL_FILENAME_LENGTH} characters"
            )
        return original_filename

    @staticmethod
    def _detect_type(prefix: bytes) -> tuple[str | None, str]:
        for signature, mime_type, extension in SIGNATURES:
            if prefix.startswith(signature):
                return mime_type, extension
        return None, ""

    @staticmethod
    def _assert_not_empty(size_bytes: int) -> None:
        if size_bytes == 0:
            raise FileValidationError("file is empty")

    def _register(
        self,
        storage_key: str,
        display_name: str,
        mime_type: str,
        measured: "_HashingStream",
        document_id: int,
    ) -> File:
        file = File(
            document_id=document_id,
            original_filename=display_name,
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=measured.size_bytes,
            sha256=measured.hexdigest,
            uploaded_at=datetime.now(timezone.utc),
        )

        try:
            self._db.add(file)
            self._db.flush()
            self._db.commit()
        except Exception:
            self._db.rollback()
            self._cleanup(storage_key)
            raise

        return file

    def _cleanup(self, storage_key: str) -> None:
        try:
            self._storage.delete(storage_key)
        except Exception:
            pass

    def list_for_document(self, document_id: int) -> list[File]:
        statement = select(File).where(File.document_id == document_id).order_by(File.id)
        return list(self._db.scalars(statement))