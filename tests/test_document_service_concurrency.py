"""Row locking in `DocumentService`, proved against a real PostgreSQL.

Every check here runs on the scratch schema created by the `engine` fixture, in
separate sessions and separate connections, because the whole subject is what
PostgreSQL does when two transactions meet on the same row. SQLite cannot show
any of it: it has no `FOR UPDATE` and serialises writers differently, so a test
against it would prove nothing about the production engine.

The races are arranged, not raced for. The first transaction is stopped inside
its `commit`, which is the last moment at which it still holds the row lock, so
the second transaction is observed waiting before it is allowed to finish. Two
independent signals confirm the wait is real rather than slow:

- the second session's backend shows an ungranted entry in `pg_locks`, which is
  PostgreSQL itself reporting that it is queued behind the lock;
- the second thread has not finished while the first still holds the lock.

Every wait has a bound, so a regression fails the test instead of hanging it.
"""

import threading
import time
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.api.documents.schemas import DocumentCreate, DocumentUpdate
from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.file import File
from app.models.issuer import Issuer
from app.services.document_service import (
    PENDING,
    REJECTED,
    VERIFIED,
    DocumentHasNoFilesError,
    DocumentService,
    InvalidValidityPeriodError,
    RejectionReasonRequiredError,
    UncommittedDocumentChangesError,
)

# Upper bound for a thread to reach its gate. Generous, because it only ever
# bounds a failure; a passing run never waits close to this.
TIMEOUT = 10.0

# How long to watch the second transaction and expect it to still be blocked.
BLOCKED_WINDOW = 0.5


def wait_until(predicate, timeout=TIMEOUT, interval=0.01):
    """Poll `predicate` until it is true, or fail after `timeout`."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def run_in_thread(fn, name):
    """Start `fn` and return its thread plus a box collecting the outcome."""
    box = {}

    def runner():
        try:
            box["value"] = fn()
        except BaseException as error:  # noqa: BLE001 - reported to the main thread
            box["error"] = error
        finally:
            box["done"] = True

    thread = threading.Thread(target=runner, name=name, daemon=True)
    thread.start()
    return thread, box


def join_or_fail(thread, what):
    """`Thread.join` returns None, so liveness has to be checked separately."""
    thread.join(TIMEOUT)
    assert not thread.is_alive(), f"the {what} transaction hung"


def gate_commit(session, reached, release):
    """Stop the session's `commit` until `release` is set.

    The transaction is complete but not yet durable, and the row lock taken at
    the start of the operation is still held — exactly the window a second
    request has to queue in.
    """
    original = session.commit

    def commit():
        reached.set()
        if not release.wait(timeout=TIMEOUT):
            raise AssertionError("the gate was never opened; test is stuck")
        original()

    session.commit = commit


def backend_pid(session):
    """Pin the session's connection and return its PostgreSQL backend id."""
    return session.execute(text("SELECT pg_backend_pid()")).scalar()


def lock_is_held(sessions, document_id):
    """Whether a competing session would have to wait for the row.

    Asked with a short `lock_timeout`, so the answer comes from the server
    rather than from waiting out the real thing.
    """
    probe = sessions()
    try:
        probe.execute(text("SET lock_timeout = '400ms'"))
        probe.execute(
            text("SELECT 1 FROM documents WHERE id = :i FOR UPDATE"),
            {"i": document_id},
        )
        probe.rollback()
        return False
    except DBAPIError:
        probe.rollback()
        return True
    finally:
        probe.close()


def ungranted_locks(observer, pid):
    """How many lock requests this backend is queued on."""
    return observer.execute(
        text("SELECT count(*) FROM pg_locks WHERE pid = :pid AND NOT granted"),
        {"pid": pid},
    ).scalar()


@pytest.fixture
def sessions(engine):
    """Independent sessions on the scratch schema, closed afterwards."""
    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    made = []

    def _open():
        session = factory()
        made.append(session)
        return session

    yield _open
    for session in made:
        session.rollback()
        session.close()


