from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.documents.schemas import DocumentCreate, DocumentUpdate
from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.file import File
from app.models.issuer import Issuer
from app.services.document_type_service import DocumentTypeService
from app.services.issuer_service import IssuerService

DEFAULT_LIMIT = 50

# Lifecycle states. They mirror ck_documents_verification_status on the table
# and the closed sets checked by document_verification_events.
PENDING = "pending"
VERIFIED = "verified"
REJECTED = "rejected"

# Why a transition happened, as opposed to where it landed.
EVENT_VERIFIED = "verified"
EVENT_REJECTED = "rejected"
EVENT_REOPENED = "reopened"

# Names PostgreSQL gave the two foreign keys on documents, and the SQLSTATE
# reported for any referential violation. Both are checked together, see
# `_foreign_key_constraint`.
DOCUMENT_TYPE_FK_CONSTRAINT = "documents_document_type_id_fkey"
ISSUER_FK_CONSTRAINT = "documents_issuer_id_fkey"
FOREIGN_KEY_VIOLATION_SQLSTATE = "23503"

# Requisites that describe what the document proves. Changing any of them makes
# the previous verification verdict stale, so the status drops back to `pending`.
# `notes` is deliberately absent: free-form commentary does not invalidate the
# document's content and therefore preserves a verdict.
SIGNIFICANT_FIELDS = frozenset(
    {
        "document_type_id",
        "number",
        "issue_date",
        "valid_from",
        "valid_to",
        "issuer_id",
    }
)


class DocumentServiceError(Exception):
    """Base error for DocumentService operations."""


class DocumentTypeNotFoundError(DocumentServiceError):
    """The referenced document type does not exist.

    The identifier is kept on the instance so a caller can report it without
    parsing the message.
    """

    def __init__(self, document_type_id: int) -> None:
        self.document_type_id = document_type_id
        super().__init__(f"Document type {document_type_id} not found")


class IssuerNotFoundError(DocumentServiceError):
    """The referenced issuer does not exist."""

    def __init__(self, issuer_id: int) -> None:
        self.issuer_id = issuer_id
        super().__init__(f"Issuer {issuer_id} not found")


class InvalidValidityPeriodError(DocumentServiceError):
    """The merged validity window would be inverted.

    Raised before any column is mutated, so a rejected update leaves neither a
    partially updated row nor a pending change in the session.
    """

    def __init__(self, valid_from: date, valid_to: date) -> None:
        self.valid_from = valid_from
        self.valid_to = valid_to
        super().__init__(
            f"valid_to {valid_to.isoformat()} is earlier than "
            f"valid_from {valid_from.isoformat()}"
        )


class DocumentHasNoFilesError(DocumentServiceError):
    """A document without an attachment cannot be confirmed.

    A verdict says the scan is the one described by the document, so there has
    to be a scan. Raised before any column is mutated, so a refused
    confirmation leaves the status untouched and records nothing.
    """

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(
            f"Document {document_id} has no attached files and cannot be verified"
        )


class RejectionReasonRequiredError(DocumentServiceError):
    """A rejection was requested without a usable reason.

    `ck_document_verification_events_rejected_reason` refuses a blank reason in
    the database, but the check is repeated here so the caller gets a domain
    error before the document is touched at all.
    """

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(f"A rejection of document {document_id} needs a reason")


def _foreign_key_constraint(error: IntegrityError) -> str | None:
    """Return the violated FK constraint name, or None if this is not one.

    SQLSTATE 23503 on its own is not enough: any foreign key in the database
    reports it, so the constraint name is checked too. Any other integrity error
    (not-null, unique, check constraint) is left untouched so it surfaces as its
    own database error rather than being reported as a missing reference.
    """
    original = error.orig
    if getattr(original, "sqlstate", None) != FOREIGN_KEY_VIOLATION_SQLSTATE:
        return None
    diagnostics = getattr(original, "diag", None)
    return getattr(diagnostics, "constraint_name", None)


