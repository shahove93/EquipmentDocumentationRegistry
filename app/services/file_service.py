import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.file import File
from app.services import transaction
from app.services.storage import StorageBackend
from app.services.verification_history import (
    REASON_FILE_ADDED,
    REASON_FILE_DELETED,
    record_reopened,
)

logger = logging.getLogger(__name__)

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


class AttachmentNotFoundError(FileServiceError):
    """The requested attachment is not a file of the requested document.

    Deliberately the same answer for "there is no such file" and "that file
    belongs to a different document". Telling those apart would turn the call
    into a way to ask whether some file id exists, which is not information a
    client needs and not information it should be able to get.

    The name is chosen so that it cannot be confused with the builtin
    `FileNotFoundError` raised by `open()`. An earlier revision called it
    `FileNotFoundError`, which shadowed the builtin inside this module: in code
    that opens files, `except FileNotFoundError` would have caught the domain
    error instead of the OS one, and the mistake would have been invisible at
    the point it was made. `StoredFileNotFoundError` in the storage layer avoids
    the same collision the same way.
    """


class TransactionAlreadyOpenError(FileServiceError):
    """The caller's session already had a transaction when the call was made.

    A finished operation must own its transaction, so this is refused rather than
    joined. Refusing is also the only answer that leaves the caller's own work
    alone: adopting the transaction would make this operation's `commit` decide
    the fate of changes the caller staged for its own reasons.

    Raised before any statement runs, so the session is left exactly as it was
    found — no rollback, no commit, no mutation.
    """


class PendingDocumentChangesError(FileServiceError):
    """The session holds uncommitted edits to the document about to be written.

    Taking the row lock refreshes the document from storage, and a refresh
    discards local edits rather than merging them. Losing them silently would be
    worse than refusing the call, so the shared locking read refuses first and
    this is what the caller is told.
    """

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(
            f"document {document_id} has uncommitted changes in this session; "
            f"commit or discard them before attaching a file"
        )