@pytest.fixture
def prepare(db):
    """Create a committed document, optionally already decided and with a file.

    `issuer` adds a second row for tests about a caller dirtying an unrelated
    object. Everything is committed so the fixture session holds no lock of its
    own; otherwise it would be the thing blocking the other sessions.
    """
    counter = {"n": 0}

    def _make(status=PENDING, with_file=True, issuer=False):
        counter["n"] += 1
        document_type = DocumentType(name=f"Тип-{counter['n']}")
        db.add(document_type)
        db.flush()
        document = Document(
            document_type=document_type,
            number=f"ПС-{counter['n']:03d}",
            verification_status=status,
            valid_from=date(2026, 6, 1) if status == "has-period" else None,
        )
        if status == "has-period":
            document.verification_status = PENDING
        db.add(document)
        db.flush()
        if with_file:
            db.add(
                File(
                    document_id=document.id,
                    original_filename="passport.pdf",
                    storage_key=f"documents/{document.id}/{counter['n']}.pdf",
                    mime_type="application/pdf",
                    size_bytes=1024,
                    sha256="0" * 64,
                    uploaded_at=datetime.now(timezone.utc),
                )
            )
        if issuer:
            db.add(Issuer(name=f"Изд-{counter['n']}"))
        db.commit()
        return document.id

    return _make


def history(session, document_id):
    """The recorded transitions, in commit order."""
    rows = session.execute(
        select(DocumentVerificationEvent)
        .where(DocumentVerificationEvent.document_id == document_id)
        .order_by(DocumentVerificationEvent.id)
    ).scalars().all()
    return [
        (e.from_status, e.to_status, e.event_type, e.reason) for e in rows
    ]


def status_of(session, document_id):
    """The stored status, read from the database rather than from memory."""
    return session.execute(
        text("SELECT verification_status FROM documents WHERE id = :i"),
        {"i": document_id},
    ).scalar()


@pytest.fixture
def racer(sessions):
    """Runs two transactions against one document, in a controlled order."""

    class Racer:
        def __init__(self):
            self.first = sessions()
            self.second = sessions()
            self.observer = sessions()
            self.at_commit = threading.Event()
            self.release = threading.Event()
            self.second_finished = threading.Event()
            self.first_outcome = {}
            self.second_outcome = {}
            gate_commit(self.first, self.at_commit, self.release)
            # take the connection now, so the backend pid stays valid
            self.second_pid = backend_pid(self.second)

        def start_first(self, call):
            thread, self.first_outcome = run_in_thread(
                lambda: call(self.first), "first"
            )
            assert self.at_commit.wait(TIMEOUT), (
                "the first transaction never reached its commit"
            )
            self.first_thread = thread

        def start_second(self, call):
            def wrapped():
                try:
                    return call(self.second)
                finally:
                    self.second_finished.set()

            thread, self.second_outcome = run_in_thread(wrapped, "second")
            self.second_thread = thread

        def assert_blocked_on_the_lock(self):
            queued = wait_until(
                lambda: ungranted_locks(self.observer, self.second_pid) > 0
            )
            assert queued, (
                "the second transaction never queued on a row lock; PostgreSQL "
                "reports no ungranted lock for its backend"
            )
            assert not self.second_finished.wait(BLOCKED_WINDOW), (
                "the second transaction finished while the first still held the lock"
            )

        def release_first(self):
            self.release.set()
            join_or_fail(self.first_thread, "first")
            join_or_fail(self.second_thread, "second")

        def outcome(self, box):
            assert "error" not in box, f"unexpected error: {box['error']!r}"
            return box.get("value")

    return Racer()


@pytest.fixture
def statements(db):
    """Record every statement this session sends to PostgreSQL."""
    from contextlib import contextmanager

    recorded = []

    @contextmanager
    def capture():
        listener = lambda conn, cursor, statement, *a: recorded.append(statement)
        sa_event.listen(db.get_bind(), "before_cursor_execute", listener)
        try:
            yield recorded
        finally:
            sa_event.remove(db.get_bind(), "before_cursor_execute", listener)

    yield capture


