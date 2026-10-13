from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Statuses the documents table already knows about; ck_documents_verification_status
# is the authority, these two constraints keep this table self-contained.
STATUSES = ("pending", "verified", "rejected")
EVENT_TYPES = ("verified", "rejected", "reopened")


class DocumentVerificationEvent(Base):
    """One recorded change of a document's verification state.

    `documents.verification_status` only holds the current value, so a row here
    is the only way to reconstruct how the document got there. `from_status` is
    the value the column carried immediately before `to_status`, which is what
    makes a `reopened` event distinguishable from the very first `verified`.

    `event_type` states why the transition happened rather than restating the
    target, so `reopened` is a first-class outcome and not just another name for
    "pending":

    - `verified`  — a decision was made to verify the document;
    - `rejected`  — a decision was made to reject it, and a reason is mandatory;
    - `reopened`  — the document was sent back to review after its content
      changed, which only makes sense from a decided state.

    `created_at` is filled by the database, not by the caller, so a client cannot
    backdate a decision. The composite index serves the only query this table
    needs today: the history of one document in chronological order, with `id`
    breaking ties inside a single transaction.

    No relationship is declared back to `Document` on purpose. Reading the
    history is always "by document_id", so a lazy collection on Document would
    be loaded whenever a document is fetched and would slow down every list
    endpoint for no gain. Dropping a document removes its events through the
    foreign key instead.
    """

    __tablename__ = "document_verification_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "from_status IN ('pending', 'verified', 'rejected')",
            name="ck_document_verification_events_from_status",
        ),
        CheckConstraint(
            "to_status IN ('pending', 'verified', 'rejected')",
            name="ck_document_verification_events_to_status",
        ),
        CheckConstraint(
            "event_type IN ('verified', 'rejected', 'reopened')",
            name="ck_document_verification_events_event_type",
        ),
        # A row that records nothing would make the history unreadable, so a
        # transition into the state the document already holds is refused. This
        # is also what keeps `verified`/`rejected` from re-deciding themselves.
        CheckConstraint(
            "from_status <> to_status",
            name="ck_document_verification_events_status_changed",
        ),
        CheckConstraint(
            "(event_type = 'verified' AND to_status = 'verified')"
            " OR (event_type = 'rejected' AND to_status = 'rejected')"
            " OR (event_type = 'reopened' AND to_status = 'pending')",
            name="ck_document_verification_events_type_matches_target",
        ),
        # Rejecting without stating why would leave an auditor with an
        # unexplained decision. btrim is given an explicit whitespace set because
        # its default trims spaces only: a reason made of tabs or newlines would
        # otherwise pass as if it were a reason.
        CheckConstraint(
            "event_type <> 'rejected'"
            " OR (reason IS NOT NULL"
            " AND btrim(reason, E' \\t\\n\\r\\f\\v') <> '')",
            name="ck_document_verification_events_rejected_reason",
        ),
        # Returning a document to review only means something after a decision;
        # pending -> pending is a no-op, not a reopening.
        CheckConstraint(
            "event_type <> 'reopened'"
            " OR from_status IN ('verified', 'rejected')",
            name="ck_document_verification_events_reopened_origin",
        ),
        Index(
            "ix_document_verification_events_document_id_created_at_id",
            "document_id",
            "created_at",
            "id",
        ),
    )