"""The single place in the project that records an automatic reopening.

A `reopened` event means one thing everywhere: a document that had been decided
on lost that decision and went back to `pending`. The trigger differs — a
significant requisite changed, a file was attached, a file was removed — so the
trigger is carried by `reason`, and that reason is what lets an auditor tell the
cases apart. Before the reason was recorded, all three produced identical rows,
and a removed file left no trace at all.

Keeping this in one module is the point. `DocumentService` writes reopened
events today and `FileService` will write them once attachments exist; two
implementations of the same rule would drift apart, and the drift would show up
as either a missing event or a duplicated one.

`reason` is a closed set of machine codes, not free text. `rejected` events
carry a human explanation instead, and the two meanings share one column, so a
reader of the history has to know which one they are looking at.
"""

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_verification_event import (
    STATUSES,
    DocumentVerificationEvent,
)

# The two values this module deals with. Both come from the closed sets the
# database already enforces — ck_documents_verification_status and
# ck_document_verification_events_event_type — and are repeated here only to
# keep the names readable.
PENDING = "pending"
REOPENED = "reopened"

# Why a decided document was sent back to review. One code per trigger, no more:
# a cause this list cannot express is not a cause the history records.
REASON_SIGNIFICANT_FIELDS_CHANGED = "significant_fields_changed"
REASON_FILE_ADDED = "file_added"
REASON_FILE_DELETED = "file_deleted"

REOPENED_REASONS = frozenset(
    {
        REASON_SIGNIFICANT_FIELDS_CHANGED,
        REASON_FILE_ADDED,
        REASON_FILE_DELETED,
    }
)


class VerificationHistoryError(Exception):
    """Base error for recording verification history."""


class InvalidReopenReasonError(VerificationHistoryError):
    """The reason is not one of the accepted reopening causes.

    The reason is a constant chosen at the call site, so a value outside the set
    is a mistake in the calling code rather than a condition a user can cause.
    It is refused before the document is touched, so a wrong reason cannot leave
    a status change behind without an event.
    """

    def __init__(self, reason: object) -> None:
        self.reason = reason
        super().__init__(
            f"{reason!r} is not a valid reopening reason; "
            f"expected one of {sorted(REOPENED_REASONS)}"
        )


class UnknownVerificationStatusError(VerificationHistoryError):
    """The document carries a status outside the column's closed set.

    `pending` and a decided state are the only states a reopening can start
    from. Anything else means the row does not satisfy
    `ck_documents_verification_status`, and guessing would produce an event the
    database rejects at flush time — a far worse place to find out.
    """

    def __init__(self, status: object) -> None:
        self.status = status
        super().__init__(
            f"{status!r} is not a known verification status; "
            f"expected one of {list(STATUSES)}"
        )


def record_reopened(db: Session, document: Document, reason: str) -> bool:
    """Send `document` back to `pending` and record why, in the caller's session.

    Returns whether a transition actually happened: `False` when the document
    was already `pending`, because there is no verdict to withdraw and an event
    for it would be noise. A document that has not been decided on yet has
    nothing to reopen, which is the same answer.

    The event is added to the caller's session and stays pending there. Nothing
    is committed, flushed or rolled back here: the transition and its history
    must land together with the rest of the operation, so the single `commit`
    stays with whoever owns the transaction. Flushing early would make the two
    independent, and rolling back would discard the caller's work.

    The document is taken as given rather than loaded. It must belong to `db`,
    and the caller decides how it got there.

    Locking is deliberately absent as well. Taking `SELECT ... FOR UPDATE` is
    the caller's job, because only the caller knows which other rows the same
    operation is about to touch. The reason this matters: a locking `SELECT`
    returns an already-loaded instance with its attributes as they were, so a
    caller that wants a fresh verdict must read it with `populate_existing`
    before calling this function.
    """
    if not isinstance(reason, str) or reason not in REOPENED_REASONS:
        raise InvalidReopenReasonError(reason)

    previous_status = document.verification_status
    if previous_status not in STATUSES:
        raise UnknownVerificationStatusError(previous_status)
    if previous_status == PENDING:
        return False

    document.verification_status = PENDING
    db.add(
        DocumentVerificationEvent(
            document_id=document.id,
            from_status=previous_status,
            to_status=PENDING,
            event_type=REOPENED,
            reason=reason,
        )
    )
    return True