class TestLockIsTaken:
    """The structural half: which statements lock and which must not."""

    def test_update_locks_the_row(self, db, prepare, statements):
        document_id = prepare()
        with statements() as sent:
            DocumentService.update(db, document_id, DocumentUpdate(number="ПС-777"))
        assert any("FOR UPDATE" in s for s in sent)

    def test_verify_locks_the_row(self, db, prepare, statements):
        document_id = prepare()
        with statements() as sent:
            DocumentService.verify(db, document_id)
        assert any("FOR UPDATE" in s for s in sent)

    def test_reject_locks_the_row(self, db, prepare, statements):
        document_id = prepare()
        with statements() as sent:
            DocumentService.reject(db, document_id, "не соответствует")
        assert any("FOR UPDATE" in s for s in sent)

    def test_get_does_not_lock(self, db, prepare, statements):
        document_id = prepare()
        with statements() as sent:
            DocumentService.get(db, document_id)
        assert not any("FOR UPDATE" in s for s in sent)

    def test_list_does_not_lock(self, db, prepare, statements):
        prepare()
        with statements() as sent:
            DocumentService.list(db)
        assert not any("FOR UPDATE" in s for s in sent)

    def test_create_does_not_lock(self, db, statements):
        document_type = DocumentType(name="Паспорт")
        db.add(document_type)
        db.commit()
        db.refresh(document_type)
        with statements() as sent:
            DocumentService.create(
                db, DocumentCreate(document_type_id=document_type.id, number="ПС-1")
            )
        assert not any("FOR UPDATE" in s for s in sent)

    def test_missing_document_takes_no_lock(self, db):
        assert DocumentService.update(db, 999_999, DocumentUpdate(number="X")) is None
        assert DocumentService.verify(db, 999_999) is None
        assert DocumentService.reject(db, 999_999, "причина") is None


class TestStaleInstance:
    """A session that loaded the document before a competitor committed."""

    def test_the_refresh_picks_up_a_committed_change(self, db, sessions, prepare):
        document_id = prepare(status=VERIFIED)

        # this session loads the document and keeps it in its identity map
        DocumentService.get(db, document_id)

        # another session moves it
        other = sessions()
        DocumentService.reject(other, document_id, "причина")

        # verify therefore reads the committed `rejected` rather than its own
        # cached `verified`, and performs the direct transition instead of
        # returning early as an idempotent re-confirmation
        assert DocumentService.verify(db, document_id).verification_status == VERIFIED
        assert history(db, document_id) == [
            (VERIFIED, REJECTED, "rejected", "причина"),
            (REJECTED, VERIFIED, "verified", None),
        ]

    def test_the_control_the_cached_instance_really_is_stale(self, db, sessions, prepare):
        # the other half of the pair: prove the instance really was out of date,
        # so the refresh above is doing work rather than confirming nothing
        document_id = prepare(status=VERIFIED)
        cached = DocumentService.get(db, document_id)

        other = sessions()
        DocumentService.reject(other, document_id, "причина")

        assert cached.verification_status == VERIFIED  # still the pre-commit value
        db.rollback()  # expires the instance; the next read goes back to the database
        assert db.get(Document, document_id).verification_status == REJECTED


class TestUncommittedChangesGuard:
    def test_update_is_refused(self, db, prepare):
        document_id = prepare()
        document = db.get(Document, document_id)
        document.number = "ПС-Локально"

        with pytest.raises(UncommittedDocumentChangesError) as info:
            DocumentService.update(db, document_id, DocumentUpdate(number="ПС-Новое"))
        assert info.value.document_id == document_id

        db.rollback()
        assert status_of(db, document_id) == PENDING

    def test_verify_is_refused(self, db, prepare):
        document_id = prepare()
        db.get(Document, document_id).notes = "черновик"

        with pytest.raises(UncommittedDocumentChangesError):
            DocumentService.verify(db, document_id)

        db.rollback()
        assert history(db, document_id) == []

    def test_reject_is_refused(self, db, prepare):
        document_id = prepare()
        db.get(Document, document_id).notes = "черновик"

        with pytest.raises(UncommittedDocumentChangesError):
            DocumentService.reject(db, document_id, "причина")

        db.rollback()
        assert history(db, document_id) == []

    def test_nothing_was_written(self, db, prepare):
        document_id = prepare()
        db.get(Document, document_id).notes = "черновик"
        with pytest.raises(UncommittedDocumentChangesError):
            DocumentService.verify(db, document_id)
        db.rollback()
        assert history(db, document_id) == []
        assert db.get(Document, document_id).notes is None