class DocumentService:
    """Business logic for documents.

    Sessions are passed in by the caller (see `app.database.connection.get_db`),
    so the service never opens or closes connections on its own.

    Transaction boundaries follow `ProductVariantService`: writes commit exactly
    once per operation, read methods never commit, and a patch that changes
    nothing commits nothing.

    Referential checks run before any column is mutated and the referenced rows
    are additionally re-checked by the database, which is what makes a
    concurrent delete between the two steps surface as a domain error instead of
    a raw `IntegrityError`.

    Verification lifecycle: `verify` and `reject` record a decision, `update`
    records an automatic reopening. Every event is added to the caller's session
    before the single `_commit` of the operation, so a status change and the row
    that explains it are committed or rolled back together. There is exactly one
    commit per mutating method, and none of them commit twice.
    """

    @staticmethod
    def create(db: Session, data: DocumentCreate) -> Document:
        """Create and persist a document, returning the stored row.

        `verification_status` is assigned here rather than taken from the
        payload; a document starts its life as `pending`. No file is attached,
        no product, variant or batch is linked, and no verification event is
        written.
        """
        DocumentService._require_document_type(db, data.document_type_id)
        if data.issuer_id is not None:
            DocumentService._require_issuer(db, data.issuer_id)

        document = Document(
            **data.model_dump(), verification_status=PENDING
        )
        db.add(document)
        DocumentService._commit(db, data.document_type_id, data.issuer_id)
        db.refresh(document)
        return document

    @staticmethod
    def get(db: Session, document_id: int) -> Document | None:
        """Return the document or None when no such row exists."""
        return db.get(Document, document_id)

    @staticmethod
    def list(
        db: Session, limit: int = DEFAULT_LIMIT, offset: int = 0
    ) -> "list[Document]":
        """Return a page of documents ordered by ascending id.

        Ordering by id rather than number keeps the page stable while documents
        are renamed, and it matches every other collection in the project.
        The page carries no total, so paging stays the caller's concern.

        The return annotation is quoted because the method is named `list`: under
        PEP 649 the annotation is evaluated lazily, by which time the class
        attribute shadows the builtin and `list[Document]` would raise
        `TypeError: 'staticmethod' object is not subscriptable`. The other
        services in this project carry the unquoted form; quoting keeps this one
        resolvable by `typing.get_type_hints` and by anything that inspects the
        signature.
        """
        statement = select(Document).order_by(Document.id).limit(limit).offset(offset)
        return list(db.scalars(statement))

    @staticmethod
    def update(db: Session, document_id: int, data: DocumentUpdate) -> Document | None:
        """Apply a partial update, returning None when no such row exists.

        `verification_status` is not part of `DocumentUpdate`, so it can only be
        moved here, and only as a consequence of a data change: a modified
        requisite sends a `verified` or `rejected` verdict back to `pending`.

        A payload that is empty, or that only repeats the values already stored,
        changes nothing and therefore commits nothing.
        """
        document = db.get(Document, document_id)
        if document is None:
            return None

        requested = data.model_dump(exclude_unset=True)
        if not requested:
            return document

        # Only fields whose value really differs. Repeating the current value is
        # a no-op: it must not commit and must not reset the verification
        # status, because nothing was actually re-asserted.
        effective = {
            field: value
            for field, value in requested.items()
            if getattr(document, field) != value
        }
        if not effective:
            return document

        # Validate the merged document before touching the ORM object, so a
        # rejected update cannot leave a half-applied row behind. The schema can
        # only compare the two bounds when both were sent together; here the
        # stored value supplies whatever the patch left out.
        valid_from = effective.get("valid_from", document.valid_from)
        valid_to = effective.get("valid_to", document.valid_to)
        if valid_from is not None and valid_to is not None and valid_to < valid_from:
            raise InvalidValidityPeriodError(valid_from, valid_to)

        # Referential checks also precede any mutation.
        if "document_type_id" in effective:
            DocumentService._require_document_type(db, effective["document_type_id"])
        if effective.get("issuer_id") is not None:
            DocumentService._require_issuer(db, effective["issuer_id"])

        for field, value in effective.items():
            setattr(document, field, value)

        if SIGNIFICANT_FIELDS.intersection(effective):
            DocumentService._apply_status_transition(db, document)

        DocumentService._commit(
            db, document.document_type_id, document.issuer_id
        )
        db.refresh(document)
        return document

    @staticmethod
    def _apply_status_transition(db: Session, document: Document) -> None:
        """Send a modified document back to `pending` and record why.

        A document that has been decided on cannot stay decided once its content
        changes: the verdict was given for the old content. `from_status` is
        therefore the verdict being withdrawn, and the event type is `reopened`
        so an auditor can tell an automatic reopening from a fresh decision.

        A document that is already pending has nothing to withdraw, so no event
        is written — otherwise every edit to an undecided document would bury
        the history under meaningless rows.

        The event is added to the same session and stays pending until the single
        `_commit` below, which is what makes the status change and its history
        one atomic unit: both land or neither does.
        """
        previous_status = document.verification_status
        if previous_status == PENDING:
            return

        document.verification_status = PENDING
        db.add(
            DocumentVerificationEvent(
                document_id=document.id,
                from_status=previous_status,
                to_status=PENDING,
                event_type=EVENT_REOPENED,
                reason=None,
            )
        )

    @staticmethod
    def verify(
        db: Session, document_id: int, reason: str | None = None
    ) -> Document | None:
        """Confirm a document, recording the decision, or return None.

        A verdict only means something alongside the scan it refers to, so at
        least one attached file is required. The check runs before the document
        is touched, so a refused confirmation changes nothing and records
        nothing.

        `rejected → verified` is allowed directly: re-examining a rejected
        document and clearing it does not have to pass through a pending state
        that nobody asked for. Re-confirming an already confirmed document is a
        no-op, so the history is not padded with rows that decided nothing.
        """
        document = db.get(Document, document_id)
        if document is None:
            return None

        if document.verification_status == VERIFIED:
            return document

        DocumentService._require_attachment(db, document.id)

        previous_status = document.verification_status
        document.verification_status = VERIFIED
        db.add(
            DocumentVerificationEvent(
                document_id=document.id,
                from_status=previous_status,
                to_status=VERIFIED,
                event_type=EVENT_VERIFIED,
                reason=reason,
            )
        )
        DocumentService._commit(
            db, document.document_type_id, document.issuer_id
        )
        db.refresh(document)
        return document

    @staticmethod
    def reject(db: Session, document_id: int, reason: str) -> Document | None:
        """Reject a document with a reason, recording the decision.

        A rejection without a reason is not auditable, so one is required and
        must contain something other than whitespace. The check runs before the
        document is touched.

        `verified → rejected` is allowed directly. Rejecting an already rejected
        document is idempotent and does not touch the recorded reason: the
        original decision stands, and rewriting history would destroy the fact
        that the document was rejected for the reason given at the time. The
        idempotency check therefore precedes the reason check.
        """
        document = db.get(Document, document_id)
        if document is None:
            return None

        if document.verification_status == REJECTED:
            return document

        if reason is None or not reason.strip():
            raise RejectionReasonRequiredError(document_id)

        previous_status = document.verification_status
        document.verification_status = REJECTED
        db.add(
            DocumentVerificationEvent(
                document_id=document.id,
                from_status=previous_status,
                to_status=REJECTED,
                event_type=EVENT_REJECTED,
                reason=reason,
            )
        )
        DocumentService._commit(
            db, document.document_type_id, document.issuer_id
        )
        db.refresh(document)
        return document

    @staticmethod
    def _require_attachment(db: Session, document_id: int) -> None:
        """Raise DocumentHasNoFilesError unless the document has a file."""
        attached = db.scalar(
            select(func.count()).select_from(File).where(File.document_id == document_id)
        )
        if not attached:
            raise DocumentHasNoFilesError(document_id)

    @staticmethod
    def _require_document_type(db: Session, document_type_id: int) -> DocumentType:
        """Return the document type or raise DocumentTypeNotFoundError."""
        document_type = DocumentTypeService.get_by_id(db, document_type_id)
        if document_type is None:
            raise DocumentTypeNotFoundError(document_type_id)
        return document_type

    @staticmethod
    def _require_issuer(db: Session, issuer_id: int) -> Issuer:
        """Return the issuer or raise IssuerNotFoundError."""
        issuer = IssuerService.get_by_id(db, issuer_id)
        if issuer is None:
            raise IssuerNotFoundError(issuer_id)
        return issuer

    @staticmethod
    def _commit(
        db: Session, document_type_id: int | None, issuer_id: int | None
    ) -> None:
        """Commit, translating a broken reference and rolling back on error.

        The identifiers are passed in rather than read from `document` because a
        rollback expires the instance; reading them afterwards would issue extra
        queries for values that are already known.
        """
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            constraint = _foreign_key_constraint(error)
            if constraint == DOCUMENT_TYPE_FK_CONSTRAINT:
                raise DocumentTypeNotFoundError(document_type_id) from error
            if constraint == ISSUER_FK_CONSTRAINT:
                raise IssuerNotFoundError(issuer_id) from error
            raise