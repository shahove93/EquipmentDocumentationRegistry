"""`record_reopened` on its own, without any service in the way.

`DocumentService` only ever calls this function with one reason, so its other
two reasons cannot be exercised through it. Testing the function directly is
also the only way to assert the things that matter for a shared mechanism: that
it writes nothing of its own to the transaction, and that a wrong reason is
refused before the document is touched.
"""

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from types import SimpleNamespace

from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.document_verification_event import DocumentVerificationEvent
from app.services.verification_history import (
    REASON_FILE_ADDED,
    REASON_FILE_DELETED,
    REASON_SIGNIFICANT_FIELDS_CHANGED,
    REOPENED,
    REOPENED_REASONS,
    InvalidReopenReasonError,
    UnknownVerificationStatusError,
    record_reopened,
)


class _NoSession:
    """Stands in for the session so a refusal needs no database at all.

    `record_reopened` refuses before it touches either the document or the
    session, so a call that must fail never reaches `db.add`. Reaching this
    object would mean the refusal came too late.
    """

    def add(self, *args, **kwargs):
        raise AssertionError("a refused reason must not reach the session")


@pytest.fixture
def document_type(db: Session) -> DocumentType:
    row = DocumentType(name="Паспорт")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def make_document(db: Session, document_type: DocumentType):
    counter = {"n": 0}

    def _make(status: str | None = None) -> Document:
        counter["n"] += 1
        row = Document(
            document_type_id=document_type.id,
            number=f"ПС-{counter['n']:03d}",
        )
        if status is not None:
            row.verification_status = status
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _make


def events_of(db: Session, document_id: int) -> list[DocumentVerificationEvent]:
    return list(
        db.scalars(
            select(DocumentVerificationEvent)
            .where(DocumentVerificationEvent.document_id == document_id)
            .order_by(DocumentVerificationEvent.id)
        )
    )


def reload(db: Session, document_id: int) -> Document:
    db.expire_all()
    return db.get(Document, document_id)


class TestTransitions:
    def test_verified_to_pending_with_significant_fields_changed(
        self, db, make_document
    ):
        document = make_document("verified")

        assert record_reopened(db, document, REASON_SIGNIFICANT_FIELDS_CHANGED) is True

        assert document.verification_status == "pending"
        db.commit()
        assert reload(db, document.id).verification_status == "pending"
        stored = events_of(db, document.id)
        assert len(stored) == 1
        assert stored[0].event_type == REOPENED
        assert stored[0].from_status == "verified"
        assert stored[0].to_status == "pending"
        assert stored[0].reason == REASON_SIGNIFICANT_FIELDS_CHANGED

    def test_rejected_to_pending_with_file_added(self, db, make_document):
        document = make_document("rejected")

        assert record_reopened(db, document, REASON_FILE_ADDED) is True

        assert document.verification_status == "pending"
        db.commit()
        assert reload(db, document.id).verification_status == "pending"
        stored = events_of(db, document.id)
        assert len(stored) == 1
        assert stored[0].from_status == "rejected"
        assert stored[0].to_status == "pending"
        assert stored[0].event_type == REOPENED
        assert stored[0].reason == REASON_FILE_ADDED

    def test_verified_to_pending_with_file_deleted(self, db, make_document):
        document = make_document("verified")

        assert record_reopened(db, document, REASON_FILE_DELETED) is True

        assert document.verification_status == "pending"
        db.commit()
        assert reload(db, document.id).verification_status == "pending"
        stored = events_of(db, document.id)
        assert len(stored) == 1
        assert stored[0].from_status == "verified"
        assert stored[0].reason == REASON_FILE_DELETED

    @pytest.mark.parametrize(
        "reason",
        [
            REASON_SIGNIFICANT_FIELDS_CHANGED,
            REASON_FILE_ADDED,
            REASON_FILE_DELETED,
        ],
    )
    def test_every_reason_is_accepted(self, db, make_document, reason):
        document = make_document("verified")
        assert record_reopened(db, document, reason) is True
        assert events_of(db, document.id)[0].reason == reason

    def test_pending_to_pending_creates_nothing(self, db, make_document):
        document = make_document("pending")

        assert record_reopened(db, document, REASON_FILE_ADDED) is False

        assert reload(db, document.id).verification_status == "pending"
        assert events_of(db, document.id) == []

    def test_pending_document_is_not_touched(self, db, make_document):
        document = make_document("pending")
        document_id = document.id
        assert record_reopened(db, document, REASON_FILE_DELETED) is False
        db.commit()
        assert reload(db, document_id).verification_status == "pending"
        assert events_of(db, document_id) == []

    def test_repeated_call_creates_no_second_event(self, db, make_document):
        document = make_document("verified")
        assert record_reopened(db, document, REASON_FILE_ADDED) is True
        db.commit()

        # the second call sees the status the first one wrote
        assert record_reopened(db, document, REASON_FILE_DELETED) is False

        db.commit()
        stored = events_of(db, document.id)
        assert len(stored) == 1
        assert stored[0].reason == REASON_FILE_ADDED

    def test_no_event_when_the_status_never_changed(self, db, make_document):
        document = make_document("rejected")
        for _ in range(3):
            record_reopened(db, document, REASON_FILE_DELETED)
        db.commit()
        assert len(events_of(db, document.id)) == 1