class TestConcurrentDecisions:
    def test_two_concurrent_verify(self, racer, prepare):
        document_id = prepare()

        racer.start_first(lambda s: DocumentService.verify(s, document_id))
        racer.start_second(lambda s: DocumentService.verify(s, document_id))
        racer.assert_blocked_on_the_lock()
        racer.release_first()

        assert racer.outcome(racer.first_outcome).verification_status == VERIFIED
        assert racer.outcome(racer.second_outcome).verification_status == VERIFIED
        assert status_of(racer.observer, document_id) == VERIFIED
        assert history(racer.observer, document_id) == [
            (PENDING, VERIFIED, "verified", None)
        ]

    def test_two_concurrent_reject(self, racer, prepare):
        document_id = prepare()

        racer.start_first(lambda s: DocumentService.reject(s, document_id, "первое"))
        racer.start_second(lambda s: DocumentService.reject(s, document_id, "второе"))
        racer.assert_blocked_on_the_lock()
        racer.release_first()

        assert status_of(racer.observer, document_id) == REJECTED
        # the second call is idempotent: the reason of the first decision stands
        assert history(racer.observer, document_id) == [
            (PENDING, REJECTED, "rejected", "первое")
        ]

    def test_verify_against_reject(self, racer, prepare):
        document_id = prepare()

        racer.start_first(lambda s: DocumentService.verify(s, document_id))
        racer.start_second(lambda s: DocumentService.reject(s, document_id, "причина"))
        racer.assert_blocked_on_the_lock()
        racer.release_first()

        # the second transaction reads `verified` and may reject it directly
        assert status_of(racer.observer, document_id) == REJECTED
        assert history(racer.observer, document_id) == [
            (PENDING, VERIFIED, "verified", None),
            (VERIFIED, REJECTED, "rejected", "причина"),
        ]

    def test_reject_against_verify(self, racer, prepare):
        document_id = prepare()

        racer.start_first(lambda s: DocumentService.reject(s, document_id, "причина"))
        racer.start_second(lambda s: DocumentService.verify(s, document_id))
        racer.assert_blocked_on_the_lock()
        racer.release_first()

        assert status_of(racer.observer, document_id) == VERIFIED
        assert history(racer.observer, document_id) == [
            (PENDING, REJECTED, "rejected", "причина"),
            (REJECTED, VERIFIED, "verified", None),
        ]

    def test_update_against_verify(self, racer, prepare):
        document_id = prepare(status=VERIFIED)

        racer.start_first(
            lambda s: DocumentService.update(s, document_id, DocumentUpdate(number="ПС-1"))
        )
        racer.start_second(lambda s: DocumentService.verify(s, document_id))
        racer.assert_blocked_on_the_lock()
        racer.release_first()

        assert status_of(racer.observer, document_id) == VERIFIED
        # exactly one `reopened`: the second transaction read the committed
        # `pending` instead of the `verified` its stale copy still held
        assert history(racer.observer, document_id) == [
            (VERIFIED, PENDING, "reopened", "significant_fields_changed"),
            (PENDING, VERIFIED, "verified", None),
        ]

    def test_update_against_reject(self, racer, prepare):
        document_id = prepare(status=REJECTED)

        racer.start_first(
            lambda s: DocumentService.update(s, document_id, DocumentUpdate(number="ПС-1"))
        )
        racer.start_second(lambda s: DocumentService.reject(s, document_id, "причина"))
        racer.assert_blocked_on_the_lock()
        racer.release_first()

        # the reopening moved the document to pending, so the waiting rejection
        # then applied to a fresh pending state and decided it
        assert status_of(racer.observer, document_id) == REJECTED
        assert history(racer.observer, document_id) == [
            (REJECTED, PENDING, "reopened", "significant_fields_changed"),
            (PENDING, REJECTED, "rejected", "причина"),
        ]

    def test_two_concurrent_updates_reopen_once(self, racer, prepare):
        document_id = prepare(status=VERIFIED)

        racer.start_first(
            lambda s: DocumentService.update(s, document_id, DocumentUpdate(number="ПС-1"))
        )
        racer.start_second(
            lambda s: DocumentService.update(s, document_id, DocumentUpdate(number="ПС-2"))
        )
        racer.assert_blocked_on_the_lock()
        racer.release_first()

        assert status_of(racer.observer, document_id) == PENDING
        assert history(racer.observer, document_id) == [
            (VERIFIED, PENDING, "reopened", "significant_fields_changed")
        ]


