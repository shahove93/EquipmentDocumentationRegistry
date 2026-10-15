"""How a service reads a document it is about to write.

Three things have to be true before any mutating method may look at a
document's status: nobody else can change it while the decision is being made,
the session holds no edits that taking the lock would destroy, and the method
knows whether the transaction it finds is its own or the caller's. All three
live here so that `DocumentService` and `FileService` cannot grow two
different answers to the same question.

What is deliberately **not** here is the policy. Ending a transaction is the
caller's judgement, not this module's: `DocumentService` adopts a transaction
it opened itself and leaves the caller's alone, while `FileService` refuses to
run inside a transaction at all. The two policies differ, so only the mechanism
is shared.
"""

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models.document import Document


class UncommittedChangesInSession(Exception):
    """The session holds edits that taking the row lock would discard.

    This is the low-level signal, raised before anything is written. Each
    service turns it into its own domain error, because whether such a call is
    merely refused or refused with a particular wording is that service's
    business.
    """

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(
            f"Document {document_id} has uncommitted changes in this session"
        )


def transaction_existed_on_entry(db: Session) -> bool:
    """Whether the caller had already opened a transaction.

    SQLAlchemy opens one implicitly on first use, so this is asked *before* any
    statement runs. It reports existence, not ownership: a session that had a
    transaction when the method was called belongs to the caller, and a service
    must decide for itself what to do about that.
    """
    return db.in_transaction()


def locked_document(db: Session, document_id: int) -> Document | None:
    """Load a document for writing, holding its row until the transaction ends.

    **The row is locked, not merely read.** Every mutating method decides what
    to do from the document's current status, and that decision is only valid
    while nobody else can change it. Two requests that both read `pending`,
    both conclude they are free to verify, and both commit would leave two
    `verified` events of which the second describes a transition that never
    happened. The lock is taken before the status is examined, so the second
    request waits and then reads what the first one committed.

    **`populate_existing` is what makes waiting worth anything.** Without it a
    document already present in the session comes straight out of the identity
    map, so a caller that loaded it before the competing transaction committed
    would keep deciding on the old status even after the wait. With it, the
    attributes are replaced by what the row holds once the lock is granted —
    which is the whole point of having waited.

    **That replacement is why the pending-change guard exists.** A refresh
    discards local edits instead of merging them. Losing a caller's work
    silently is worse than refusing the call, so the session is asked first and
    the refusal is raised before anything is written.

    `db.get` runs before the locking statement for that check alone. It is a
    second round trip when the document is not already loaded, which is a price
    worth paying on a write path to keep the check in front of the refresh
    rather than behind it.

    Returns None when the row is gone. That is what a concurrent delete looks
    like from here: the locking select waits for the deleting transaction and
    then matches nothing.

    Raises `UncommittedChangesInSession` if the document carries uncommitted
    edits. It commits, rolls back and flushes nothing either way.
    """
    document = db.get(Document, document_id)
    if document is None:
        return None

    if inspect(document).modified:
        raise UncommittedChangesInSession(document_id)

    statement = (
        select(Document)
        .where(Document.id == document_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.execute(statement).scalar_one_or_none()


def release(db: Session, service_opened: bool) -> None:
    """End the transaction this method started, if it started one.

    A row lock lives until its transaction ends. A path that changes nothing —
    a refused confirmation, an idempotent repeat, a no-op update — would
    otherwise walk away still holding the document, making every other
    transaction on it wait for as long as the caller's session happened to live.

    `service_opened` is the caller's answer to `transaction_existed_on_entry`,
    not a decision made here. Passing False for a transaction that belongs to
    the caller is what keeps a rollback from destroying work that was staged
    before the service was ever called.
    """
    if service_opened:
        db.rollback()