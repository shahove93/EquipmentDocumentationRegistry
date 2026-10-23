import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File as FormFile,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.files.download import (
    ClosingStreamingResponse,
    DownloadIntegrityError,
    content_disposition,
    prepare_verified_download,
)
from app.api.files.schemas import FileListOut, FileOut
from app.database.connection import get_db
from app.dependencies import get_file_service, get_storage
from app.models.file import File
from app.services.document_service import DocumentService
from app.services.file_service import (
    AttachmentNotFoundError,
    DocumentNotFoundError,
    FileService,
    FileTooLargeError,
    FileValidationError,
    PendingDocumentChangesError,
    TransactionAlreadyOpenError,
    UnsupportedFileTypeError,
)
from app.services.storage import StorageBackend, StorageError

logger = logging.getLogger(__name__)

# `File` is the ORM row; the multipart field declaration is imported as
# `FormFile` so the two cannot be mistaken for each other in this module.
#
# Every path is addressed through its document, so the router carries no prefix
# and declares them in full — the same arrangement as `variants`. ADR-009 fixes
# the shapes used here:
# `/documents/{document_id}/files` (POST, GET),
# `/documents/{document_id}/files/{file_id}` (GET, DELETE) and
# `/documents/{document_id}/files/{file_id}/content` (GET).
files_router = APIRouter(tags=["files"])


@files_router.post(
    "/documents/{document_id}/files",
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED,
    summary="Attach a file to a document",
    name="attach_document_file",
)
def attach_document_file(
    document_id: int,
    file: Annotated[UploadFile, FormFile(description="PDF, JPEG or PNG attachment")],
    response: Response,
    request: Request,
    service: Annotated[FileService, Depends(get_file_service)],
) -> FileOut:
    """Attach one uploaded file and return `201` with its metadata.

    The router does no file work of its own. `UploadFile.file` is handed to the
    service as a plain binary stream, and the service does the rest: it reads the
    signature, streams the body to storage in chunks while hashing it, enforces
    `MAX_UPLOAD_SIZE_BYTES`, and writes the file row, the document status and the
    history event in one transaction. Reading the upload with `await read()`
    here would defeat that streaming and hold the whole file in memory for no
    reason.

    Nothing in this function runs SQL before `attach`. That is a requirement,
    not a style: `attach` refuses a session that already has a transaction
    (`TransactionAlreadyOpenError`) and owns the one it starts. The dependencies
    are built without one — `get_db` only constructs a `Session`, and
    `get_file_service` only wraps it in a `LocalStorageBackend` — so the session
    reaches the service exactly as the request opened it.

    The filename comes from `UploadFile.filename` and is only a label. The
    declared content type is ignored: the service decides the type from the
    file's own signature, so a PDF named `.png` is still a PDF and an executable
    named `.pdf` is still refused. A missing filename is not corrected here — it
    is passed through (as `None`) and refused by the service as a validation
    error, so the rule lives in one place.

    Only the domain errors the service documents are translated, each to the
    status ADR-009 assigns it:

    - `DocumentNotFoundError` → `404`;
    - `FileTooLargeError` → `413`;
    - `FileValidationError`, `UnsupportedFileTypeError` → `422`;
    - `TransactionAlreadyOpenError`, `PendingDocumentChangesError` → `409`.

    Anything else propagates untouched and becomes the framework's generic
    `500`. That is deliberate: a storage or database failure is not a validation
    error, and dressing it up as `422` would tell the client to fix a request
    that was fine. The generic response carries no driver text, SQL or storage
    path.

    `Location` points at the metadata route of the new attachment, as ADR-009
    requires. FastAPI closes the uploaded file when it releases the form body
    after the response, so nothing is closed here by hand.
    """
    try:
        stored = service.attach(document_id, file.filename, file.file)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        ) from error
    except FileTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                "File exceeds the maximum upload size of "
                f"{service.max_upload_size_bytes} bytes"
            ),
        ) from error
    except (FileValidationError, UnsupportedFileTypeError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except TransactionAlreadyOpenError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The request conflicts with the current transaction state",
        ) from error
    except PendingDocumentChangesError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The document has uncommitted changes",
        ) from error

    response.headers["Location"] = str(
        request.url_for(
            "get_document_file",
            document_id=document_id,
            file_id=stored.id,
        )
    )
    return FileOut.model_validate(stored)