class TestAfterTheWait:
    def test_the_waiter_sees_the_committed_status(self, racer, prepare):
        document_id = prepare()

        racer.start_first(lambda s: DocumentService.verify(s, document_id))
        racer.start_second(lambda s: DocumentService.verify(s, document_id))
        racer.assert_blocked_on_the_lock()
        racer.release_first()

        # the waiter returned the refreshed row, not the one it blocked on
        waited = racer.outcome(racer.second_outcome)
        assert waited.verification_status == VERIFIED
        assert len(history(racer.observer, document_id)) == 1

    def test_a_repeated_decision_adds_no_event(self, sessions, prepare):
        document_id = prepare()
        first = sessions()
        DocumentService.verify(first, document_id)
        second = sessions()
        DocumentService.verify(second, document_id)
        assert history(sessions(), document_id) == [
            (PENDING, VERIFIED, "verified", None)
        ]

    def test_a_repeated_rejection_keeps_the_first_reason(self, sessions, prepare):
        document_id = prepare()
        first = sessions()
        DocumentService.reject(first, document_id, "первое")
        second = sessions()
        DocumentService.reject(second, document_id, "другое")
        assert history(sessions(), document_id) == [
            (PENDING, REJECTED, "rejected", "первое")
        ]

    def test_a_waiter_sees_a_concurrently_deleted_document(
        self, racer, sessions, prepare
    ):
        document_id = prepare()

        def delete_then_wait(session):
            session.execute(
                text("DELETE FROM documents WHERE id = :i"), {"i": document_id}
            )
            session.commit()  # gated: the row stays deleted-but-uncommitted

        racer.start_first(delete_then_wait)
        racer.start_second(lambda s: DocumentService.verify(s, document_id))
        racer.assert_blocked_on_the_lock()
        racer.release_first()

        # the waiting transaction re-evaluates the row after the delete commits
        # and finds nothing, which is reported as "no such document"
        assert racer.second_outcome.get("value") is None
        assert sessions().execute(
            text("SELECT count(*) FROM documents WHERE id = :i"),
            {"i": document_id},
        ).scalar() == 0


