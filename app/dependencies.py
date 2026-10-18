"""FastAPI dependencies that assemble services for a request.

This is the single place where a service is built with its collaborators and
bound to the request's session. Routers depend on the factory here rather than
constructing a service themselves, so every request gets the same wiring and a
test can replace any part of it with `app.dependency_overrides`.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.connection import get_db
from app.services.file_service import FileService
from app.services.local_storage import LocalStorageBackend
from app.services.storage import StorageBackend


def get_file_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileService:
    """Assemble a FileService over the request session and the settings.

    The session is the one `get_db` yields; the service never opens its own.
    Sharing the request's session is what lets a file write and the document it
    touches land in a single transaction — `attach` and `detach` put the file
    row, the reopened `verification_status` and the history event into one
    `commit`, and a second session would split them across two.

    Nothing here runs SQL or opens a transaction, and that is a requirement
    rather than an optimisation: `attach` and `detach` refuse a session that
    already has a transaction on entry (`TransactionAlreadyOpenError`), so a
    dependency that started one would turn every file request into a conflict.
    The session is handed over exactly as `get_db` produced it.

    `STORAGE_ROOT` and `MAX_UPLOAD_SIZE_BYTES` are read here, which is where
    ADR-009 places them: until now both settings were declared but used by no
    production code.

    Every part is replaceable. Tests can override `get_db` (already the
    project's habit), `get_settings`, or this function as a whole to point the
    service at a scratch schema and a temporary storage root.
    """
    return FileService(
        db,
        LocalStorageBackend(root_path=settings.STORAGE_ROOT),
        max_upload_size_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
    )


def get_storage(
    settings: Annotated[Settings, Depends(get_settings)],
) -> StorageBackend:
    """Open the blob storage that the download route reads from.

    This is a second dependency rather than a method on `FileService`: the write
    service keeps its backend private, and a download needs nothing from the
    service but `open()`. Building a backend here also keeps the route free of
    storage wiring, and returning the `StorageBackend` interface rather than
    `LocalStorageBackend` lets a test substitute a stream that records how it
    was read without touching the filesystem.

    The service builds its own `LocalStorageBackend` over the same
    `STORAGE_ROOT`. Two instances over one root are interchangeable — the
    backend holds only the resolved path — so a file written through the
    service is readable here.

    Like `get_file_service`, this runs no SQL and opens no transaction: it only
    resolves the configured root, and the settings are validated at startup.
    """
    return LocalStorageBackend(root_path=settings.STORAGE_ROOT)