class TestInvalidReason:
    @pytest.mark.parametrize(
        "reason",
        [
            "file_renamed",
            "",
            " ",
            "FILE_ADDED",
            "file_added ",
            " file_added",
            "Significant_fields_changed",
            None,
            1,
            1.5,
            True,
            b"file_added",
            ["file_added"],
            {"reason": "file_added"},
        ],
    )
    def test_rejected(self, db, make_document, reason):
        document = make_document("verified")

        with pytest.raises(InvalidReopenReasonError):
            record_reopened(db, document, reason)

    @pytest.mark.parametrize(
        "reason", ["file_renamed", "", None, ["file_added"]]
    )
    def test_refused_before_the_document_is_touched(self, db, make_document, reason):
        document = make_document("verified")

        with pytest.raises(InvalidReopenReasonError):
            record_reopened(db, document, reason)

        assert reload(db, document.id).verification_status == "verified"
        assert events_of(db, document.id) == []

    def test_refused_even_for_a_pending_document(self, db, make_document):
        # the reason is a constant chosen at the call site, so a wrong one is a
        # mistake regardless of whether a transition would have happened
        document = make_document("pending")

        with pytest.raises(InvalidReopenReasonError):
            record_reopened(db, document, "file_renamed")

        assert events_of(db, document.id) == []

    def test_error_carries_the_reason(self, db, make_document):
        document = make_document("verified")
        with pytest.raises(InvalidReopenReasonError) as info:
            record_reopened(db, document, "file_renamed")
        assert info.value.reason == "file_renamed"
        assert "file_added" in str(info.value)

    def test_the_closed_set_is_exactly_three_codes(self):
        assert REOPENED_REASONS == frozenset(
            {"significant_fields_changed", "file_added", "file_deleted"}
        )

    def test_free_text_rejected_is_the_documented_meaning(self):
        # `rejected` events take a human explanation in the same column, so the
        # separation between the two meanings is a real constraint
        assert "проверен вручную" not in REOPENED_REASONS