class TestTransactionOwnership:
    """The rule: end the transaction this method started, never the caller's.

    Every case below asks the same question in a different way — after the
    method returned, would another transaction have to wait, and did the caller's
    own work survive? The lock probe answers the first from the server, using
    `lock_timeout`, so nothing here depends on a sleep or on timing luck.
    """

    def test_verify_without_a_file_releases_the_lock(self, sessions, prepare):
        document_id = prepare(with_file=False)
        session = sessions()
        assert not session.in_transaction()

        with pytest.raises(DocumentHasNoFilesError):
            DocumentService.verify(session, document_id)

        assert not session.in_transaction()
        assert not lock_is_held(sessions, document_id)

    def test_reject_without_a_reason_releases_the_lock(self, sessions, prepare):
        document_id = prepare()
        session = sessions()

        with pytest.raises(RejectionReasonRequiredError):
            DocumentService.reject(session, document_id, "  ")

        assert not session.in_transaction()
        assert not lock_is_held(sessions, document_id)

    def test_update_with_an_inverted_merged_period_releases_the_lock(
        self, sessions, prepare
    ):
        # the schema can only compare the two bounds when both are sent together,
        # so the service-level check needs a stored bound plus a patched one
        document_id = prepare(status="has-period")
        session = sessions()

        with pytest.raises(InvalidValidityPeriodError):
            DocumentService.update(
                session, document_id, DocumentUpdate(valid_to=date(2026, 1, 1))
            )

        assert not session.in_transaction()
        assert not lock_is_held(sessions, document_id)

    def test_repeated_verify_releases_the_lock(self, sessions, prepare):
        document_id = prepare()
        first = sessions()
        DocumentService.verify(first, document_id)

        second = sessions()
        assert not second.in_transaction()
        result = DocumentService.verify(second, document_id)

        # checked before any attribute is read: touching an expired attribute
        # issues a SELECT, which autobegin turns into a new transaction
        assert not second.in_transaction()
        assert result.verification_status == VERIFIED
        assert not lock_is_held(sessions, document_id)
        assert history(sessions(), document_id) == [
            (PENDING, VERIFIED, "verified", None)
        ]

    def test_repeated_reject_releases_the_lock(self, sessions, prepare):
        document_id = prepare()
        first = sessions()
        DocumentService.reject(first, document_id, "первое")

        second = sessions()
        result = DocumentService.reject(second, document_id, "другое")

        assert not second.in_transaction()
        assert result.verification_status == REJECTED
        assert not lock_is_held(sessions, document_id)
        assert history(sessions(), document_id) == [
            (PENDING, REJECTED, "rejected", "первое")
        ]

    def test_empty_update_releases_the_lock(self, sessions, prepare):
        document_id = prepare()
        session = sessions()

        DocumentService.update(session, document_id, DocumentUpdate())

        assert not session.in_transaction()
        assert not lock_is_held(sessions, document_id)

    def test_update_with_identical_values_releases_the_lock(self, sessions, prepare):
        document_id = prepare()
        reader = sessions()
        number = reader.execute(
            text("SELECT number FROM documents WHERE id = :i"), {"i": document_id}
        ).scalar()
        reader.close()

        session = sessions()
        DocumentService.update(session, document_id, DocumentUpdate(number=number))

        assert not session.in_transaction()
        assert not lock_is_held(sessions, document_id)

    def test_a_missing_document_leaves_no_transaction(self, sessions, prepare):
        prepare()
        session = sessions()
        assert not session.in_transaction()

        assert DocumentService.update(session, 999_999, DocumentUpdate(number="X")) is None
        assert not session.in_transaction()
        assert DocumentService.verify(session, 999_999) is None
        assert not session.in_transaction()
        assert DocumentService.reject(session, 999_999, "причина") is None
        assert not session.in_transaction()

    def test_a_refused_session_can_be_reused_immediately(self, sessions, prepare):
        document_id = prepare(with_file=False)
        session = sessions()
        with pytest.raises(DocumentHasNoFilesError):
            DocumentService.verify(session, document_id)

        # same session, second attempt: no lingering state to trip over
        again = DocumentService.reject(session, document_id, "причина")
        assert again.verification_status == REJECTED
        assert history(sessions(), document_id) == [
            (PENDING, REJECTED, "rejected", "причина")
        ]

    def test_a_competing_session_does_not_wait_after_a_refusal(self, sessions, prepare):
        document_id = prepare(with_file=False)
        session = sessions()
        with pytest.raises(DocumentHasNoFilesError):
            DocumentService.verify(session, document_id)

        # the whole point: another transaction takes the row immediately, without
        # the caller having to remember to roll anything back
        acquired = threading.Event()
        release = threading.Event()
        holder = sessions()

        def take_and_hold():
            holder.execute(
                text("SELECT 1 FROM documents WHERE id = :i FOR UPDATE"),
                {"i": document_id},
            )
            acquired.set()
            assert release.wait(TIMEOUT), "gate never opened"
            holder.commit()

        worker, box = run_in_thread(take_and_hold, "holder")
        # if the refusal had left the lock held, this wait would time out
        assert acquired.wait(TIMEOUT), (
            "another transaction could not take the row after the refusal"
        )
        release.set()
        join_or_fail(worker, "holder")
        assert "error" not in box, box.get("error")
        holder.close()

    def test_a_caller_opened_transaction_is_not_rolled_back(self, sessions, prepare):
        document_id = prepare()
        session = sessions()
        session.execute(text("SELECT 1"))
        assert session.in_transaction()

        with pytest.raises(RejectionReasonRequiredError):
            DocumentService.reject(session, document_id, "  ")

        assert session.in_transaction()
        assert lock_is_held(sessions, document_id)

        session.rollback()
        assert not lock_is_held(sessions, document_id)

    def test_the_callers_pending_work_survives_a_refusal(self, sessions, prepare):
        document_id = prepare(with_file=False, issuer=True)
        session = sessions()
        issuer = session.query(Issuer).first()
        issuer.name = "правка вызывающего"
        session.execute(text("SELECT 1"))

        with pytest.raises(DocumentHasNoFilesError):
            DocumentService.verify(session, document_id)

        assert session.get(Issuer, issuer.id).name == "правка вызывающего"
        assert session.in_transaction()

        # it is still the caller's to commit, and it still works
        session.commit()
        reader = sessions()
        assert reader.execute(
            text("SELECT count(*) FROM issuers WHERE name = 'правка вызывающего'")
        ).scalar() == 1

    def test_the_guard_does_not_discard_local_changes(self, sessions, prepare):
        document_id = prepare()
        session = sessions()
        document = session.get(Document, document_id)
        document.notes = "черновик"

        with pytest.raises(UncommittedDocumentChangesError):
            DocumentService.verify(session, document_id)

        assert session.get(Document, document_id).notes == "черновик"
        session.rollback()

    def test_a_successful_path_still_commits_once(self, sessions, prepare, monkeypatch):
        document_id = prepare(status=VERIFIED)
        session = sessions()
        calls = []
        original = session.commit
        monkeypatch.setattr(
            session, "commit", lambda: (calls.append(1), original())[1]
        )

        DocumentService.update(session, document_id, DocumentUpdate(number="ПС-1"))

        assert len(calls) == 1
        assert history(sessions(), document_id) == [
            (VERIFIED, PENDING, "reopened", "significant_fields_changed")
        ]

    def test_history_stays_atomic_under_the_release(self, sessions, prepare):
        # the release runs on failure paths only; a committed transition must
        # leave the status and its event together
        document_id = prepare(status=VERIFIED)
        session = sessions()
        DocumentService.update(session, document_id, DocumentUpdate(number="ПС-2"))

        reader = sessions()
        assert reader.execute(
            text("SELECT verification_status FROM documents WHERE id = :i"),
            {"i": document_id},
        ).scalar() == PENDING
        assert history(sessions(), document_id) == [
            (VERIFIED, PENDING, "reopened", "significant_fields_changed")
        ]

    def test_successive_refusals_do_not_stack_locks(self, sessions, prepare):
        document_id = prepare(with_file=False)
        session = sessions()
        for _ in range(4):
            with pytest.raises(DocumentHasNoFilesError):
                DocumentService.verify(session, document_id)
            assert not session.in_transaction()
            assert not lock_is_held(sessions, document_id)