class StorageWrittenError(FileServiceError):
    """Staging failed after the blob was already written to storage.

    The file is in storage and the session holds nothing that a rollback would
    discard from the database, so the caller has a choice to make rather than a
    mess to clean up silently: compensate the blob, or keep it if the operation
    turns out to have succeeded. Reporting the key is what makes that choice
    possible — the caller cannot guess a UUID that was generated here.

    The original failure is kept as `__cause__`, so a caller that compensates
    can still re-raise what actually went wrong.
    """

    def __init__(self, storage_key: str) -> None:
        self.storage_key = storage_key
        super().__init__(
            f"file was written to storage but could not be staged: {storage_key!r}"
        )


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
        """Attach a file to a document. Retained for compatibility.

        A thin wrapper over `attach()`, which is the whole point: one code path
        for adding a file means the document lock, the transaction rules and the
        history of a reopened verdict cannot be bypassed by choosing the older
        method name.

        The signature is unchanged for its existing callers. What has changed is
        what it means — an upload to a `verified` or `rejected` document now
        returns that document to `pending` and records why, exactly as
        `attach()` does.
        """
        return self.attach(document_id, original_filename, source)

    def attach(
        self, document_id: int, original_filename: str, source: BinaryIO
    ) -> File:
        """Attach a file to a document as one finished unit of work.

        The file row, the document's `verification_status` and the history event
        that explains it are written by a **single** `commit`. Either all three
        land or none does; a document claiming to be reopened while its new scan
        is missing would be worse than either outcome alone.

        Adding a file to a `verified` or `rejected` document withdraws that
        verdict — the decision was made about a set of scans that no longer
        exists — so the document returns to `pending` with one `reopened` event
        carrying the machine reason `file_added`. A `pending` document has no
        verdict to withdraw, so it gains a file and nothing else.

        This method owns its transaction. A caller's session that already has
        one is refused before anything runs, because the alternative — adopting
        it — would let this operation's `commit` decide the fate of work the
        caller staged for its own reasons. Refusing also leaves that work
        untouched.

        The file system is not part of the database transaction, so a failure
        can leave a blob behind. What happens then is decided from evidence
        rather than from the kind of error that happened: before `commit` is
        called nothing can have been accepted, so the blob is removed; after
        `commit` fails the database is asked whether the row is there, and only
        a row that is demonstrably absent may be compensated.
        """
        if transaction.transaction_existed_on_entry(self._db):
            raise TransactionAlreadyOpenError(
                "the session already has a transaction; a file attach must own "
                "its own, so commit or roll back before calling attach()"
            )

        try:
            document = transaction.locked_document(self._db, document_id)
        except transaction.UncommittedChangesInSession as signal:
            # Deliberately no rollback. The guard fires before anything is
            # written, so there is nothing of ours to undo — and rolling back
            # would discard the very edits it exists to protect, along with
            # whatever else the caller had staged.
            raise PendingDocumentChangesError(signal.document_id) from signal

        if document is None:
            self._db.rollback()
            raise DocumentNotFoundError(
                f"document {document_id!r} does not exist"
            )

        try:
            file = self._stage_upload(document_id, original_filename, source)
        except StorageWrittenError as staged:
            # the commit was never reached, so nothing can have been accepted
            self._db.rollback()
            self._compensate(
                staged.storage_key, document_id, "staging_failed"
            )
            if staged.__cause__ is None:
                raise
            raise staged.__cause__
        except Exception:
            # Refused before a byte reached storage, so there is no blob to undo
            # — but the row lock still has to go. A lock held until the
            # caller's session happens to end would make every other operation
            # on this document wait for nothing.
            self._db.rollback()
            raise

        try:
            record_reopened(self._db, document, REASON_FILE_ADDED)
        except Exception:
            # still before the commit, so the same evidence applies
            self._db.rollback()
            self._compensate(file.storage_key, document_id, "history_failed")
            raise

        try:
            self._db.commit()
        except Exception as error:
            self._db.rollback()
            self._settle(file.storage_key, document_id, error)
            raise

        return file

    def detach(self, document_id: int, file_id: int) -> None:
        """Remove one attachment as a finished unit of work.

        The file row, the document's `verification_status` and the history event
        that explains it are written by a **single** `commit`, exactly as in
        `attach`. A document that still claimed a verdict over a scan that is
        gone, or a history entry describing a transition that never happened,
        would each be worse than either outcome alone.

        Removing a file from a `verified` or `rejected` document withdraws that
        verdict for the same reason adding one does: the decision was made about
        a set of scans that no longer exists. The document returns to `pending`
        with one `reopened` event carrying the machine reason `file_deleted`. A
        `pending` document has no verdict to withdraw, so it loses a file and
        nothing else. Removing the **last** file is allowed — the point of the
        operation is that the document is no longer verified, and a document
        with no scans cannot be.

        The blob leaves storage only **after** `commit` has returned. Until
        then the row still points at it, so deleting it early would risk
        destroying a file the database still refers to — and unlike `attach`,
        where a leftover blob can be arbitrated against the row, here a lost
        blob is simply lost. That asymmetry is why a failed `commit` keeps the
        blob without asking the database which way it went: the only safe
        reading of an unconfirmed commit is that the row may still exist.

        This method owns its transaction. A caller's session that already has
        one is refused before anything runs, for the same reason `attach`
        refuses: adopting it would let this operation's `commit` decide the fate
        of work the caller staged for its own reasons.
        """
        if transaction.transaction_existed_on_entry(self._db):
            raise TransactionAlreadyOpenError(
                "the session already has a transaction; a file detach must own "
                "its own, so commit or roll back before calling detach()"
            )

        try:
            document = transaction.locked_document(self._db, document_id)
        except transaction.UncommittedChangesInSession as signal:
            # As in `attach`: no rollback. The guard fires before anything is
            # written, and rolling back would discard the edits it protects.
            raise PendingDocumentChangesError(signal.document_id) from signal

        if document is None:
            self._db.rollback()
            raise DocumentNotFoundError(
                f"document {document_id!r} does not exist"
            )

        try:
            file = self._locked_file(document_id, file_id)
        except Exception:
            # A lock that could not be taken still has to be given back, and so
            # does the document lock taken a moment earlier.
            self._db.rollback()
            raise

        if file is None:
            elsewhere = self._file_owner(file_id)
            self._db.rollback()
            if elsewhere is not None:
                # Refused the same way as a missing file, so the client learns
                # nothing — but this is worth a record: a client asking for
                # another document's attachment is either broken or probing.
                logger.warning(
                    "a file was requested for the wrong document; the request "
                    "was refused and nothing was changed",
                    extra=self._report(
                        "file.detach",
                        "file_belongs_to_another_document",
                        document_id,
                        None,
                        None,
                    ),
                )
            raise AttachmentNotFoundError(
                f"file {file_id!r} is not an attachment of document "
                f"{document_id!r}"
            )

        storage_key = file.storage_key

        try:
            record_reopened(self._db, document, REASON_FILE_DELETED)
            self._db.delete(file)
        except Exception:
            # Nothing has left the database, so the blob matches its row and
            # must be left alone.
            self._db.rollback()
            raise

        try:
            self._db.commit()
        except Exception as error:
            # A failed commit proves nothing about what the server did, and
            # `rollback()` cannot undo a commit that was already accepted. The
            # blob is therefore kept: if the row did go, a leftover blob is
            # recoverable by reconciliation, whereas a blob deleted for a row
            # that survived is lost for good. The transaction still has to be
            # ended, or the document lock would outlive the call.
            self._db.rollback()
            logger.error(
                "file detach could not confirm its commit; the blob is kept and "
                "the row needs reconciliation",
                extra=self._report(
                    "file.detach",
                    "unknown_commit_outcome",
                    document_id,
                    storage_key,
                    error,
                ),
            )
            raise

        self._discard_blob(storage_key, document_id)

    def _locked_file(self, document_id: int, file_id: int) -> File | None:
        """Find the file **and** lock its row, after the document is locked.

        Both identifiers are in the filter, so an attachment of another document
        is not found here rather than being detached from the wrong document.

        `with_for_update` locks the row in the same statement that reads it, so
        there is no window between reading `storage_key` and holding the row it
        belongs to. `populate_existing` refreshes an instance this session
        already holds, for the same reason the document lock does: a stale key
        would send the later physical delete after the wrong blob.

        The order is document first, then file, matching `attach` — which locks
        the document and only then inserts a file row. Taking them the other way
        round is the textbook way to deadlock two operations that each want both.
        """
        statement = (
            select(File)
            .where(File.id == file_id, File.document_id == document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self._db.execute(statement).scalar_one_or_none()

    def _file_owner(self, file_id: int) -> int | None:
        """Which document owns `file_id`, if any at all.

        Asked only after the locking lookup found nothing, and only so that the
        log can tell a plain "no such file" from "that one is not yours". It
        decides nothing: both answers are refused identically, so a race that
        changes this value cannot change what the caller sees.
        """
        return self._db.scalar(select(File.document_id).where(File.id == file_id))

    def _discard_blob(self, storage_key: str, document_id: int) -> None:
        """Remove the blob of a row whose removal is already committed.

        Reached only after `commit` returned, so the row is gone for good and
        nothing refers to the blob any more.

        A failure here is reported and then swallowed. Turning it into an error
        the caller sees would misreport the outcome: the database did what was
        asked and there is nothing left to roll back or restore. The blob is
        named in the log instead, which is what a later sweep needs to finish
        the job.
        """
        try:
            self._storage.delete(storage_key)
        except Exception as error:
            logger.error(
                "a file row was removed but its blob could not be; the row is "
                "committed and the blob needs reconciliation",
                extra=self._report(
                    "file.detach",
                    "blob_removal_failed",
                    document_id,
                    storage_key,
                    error,
                ),
            )

    def _stage_upload(
        self, document_id: int, original_filename: str, source: BinaryIO
    ) -> File:
        """Validate, store and stage one file, **without committing**.

        Everything that decides whether this file may exist happens before a
        byte is written: the document, the name, the content signature and the
        size limit. Only once all of them pass is the blob stored, which is
        what makes the failure paths cheap.

        The metadata is flushed so the row's id exists and any database error
        surfaces here rather than at a commit the caller may not control. It is
        deliberately **not** committed: the caller decides the transaction
        boundary, which is what lets a future `attach()` put the file row, the
        document status and the history event into one transaction.

        On return the blob is in storage and the row is staged. On failure
        before the blob is written, nothing exists. On failure after it,
        `StorageWrittenError` names the blob, leaving the caller to compensate —
        this method never deletes storage on its own, because only the caller
        knows whether the surrounding operation still needs the file.

        It does not touch the document's verification status. Recording the
        automatic reopening is `attach()`'s job, not the staging stage's.
        """
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
            return self._stage_file_row(
                storage_key, display_name, mime_type, measured, document_id
            )
        except Exception as error:
            raise StorageWrittenError(storage_key) from error

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

    def _stage_file_row(
        self,
        storage_key: str,
        display_name: str,
        mime_type: str,
        measured: "_HashingStream",
        document_id: int,
    ) -> File:
        """Add the metadata row and flush it, **without committing**.

        The flush is what makes the row visible to this session with its `id`
        filled in, and what surfaces a database error here rather than inside a
        commit the caller owns. No `commit` and no `rollback` happen here: both
        belong to whoever decided the transaction boundary.
        """
        file = File(
            document_id=document_id,
            original_filename=display_name,
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=measured.size_bytes,
            sha256=measured.hexdigest,
            uploaded_at=datetime.now(timezone.utc),
        )

        self._db.add(file)
        self._db.flush()
        return file

    def _settle(self, storage_key: str, document_id: int, error: Exception) -> None:
        """Decide what happens to a blob whose `commit` raised.

        The kind of exception proves nothing: `rollback()` does not undo a commit
        the server already accepted, so no class of error is evidence that the
        transaction did not land. The only witness is the database itself.

        `storage_key` is what makes the question answerable — it holds a UUID
        generated for this operation alone, so a row found under it is this
        operation's row and nothing else could have put it there.

        Three answers are possible and only one permits deleting anything:

        - the row is absent, so the transaction demonstrably did not land and
          the blob is an orphan that should not have survived;
        - the row is present, so the transaction did land and the caller is
          being told it failed anyway — reported, never compensated;
        - the row cannot be read, which is the honest unknown. The blob stays
          and the key goes to the log, because an orphaned file is recoverable
          by reconciliation and a deleted one is not.
        """
        try:
            stored = self._db.scalar(
                select(File.id).where(File.storage_key == storage_key)
            )
        except Exception as read_error:
            logger.error(
                "file attach left a blob whose transaction outcome is unknown; "
                "it needs reconciliation before it may be removed",
                extra=self._report(
                    "file.attach",
                    "unknown_commit_outcome",
                    document_id,
                    storage_key,
                    read_error,
                ),
            )
            return

        if stored is None:
            self._compensate(storage_key, document_id, "commit_refused", error)
            return

        logger.error(
            "file attach reported a failure but the transaction is in the "
            "database; the blob is kept and the row must be reconciled",
            extra=self._report(
                "file.attach",
                "commit_landed_despite_failure",
                document_id,
                storage_key,
                error,
            ),
        )

    def _compensate(
        self,
        storage_key: str,
        document_id: int,
        category: str,
        cause: Exception | None = None,
    ) -> None:
        """Remove a blob that is demonstrably not referenced by any row.

        A failure here is reported and then swallowed: the caller is already
        holding a real error, and replacing it with "the cleanup broke" would
        hide what actually went wrong. The blob is left on disk and named in
        the log, which is what makes it findable later.
        """
        try:
            self._storage.delete(storage_key)
        except Exception as cleanup_error:
            logger.error(
                "compensating a file blob failed; it is orphaned and needs "
                "reconciliation",
                extra=self._report(
                    "file.attach",
                    f"compensation_failed:{category}",
                    document_id,
                    storage_key,
                    cleanup_error,
                ),
            )

    @staticmethod
    def _report(
        operation: str,
        category: str,
        document_id: int,
        storage_key: str,
        error: Exception | None,
    ) -> dict[str, object]:
        """The fields a log record has to carry to be actionable.

        Carried as `extra` rather than baked into the message so that a
        configured formatter can put them in dedicated fields. The time is not
        here — it belongs to the logging configuration, so that one place
        decides how records are stamped.

        The record names the operation, the document, the blob and a failure
        category, and identifies the error by its **type**. It deliberately does
        not carry `str(error)`: SQLAlchemy puts the failing statement and its
        parameters into that text, and those parameters include the original
        filename, the storage key and the free-text reason of a human verdict.
        The type plus the category is what recognition needs and is safe to keep
        indefinitely; a driver message is neither.
        """
        return {
            "operation": operation,
            "document_id": document_id,
            "storage_key": storage_key,
            "failure_category": category,
            "error_type": type(error).__name__ if error is not None else None,
        }

    def list_for_document(self, document_id: int) -> list[File]:
        statement = select(File).where(File.document_id == document_id).order_by(File.id)
        return list(self._db.scalars(statement))