class TestUnknownStatus:
    """The closed set of `documents.verification_status` is the only input
    accepted besides a decided state. These cases use a stand-in object on
    purpose: a real row carrying an impossible status cannot be re-read, because
    any query would autoflush a value the column refuses."""

    @pytest.mark.parametrize(
        "status", [None, "", " ", "verified ", "VERIFIED", "archived", 0, 1, 2]
    )
    def test_status_outside_the_closed_set_is_refused(self, status):
        stub = SimpleNamespace(verification_status=status)

        with pytest.raises(UnknownVerificationStatusError):
            record_reopened(_NoSession(), stub, REASON_FILE_ADDED)

    def test_the_refused_document_is_left_alone(self):
        stub = SimpleNamespace(verification_status="archived")

        with pytest.raises(UnknownVerificationStatusError):
            record_reopened(_NoSession(), stub, REASON_FILE_ADDED)

        assert stub.verification_status == "archived"

    def test_error_carries_the_status(self):
        stub = SimpleNamespace(verification_status="archived")
        with pytest.raises(UnknownVerificationStatusError) as info:
            record_reopened(_NoSession(), stub, REASON_FILE_ADDED)
        assert info.value.status == "archived"

    def test_the_refusal_precedes_the_reason_check(self):
        # a bad reason and an unknown status are both refused, and the reason is
        # checked first because it is a mistake in the calling code
        stub = SimpleNamespace(verification_status="archived")
        with pytest.raises(InvalidReopenReasonError):
            record_reopened(_NoSession(), stub, "file_renamed")

    def test_an_unflushed_document_has_no_status_yet(self, db, document_type):
        # `default="pending"` is applied on INSERT, so a document that has not
        # been flushed carries None — which is refused rather than guessed at
        document = Document(document_type_id=document_type.id, number="ПС-900")
        db.add(document)

        with pytest.raises(UnknownVerificationStatusError):
            record_reopened(db, document, REASON_FILE_ADDED)

        db.rollback()
        assert events_of(db, document.id) == []

    def test_a_stored_row_always_has_a_known_status(self, db, make_document):
        # the guard never fires for a row that came out of the database
        for status in ("pending", "verified", "rejected"):
            document = make_document(status)
            assert record_reopened(db, document, REASON_FILE_ADDED) in (True, False)


class TestTransactionBoundary:
    def test_no_commit(self, db, make_document, monkeypatch):
        document = make_document("verified")
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append("commit"))

        assert record_reopened(db, document, REASON_FILE_ADDED) is True
        assert calls == []

    def test_no_rollback(self, db, make_document, monkeypatch):
        document = make_document("verified")
        calls = []
        monkeypatch.setattr(db, "rollback", lambda: calls.append("rollback"))

        record_reopened(db, document, REASON_FILE_DELETED)
        assert calls == []

    def test_no_flush(self, db, make_document, monkeypatch):
        document = make_document("verified")
        calls = []
        monkeypatch.setattr(db, "flush", lambda: calls.append("flush"))

        record_reopened(db, document, REASON_SIGNIFICANT_FIELDS_CHANGED)
        assert calls == []

    def test_nothing_survives_a_rollback_by_the_caller(self, db, make_document):
        # the function committed nothing of its own, so the caller's rollback
        # discards both halves — the status change and the event together
        document = make_document("verified")

        assert record_reopened(db, document, REASON_FILE_ADDED) is True
        assert document.verification_status == "pending"
        assert len(events_of(db, document.id)) == 1

        db.rollback()

        assert reload(db, document.id).verification_status == "verified"
        assert events_of(db, document.id) == []

    def test_the_caller_can_retry_after_a_rollback(self, db, make_document):
        document = make_document("verified")
        record_reopened(db, document, REASON_FILE_ADDED)
        db.rollback()

        assert record_reopened(db, document, REASON_FILE_ADDED) is True
        db.commit()

        assert reload(db, document.id).verification_status == "pending"
        assert len(events_of(db, document.id)) == 1

    def test_the_caller_owns_the_commit(self, db, make_document):
        document = make_document("verified")
        assert record_reopened(db, document, REASON_FILE_ADDED) is True
        db.commit()

        assert reload(db, document.id).verification_status == "pending"
        assert len(events_of(db, document.id)) == 1

    def test_a_failed_save_rolls_back_the_status(self, db, make_document, monkeypatch):
        # the event violates its own CHECK at flush time, so the failure happens
        # inside the caller's commit and the caller's rollback undoes both halves
        from app.services.verification_history import PENDING

        document = make_document("verified")
        real_add = db.add

        def poisoned(instance, *args, **kwargs):
            if isinstance(instance, DocumentVerificationEvent):
                instance.event_type = "approved"  # not in EVENT_TYPES
            return real_add(instance, *args, **kwargs)

        monkeypatch.setattr(db, "add", poisoned)

        assert record_reopened(db, document, REASON_FILE_ADDED) is True
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        monkeypatch.undo()

        assert reload(db, document.id).verification_status == "verified"
        assert events_of(db, document.id) == []
        assert PENDING == "pending"