class TestLockReleaseOnFailure:
    """Who ends the transaction after a refusal.

    Before TASK-DOC-005F.2 this class asserted the opposite: a raised domain
    error left the transaction open and the lock held until someone remembered
    to roll back. That is what allowed a refused request to keep every other
    transaction on the document waiting. The service now ends the transaction it
    started, and these tests pin both halves of the rule.
    """

    def test_a_refusal_frees_the_lock_when_the_service_opened_it(
        self, sessions, prepare
    ):
        document_id = prepare()
        session = sessions()
        assert not session.in_transaction()

        with pytest.raises(RejectionReasonRequiredError):
            DocumentService.reject(session, document_id, "   ")

        assert not session.in_transaction()
        # the next transaction takes the row without waiting
        assert ungranted_locks(sessions(), backend_pid(session)) == 0
        other = sessions()
        assert DocumentService.verify(other, document_id).verification_status == VERIFIED
        assert history(sessions(), document_id) == [
            (PENDING, VERIFIED, "verified", None)
        ]

    def test_a_refusal_leaves_the_callers_transaction_alone(self, sessions, prepare):
        document_id = prepare()
        session = sessions()
        session.execute(text("SELECT 1"))       # the caller opened the transaction
        assert session.in_transaction()

        with pytest.raises(RejectionReasonRequiredError):
            DocumentService.reject(session, document_id, "   ")

        assert session.in_transaction(), "the caller's transaction was rolled back"
        assert lock_is_held(sessions, document_id), (
            "the lock must survive: the caller still owns the transaction"
        )

        # and the caller releases it exactly as it would any other
        session.rollback()
        assert not lock_is_held(sessions, document_id)
        assert DocumentService.verify(
            sessions(), document_id
        ).verification_status == VERIFIED

    def test_the_release_happens_before_the_method_returns(
        self, sessions, prepare
    ):
        # the point of the fix: no window in which the caller holds a lock it
        # does not know about
        document_id = prepare(with_file=False)
        session = sessions()
        with pytest.raises(DocumentHasNoFilesError):
            DocumentService.verify(session, document_id)
        assert not lock_is_held(sessions, document_id)

    def test_a_transaction_that_rolled_back_can_start_again(self, sessions, prepare):
        document_id = prepare()
        session = sessions()
        DocumentService.verify(session, document_id)
        session.rollback()
        again = DocumentService.verify(session, document_id)
        assert again.verification_status == VERIFIED