@files_router.get(
    "/documents/{document_id}/files",
    response_model=FileListOut,
    summary="List a document's attachments",
    name="list_document_files",
)
def list_document_files(
    document_id: int,
    service: Annotated[FileService, Depends(get_file_service)],
    db: Annotated[Session, Depends(get_db)],
) -> FileListOut:
    """Return the document's attachments as a bare JSON array, ordered by id.

    A document with no attachments is `200` with `[]`, not `404`: the document
    exists, so the collection exists and is merely empty. An unknown document is
    `404`, which is why existence is asked about separately — an empty listing
    cannot tell an empty document from a missing one.

    `service` and `db` share a single session: `get_file_service` depends on
    `get_db`, and FastAPI resolves a dependency once per request, so the
    existence check and the listing run on the same connection. The ordering is
    `File.id` ascending, which is what `list_for_document` already does; the
    service is reused rather than restated here.

    No row is locked. This request changes neither the status, nor the history,
    nor the set of attachments, so `SELECT ... FOR UPDATE` would hold a row for a
    reader that has nothing to serialise against.
    """
    if DocumentService.get(db, document_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return FileListOut.model_validate(service.list_for_document(document_id))


@files_router.get(
    "/documents/{document_id}/files/{file_id}",
    response_model=FileOut,
    summary="Get one attachment's metadata",
    name="get_document_file",
)
def get_document_file(
    document_id: int,
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> FileOut:
    """Return one attachment's metadata, or `404`.

    Ownership is decided by the query, not after it: the filter carries both
    `id` and `document_id`, so a file belonging to another document never comes
    back to the application at all. That is the difference between refusing to
    answer and answering and then hiding the answer — the second still lets a
    caller probe which file ids exist.

    Every miss shares one answer and one message: an unknown document, an
    unknown file and a file of another document all produce the same `404`
    wording. Telling them apart would turn this route into exactly the probe the
    query above is written to prevent. The same reasoning shapes
    `AttachmentNotFoundError` in the service layer.

    Metadata comes from the database alone; the blob in storage is not touched,
    so this route answers as long as the row exists.

    `db` is the session from `get_db`; no second session is opened.
    """
    file = db.scalar(
        select(File).where(File.id == file_id, File.document_id == document_id)
    )
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found for document {document_id}",
        )
    return FileOut.model_validate(file)


@files_router.get(
    "/documents/{document_id}/files/{file_id}/content",
    summary="Download one attachment's content",
    response_class=ClosingStreamingResponse,
    name="download_document_file",
    responses={
        200: {
            "description": (
                "The stored bytes, streamed in chunks with the MIME type "
                "recorded at upload."
            ),
            "content": {
                "application/pdf": {},
                "image/jpeg": {},
                "image/png": {},
            },
        }
    },
)
def download_document_file(
    document_id: int,
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> ClosingStreamingResponse:
    """Stream one attachment's stored bytes, or `404` if it is not here.

    Ownership is decided by the query, exactly as in `get_document_file`: the
    filter carries both `File.id` and `File.document_id`, so a file belonging to
    another document never reaches the application. All misses — unknown
    document, unknown file, another document's file — share one answer and one
    message, because distinguishing them would let a caller probe file ids.

    The row is selected without `FOR UPDATE`. This request reads; it changes no
    status, writes no history and touches no other row, so there is nothing to
    serialise against and a row lock would only make concurrent downloads wait.

    **The blob is opened and verified before the response starts.** The opened
    stream is copied into a private temporary snapshot while SHA-256 is counted
    over the same chunks, and the digest is compared with the row's `sha256`
    before `ClosingStreamingResponse` is built. Only the verified snapshot is
    streamed, so a blob that is replaced after the check cannot change the bytes
    a client receives. `storage.open` raises `StoredFileNotFoundError` when the
    row has outlived its content; a mismatch or any read, copy, flush or rewind
    failure is caught in the same place. All of them are answered while a status
    code can still be chosen; if the check were deferred into the stream, the
    headers would already have gone out and a broken store would look like a
    successful, empty download.

    A row without content or with content that does not match its digest is
    answered `500`, not `404`, and logged. The record exists; what is missing or
    wrong is the store's half of it, which is an integrity failure rather than an
    absent resource, and calling it `404` would blame the caller for a server
    fault. ADR-009 states the same rule: an absent row or a row belonging to
    another document is `404`, while a row whose blob is missing is a safe `500`
    with diagnostics. The message is fixed and says nothing about the storage
    key, the path or the digest, which is why none of the caught errors is
    echoed; each failure produces exactly one safe log record with a
    `failure_category` of `content_open_failed`, `sha256_mismatch` or
    `content_prepare_failed`.

    `Content-Type` is the MIME type recorded at upload, which `FileService`
    derived from the file's signature rather than from the client's claim.
    `Content-Disposition` is built by `content_disposition`, which keeps a
    hostile filename from becoming a second header.

    `Content-Length` is deliberately absent: ADR-009 rules that `size_bytes` was
    written at upload and may have drifted from the blob, so a length taken from
    the row could truncate a client; the body is sent chunked instead.

    The metadata is copied out of the row before the response is returned, and
    the stream never touches `db`, so the session may close while the body is
    still being sent. Nothing is committed or rolled back here. The storage
    descriptor is closed by `prepare_verified_download` before the response
    starts, and the snapshot descriptor is closed by `ClosingStreamingResponse`
    on every exit — a finished body, a failed `send` or a cancelled request —
    rather than only by `iter_blob` when the generator is exhausted.
    """
    file = db.scalar(
        select(File).where(File.id == file_id, File.document_id == document_id)
    )
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found for document {document_id}",
        )

    mime_type = file.mime_type
    original_filename = file.original_filename
    storage_key = file.storage_key
    expected_sha256 = file.sha256

    try:
        source = storage.open(storage_key)
    except (StorageError, OSError) as error:
        logger.error(
            "a file row exists but its content cannot be opened: storage and "
            "the database disagree",
            extra={
                "operation": "file.download",
                "document_id": document_id,
                "file_id": file_id,
                "failure_category": "content_open_failed",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored file content is unavailable",
        ) from error

    try:
        verified = prepare_verified_download(source, expected_sha256)
    except DownloadIntegrityError as error:
        logger.error(
            "a file row exists but its content does not match its recorded "
            "digest",
            extra={
                "operation": "file.download",
                "document_id": document_id,
                "file_id": file_id,
                "failure_category": "sha256_mismatch",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored file content is unavailable",
        ) from error
    except Exception as error:
        logger.error(
            "a file row exists but its content could not be prepared for "
            "download",
            extra={
                "operation": "file.download",
                "document_id": document_id,
                "file_id": file_id,
                "failure_category": "content_prepare_failed",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored file content is unavailable",
        ) from error

    return ClosingStreamingResponse(
        verified,
        media_type=mime_type,
        headers={"Content-Disposition": content_disposition(original_filename)},
    )


@files_router.delete(
    "/documents/{document_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Detach one attachment from a document",
    name="delete_document_file",
)
def delete_document_file(
    document_id: int,
    file_id: int,
    service: Annotated[FileService, Depends(get_file_service)],
) -> Response:
    """Remove one attachment and answer `204` with no body.

    The router does none of the work. `detach` owns the whole unit: it locks the
    document, then the file row, records the `reopened` event when the document
    had a verdict, deletes the row, commits, and only then removes the blob.
    Nothing is read here beforehand — a preliminary `SELECT` would open a
    transaction, and `detach` refuses a session that already has one
    (`TransactionAlreadyOpenError`), so the check would break the operation it
    was meant to guard. No session is opened, nothing is committed or rolled
    back, and `storage.delete` is never called from this layer.

    Every miss is a `404`: an unknown document, an unknown file, a file of
    another document and a second delete of the same file. A missing file and a
    foreign one share one message, word for word the same as the metadata and
    content routes, so the answer cannot reveal that a file exists elsewhere.
    The document case keeps its own message, as in `attach`.

    A session that arrives mid-transaction and a document with uncommitted
    changes are `409`, with the same texts the upload route uses.

    `204` means the database part is finished, not that every byte was
    reclaimed. If the commit was confirmed and the blob could not be removed,
    `detach` logs `blob_removal_failed` and returns, and this route still answers
    `204`: the row is gone and the operation the client asked for has happened.
    If the commit outcome is unknown, `detach` raises, the blob is deliberately
    kept for reconciliation, and the framework answers `500` — an operation whose
    fate is unknown is never reported as success. That error carries no driver
    text, SQL or storage path.

    The response is an explicit empty `Response` rather than `None`: FastAPI's
    default JSON response would attach `application/json` to a `204` and, with a
    return value, write a body the status forbids.
    """
    try:
        service.detach(document_id, file_id)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        ) from error
    except AttachmentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found for document {document_id}",
        ) from error
    except TransactionAlreadyOpenError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The request conflicts with the current transaction state",
        ) from error
    except PendingDocumentChangesError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The document has uncommitted changes",
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