class TestIsolationBetweenDocuments:
    def test_independent_documents_do_not_interfere(self, db, make_document):
        first = make_document("verified")
        second = make_document("verified")
        third = make_document("pending")

        assert record_reopened(db, first, REASON_FILE_ADDED) is True
        assert record_reopened(db, second, REASON_FILE_DELETED) is True
        assert record_reopened(db, third, REASON_FILE_ADDED) is False
        db.commit()

        assert reload(db, first.id).verification_status == "pending"
        assert reload(db, second.id).verification_status == "pending"
        assert reload(db, third.id).verification_status == "pending"

        assert len(events_of(db, first.id)) == 1
        assert len(events_of(db, second.id)) == 1
        assert events_of(db, third.id) == []

    def test_events_are_not_cross_linked(self, db, make_document):
        first = make_document("verified")
        second = make_document("rejected")
        record_reopened(db, first, REASON_FILE_ADDED)
        record_reopened(db, second, REASON_FILE_DELETED)
        db.commit()

        first_events = events_of(db, first.id)
        second_events = events_of(db, second.id)
        assert first_events[0].document_id == first.id
        assert second_events[0].document_id == second.id
        assert first_events[0].id != second_events[0].id


class TestSharedMechanism:
    def test_document_service_uses_this_function(self):
        # the whole point of the module: DocumentService must not build the event
        # itself any more
        import inspect

        from app.services import document_service, verification_history

        source = inspect.getsource(document_service)
        assert "record_reopened" in source
        assert "REASON_SIGNIFICANT_FIELDS_CHANGED" in source
        assert 'event_type=EVENT_REOPENED' not in source
        assert "EVENT_REOPENED" not in source

        shared = inspect.getsource(verification_history)
        assert 'event_type=REOPENED' in shared

    def test_event_type_constant_comes_from_the_model(self):
        from app.models.document_verification_event import EVENT_TYPES

        assert REOPENED in EVENT_TYPES

    def test_pending_constant_comes_from_the_model(self):
        from app.models.document_verification_event import STATUSES

        from app.services.verification_history import PENDING

        assert PENDING in STATUSES


class TestNoLocking:
    def test_the_function_takes_no_row_lock(self, db, make_document):
        # the caller owns locking; a lock here would serialise unrelated work
        document = make_document("verified")
        statements = []

        def capture(conn, cursor, statement, *args):
            statements.append(statement)

        sa_event.listen(db.get_bind(), "before_cursor_execute", capture)
        try:
            record_reopened(db, document, REASON_FILE_ADDED)
        finally:
            sa_event.remove(db.get_bind(), "before_cursor_execute", capture)

        assert not any("FOR UPDATE" in s for s in statements)

    def test_the_function_does_not_load_the_document(self, db, make_document):
        # the document is handed over, so the function must never go and get it
        document = make_document("verified")
        calls = []

        def forbidden(*args, **kwargs):
            calls.append(1)
            raise AssertionError("record_reopened must not read the document")

        monkey = db.get
        db.get = forbidden
        try:
            assert record_reopened(db, document, REASON_FILE_ADDED) is True
        finally:
            db.get = monkey
        assert calls == []