class TestDifferentDocuments:
    def test_two_documents_do_not_block_each_other(self, racer, prepare):
        first_id = prepare()
        second_id = prepare()

        racer.start_first(lambda s: DocumentService.verify(s, first_id))

        # the second document's row was never locked, so this must not wait
        racer.start_second(lambda s: DocumentService.verify(s, second_id))
        assert racer.second_finished.wait(TIMEOUT), (
            "an operation on an unrelated document waited for the lock"
        )
        assert ungranted_locks(racer.observer, racer.second_pid) == 0

        racer.release_first()
        assert racer.outcome(racer.second_outcome).verification_status == VERIFIED
        assert status_of(racer.observer, first_id) == VERIFIED
        assert status_of(racer.observer, second_id) == VERIFIED

    def test_the_same_document_is_serialised(self, racer, prepare):
        document_id = prepare()

        racer.start_first(lambda s: DocumentService.verify(s, document_id))
        racer.start_second(lambda s: DocumentService.reject(s, document_id, "причина"))
        racer.assert_blocked_on_the_lock()
        racer.release_first()

        # opposite outcome to the unrelated-document case: this one had to wait
        assert history(racer.observer, document_id) == [
            (PENDING, VERIFIED, "verified", None),
            (VERIFIED, REJECTED, "rejected", "причина"),
        ]


class TestBusinessRulesUnchanged:
    """The locking must not have moved a single rule."""

    def test_verify_still_needs_a_file(self, db, prepare):
        document_id = prepare(with_file=False)
        with pytest.raises(DocumentHasNoFilesError):
            DocumentService.verify(db, document_id)
        assert history(db, document_id) == []

    def test_reject_still_needs_a_reason(self, db, prepare):
        document_id = prepare()
        with pytest.raises(RejectionReasonRequiredError):
            DocumentService.reject(db, document_id, "  ")
        assert history(db, document_id) == []

    def test_notes_alone_still_preserve_the_verdict(self, db, prepare):
        document_id = prepare(status=VERIFIED)
        updated = DocumentService.update(db, document_id, DocumentUpdate(notes="правка"))
        assert updated.verification_status == VERIFIED
        assert history(db, document_id) == []

    def test_creation_starts_pending_without_events(self, db):
        document_type = DocumentType(name="Паспорт")
        db.add(document_type)
        db.commit()
        db.refresh(document_type)
        document = DocumentService.create(
            db, DocumentCreate(document_type_id=document_type.id, number="ПС-1")
        )
        assert document.verification_status == PENDING
        assert history(db, document.id) == []

    def test_exactly_one_commit_per_operation(self, db, prepare, monkeypatch):
        document_id = prepare(status=VERIFIED)
        calls = []
        original = db.commit
        monkeypatch.setattr(
            db, "commit", lambda: (calls.append(1), original())[1]
        )
        DocumentService.update(db, document_id, DocumentUpdate(number="ПС-1"))
        assert len(calls) == 1

    def test_the_status_and_the_event_land_together(self, sessions, prepare):
        document_id = prepare(status=VERIFIED)
        session = sessions()
        DocumentService.update(session, document_id, DocumentUpdate(number="ПС-1"))
        reader = sessions()
        assert reader.execute(
            text("SELECT verification_status FROM documents WHERE id = :i"),
            {"i": document_id},
        ).scalar() == PENDING
        assert len(history(sessions(), document_id)) == 1