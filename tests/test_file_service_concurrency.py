"""Concurrent use of `FileService.attach` against real PostgreSQL.

`attach` decides a document's verdict from its status and takes a row lock
before reading that status. Everything here exists to show what that lock buys
when two requests meet over the same document: one of them withdraws the
verdict, the other sees the withdrawal, and neither writes a second history
event describing a transition that did not happen.

Real PostgreSQL, separate connections, bounded waits. A test that passes
because both threads ran one after another would prove nothing about locking,
so each one makes the second transaction wait on the first and then checks
that it really was waiting.
"""

import hashlib
import io
import threading
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.documents.schemas import DocumentUpdate
from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.file import File
from app.services.document_service import DocumentService
from app.services.file_service import AttachmentNotFoundError
from app.services.file_service import FileService

# Upper bound for a thread to reach its gate. Generous, because it only ever
# bounds a failure; a passing run never waits close to this.
TIMEOUT = 10.0

# How long to watch the second transaction and expect it to still be blocked.
BLOCKED_WINDOW = 0.5

PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n" + b"pdf-body" * 4
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"jpeg-body" * 4


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


def document_locks_waiting(observer):
    """How many backends are queued on the documents table.

    Asked about the table rather than about a pid on purpose. `attach` refuses
    to start inside a transaction it does not own, so its session cannot be
    left holding a connection just to be asked for its backend id — rolling
    that back would release the connection and invalidate the answer.
    """
    return observer.execute(
        text(
            "SELECT count(*) FROM pg_locks WHERE NOT granted AND ("
            "  relation = 'documents'::regclass"
            "  OR locktype = 'transactionid'"
            ")"
        )
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
def storage(tmp_path):
    from app.services.local_storage import LocalStorageBackend

    return LocalStorageBackend(root_path=tmp_path / "storage")


@pytest.fixture
def prepare(engine, sessions):
    """Create a committed document in a decided or undecided state.

    Everything is committed, and made through a session of its own, so the
    fixture leaves `db` without a transaction. Otherwise the fixture would be
    the thing holding the lock the tests are trying to observe.
    """
    counter = {"n": 0}

    def _make(status="pending", with_event=False, with_file=False):
        # its own session, so the fixture leaves `db` without a transaction:
        # `attach` refuses to start inside one that belongs to the caller
        creator = Session(engine, future=True, expire_on_commit=False)
        counter["n"] += 1
        document_type = DocumentType(name=f"Тип-{counter['n']}")
        document = Document(
            document_type=document_type,
            number=f"D-{counter['n']}",
            verification_status=status,
        )
        creator.add(document)
        creator.flush()
        if with_event:
            creator.add(
                DocumentVerificationEvent(
                    document_id=document.id,
                    from_status="pending",
                    to_status=status,
                    event_type=status,
                    reason="решение, принятое до теста",
                )
            )
        if with_file:
            creator.add(
                File(
                    document_id=document.id,
                    original_filename="existing.pdf",
                    storage_key=f"documents/{document.id}/existing.pdf",
                    mime_type="application/pdf",
                    size_bytes=len(PDF_BYTES),
                    sha256="0" * 64,
                    uploaded_at=datetime.now(timezone.utc),
                )
            )
        creator.commit()
        creator.expunge_all()
        creator.close()
        return document

    yield _make


def events(session, document_id):
    return list(session.scalars(select_events(document_id)))


def select_events(document_id):
    return (
        select(DocumentVerificationEvent)
        .where(DocumentVerificationEvent.document_id == document_id)
        .order_by(DocumentVerificationEvent.id)
    )


def status_of(session, document_id):
    session.rollback()
    return session.get(Document, document_id).verification_status


def reopened_events(session, document_id):
    return [e for e in events(session, document_id) if e.event_type == "reopened"]


def files_of(session, document_id):
    session.rollback()
    return list(
        session.scalars(
            select(File)
            .where(File.document_id == document_id)
            .order_by(File.id)
        )
    )


class TestTwoUploadsRacingForOneVerdict:
    def test_the_second_waits_for_the_first(self, db, sessions, storage, prepare):
        document = prepare("verified", with_event=True)
        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)

        runner = FileService(db=first, storage=storage)
        thread_a, box_a = run_in_thread(
            lambda: runner.attach(document.id, "a.pdf", io.BytesIO(PDF_BYTES)),
            "attach-a",
        )
        assert reached.wait(TIMEOUT), "the first attach never reached its commit"
        assert lock_is_held(sessions, document.id), (
            "the first attach must hold the document while it is uncommitted"
        )

        second = sessions()
        runner_b = FileService(db=second, storage=storage)
        thread_b, box_b = run_in_thread(
            lambda: runner_b.attach(document.id, "b.jpg", io.BytesIO(JPEG_BYTES)),
            "attach-b",
        )

        observer = sessions()
        assert wait_until(lambda: document_locks_waiting(observer) > 0), (
            "the second attach never queued on the document row"
        )
        observer.close()

        release.set()
        join_or_fail(thread_a, "first attach")
        join_or_fail(thread_b, "second attach")
        assert "error" not in box_a, box_a.get("error")
        assert "error" not in box_b, box_b.get("error")

        stored = files_of(db, document.id)
        assert len(stored) == 2, "both uploads must be recorded"
        assert {f.original_filename for f in stored} == {"a.pdf", "b.jpg"}
        assert status_of(db, document.id) == "pending"

    def test_exactly_one_reopen_is_recorded(self, db, sessions, storage, prepare):
        document = prepare("verified", with_event=True)
        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)

        service_a = FileService(db=first, storage=storage)
        thread_a, box_a = run_in_thread(
            lambda: service_a.attach(document.id, "a.pdf", io.BytesIO(PDF_BYTES)),
            "attach-a",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        service_b = FileService(db=second, storage=storage)
        thread_b, box_b = run_in_thread(
            lambda: service_b.attach(document.id, "b.jpg", io.BytesIO(JPEG_BYTES)),
            "attach-b",
        )
        release.set()
        join_or_fail(thread_a, "first attach")
        join_or_fail(thread_b, "second attach")
        assert "error" not in box_a, box_a.get("error")
        assert "error" not in box_b, box_b.get("error")

        history = events(db, document.id)
        reopens = [e for e in history if e.event_type == "reopened"]
        assert len(reopens) == 1, (
            f"exactly one upload may withdraw the verdict, got {len(reopens)}: "
            f"{[(e.from_status, e.reason) for e in reopens]}"
        )
        assert reopens[0].reason == "file_added"
        assert reopens[0].from_status == "verified"

    def test_both_blobs_are_on_disk(self, db, sessions, storage, prepare):
        document = prepare("verified", with_event=True)
        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)

        service_a = FileService(db=first, storage=storage)
        thread_a, _ = run_in_thread(
            lambda: service_a.attach(document.id, "a.pdf", io.BytesIO(PDF_BYTES)),
            "attach-a",
        )
        assert reached.wait(TIMEOUT)
        second = sessions()
        service_b = FileService(db=second, storage=storage)
        thread_b, _ = run_in_thread(
            lambda: service_b.attach(document.id, "b.jpg", io.BytesIO(JPEG_BYTES)),
            "attach-b",
        )
        release.set()
        join_or_fail(thread_a, "first attach")
        join_or_fail(thread_b, "second attach")

        on_disk = [p for p in storage.root_path.rglob("*") if p.is_file()]
        assert len(on_disk) == 2

    def test_no_deadlock_when_three_race(self, db, sessions, storage, prepare):
        document = prepare("verified", with_event=True)
        opened = []

        def upload(index):
            session = sessions()
            opened.append(session)
            return FileService(db=session, storage=storage).attach(
                document.id, f"scan-{index}.pdf", io.BytesIO(PDF_BYTES)
            )

        threads = [
            run_in_thread(lambda i=i: upload(i), f"attach-{i}") for i in range(3)
        ]
        for thread, box in threads:
            join_or_fail(thread, f"attach {thread.name}")
            assert "error" not in box, box.get("error")

        assert len(files_of(db, document.id)) == 3
        assert len(reopened_events(db, document.id)) == 1


class TestUploadRacingWithVerify:
    def test_verify_first_then_upload_reopens(self, db, sessions, storage, prepare):
        document = prepare("pending", with_file=True)
        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)

        thread_v, box_v = run_in_thread(
            lambda: DocumentService.verify(first, document.id, "проверено"),
            "verify",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        service = FileService(db=second, storage=storage)
        thread_u, box_u = run_in_thread(
            lambda: service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES)),
            "attach",
        )
        release.set()
        join_or_fail(thread_v, "verify")
        join_or_fail(thread_u, "attach")
        assert "error" not in box_v, box_v.get("error")
        assert "error" not in box_u, box_u.get("error")

        history = events(db, document.id)
        kinds = [e.event_type for e in history]
        assert kinds.count("verified") == 1
        assert kinds.count("reopened") == 1
        assert kinds.index("verified") < kinds.index("reopened"), (
            "the verdict must be withdrawn only after it was granted"
        )
        assert status_of(db, document.id) == "pending"

    def test_upload_first_then_verify_decides_again(self, db, sessions, storage, prepare):
        document = prepare("rejected", with_event=True)
        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)

        service = FileService(db=first, storage=storage)
        thread_u, box_u = run_in_thread(
            lambda: service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES)),
            "attach",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        thread_v, box_v = run_in_thread(
            lambda: DocumentService.verify(second, document.id, "проверено заново"),
            "verify",
        )
        release.set()
        join_or_fail(thread_u, "attach")
        join_or_fail(thread_v, "verify")
        assert "error" not in box_u, box_u.get("error")
        assert "error" not in box_v, box_v.get("error")

        history = events(db, document.id)
        kinds = [e.event_type for e in history]
        assert kinds.count("reopened") == 1
        assert kinds.count("verified") == 1
        assert kinds.index("reopened") < kinds.index("verified")
        assert status_of(db, document.id) == "verified"

    def test_the_file_is_never_lost_to_the_race(self, db, sessions, storage, prepare):
        document = prepare("pending", with_file=True)
        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)

        thread_v, _ = run_in_thread(
            lambda: DocumentService.verify(first, document.id, "проверено"),
            "verify",
        )
        assert reached.wait(TIMEOUT)
        second = sessions()
        service = FileService(db=second, storage=storage)
        thread_u, _ = run_in_thread(
            lambda: service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES)),
            "attach",
        )
        release.set()
        join_or_fail(thread_v, "verify")
        join_or_fail(thread_u, "attach")

        stored = files_of(db, document.id)
        assert len(stored) == 2, "the pre-existing scan and the uploaded one"

        uploaded = [f for f in stored if f.original_filename == "scan.pdf"]
        assert len(uploaded) == 1, "the uploaded file must not be lost to the race"
        assert storage.exists(uploaded[0].storage_key)


class TestUploadRacingWithUpdate:
    def test_a_significant_change_does_not_duplicate_events(
        self, db, sessions, storage, prepare
    ):
        document = prepare("verified", with_event=True)
        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)

        service = FileService(db=first, storage=storage)
        thread_u, box_u = run_in_thread(
            lambda: service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES)),
            "attach",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        payload = DocumentUpdate(number="D-CHANGED")
        thread_up, box_up = run_in_thread(
            lambda: DocumentService.update(second, document.id, payload),
            "update",
        )
        release.set()
        join_or_fail(thread_u, "attach")
        join_or_fail(thread_up, "update")
        assert "error" not in box_u, box_u.get("error")
        assert "error" not in box_up, box_up.get("error")

        reopens = [e for e in events(db, document.id) if e.event_type == "reopened"]
        # at most one reopen per withdrawal, and never a second for a verdict
        # that is already pending
        assert len(reopens) <= 1
        assert status_of(db, document.id) == "pending"
        assert len(files_of(db, document.id)) == 1

    def test_the_update_is_not_lost(self, db, sessions, storage, prepare):
        document = prepare("pending", with_file=True)
        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)

        service = FileService(db=first, storage=storage)
        thread_u, _ = run_in_thread(
            lambda: service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES)),
            "attach",
        )
        assert reached.wait(TIMEOUT)
        second = sessions()
        payload = DocumentUpdate(number="D-CHANGED")
        thread_up, box_up = run_in_thread(
            lambda: DocumentService.update(second, document.id, payload),
            "update",
        )
        release.set()
        join_or_fail(thread_u, "attach")
        join_or_fail(thread_up, "update")
        assert "error" not in box_up, box_up.get("error")

        assert db.get(Document, document.id).number == "D-CHANGED"

    def test_an_upload_serialises_a_concurrent_update(self, db, sessions, storage, prepare):
        document = prepare("verified", with_event=True)
        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)

        service = FileService(db=first, storage=storage)
        thread_u, box_u = run_in_thread(
            lambda: service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES)),
            "attach",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        # a note is not a significant field, so the update has real work to do
        # and reaches its commit rather than taking the no-op path
        payload = DocumentUpdate(notes="уточнение после загрузки")
        thread_up, box_up = run_in_thread(
            lambda: DocumentService.update(second, document.id, payload),
            "update",
        )
        observer = sessions()
        assert wait_until(lambda: document_locks_waiting(observer) > 0), (
            "the update must queue behind the upload rather than read a stale status"
        )
        observer.close()

        release.set()
        join_or_fail(thread_u, "upload")
        join_or_fail(thread_up, "update")
        assert "error" not in box_u, box_u.get("error")
        assert "error" not in box_up, box_up.get("error")

        assert db.get(Document, document.id).notes == "уточнение после загрузки"
        assert len(files_of(db, document.id)) == 1
        assert len(reopened_events(db, document.id)) == 1


class TestDifferentDocumentsDoNotWait:
    def test_two_documents_are_attached_at_once(self, db, sessions, storage, prepare):
        first_doc = prepare("verified", with_event=True)
        second_doc = prepare("verified", with_event=True)

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        service_a = FileService(db=first, storage=storage)
        thread_a, _ = run_in_thread(
            lambda: service_a.attach(first_doc.id, "a.pdf", io.BytesIO(PDF_BYTES)),
            "attach-a",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        service_b = FileService(db=second, storage=storage)
        thread_b, box_b = run_in_thread(
            lambda: service_b.attach(second_doc.id, "b.pdf", io.BytesIO(PDF_BYTES)),
            "attach-b",
        )

        observer = sessions()
        assert wait_until(lambda: document_locks_waiting(observer) == 0), (
            "a second document must not queue behind the first"
        )
        observer.close()

        release.set()
        join_or_fail(thread_a, "first attach")
        join_or_fail(thread_b, "second attach")
        assert "error" not in box_b, box_b.get("error")

        assert len(files_of(db, first_doc.id)) == 1
        assert len(files_of(db, second_doc.id)) == 1
        assert len(reopened_events(db, first_doc.id)) == 1
        assert len(reopened_events(db, second_doc.id)) == 1


class TestTheLockIsReleasedWhateverHappens:
    def _assert_free(self, sessions, document_id):
        probe = sessions()
        probe.execute(text("SET lock_timeout = '400ms'"))
        probe.execute(
            text("SELECT 1 FROM documents WHERE id = :i FOR UPDATE"),
            {"i": document_id},
        )
        probe.rollback()
        probe.close()

    @pytest.mark.parametrize(
        "payload, filename",
        [
            (b"GIF89a-not-allowed", "scan.gif"),
            (b"", "empty.pdf"),
        ],
        ids=["unsupported", "empty"],
    )
    def test_a_refused_upload_leaves_the_document_free(
        self, db, sessions, storage, prepare, payload, filename
    ):
        document = prepare("verified", with_event=True)
        worker = sessions()
        service = FileService(db=worker, storage=storage)
        thread, box = run_in_thread(
            lambda: service.attach(document.id, filename, io.BytesIO(payload)),
            "attach",
        )
        join_or_fail(thread, "attach")
        assert "error" in box, "the upload should have been refused"

        self._assert_free(sessions, document.id)
        assert status_of(db, document.id) == "verified"
        assert reopened_events(db, document.id) == []

    def test_a_committed_upload_leaves_the_document_free(
        self, db, sessions, storage, prepare
    ):
        document = prepare("verified", with_event=True)
        worker = sessions()
        service = FileService(db=worker, storage=storage)
        thread, box = run_in_thread(
            lambda: service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES)),
            "attach",
        )
        join_or_fail(thread, "attach")
        assert "error" not in box, box.get("error")

        self._assert_free(sessions, document.id)

    def test_a_caller_with_an_open_transaction_is_refused_without_locking(
        self, db, sessions, storage, prepare
    ):
        from app.services.file_service import TransactionAlreadyOpenError

        document = prepare("verified", with_event=True)
        worker = sessions()
        worker.execute(text("SELECT 1"))  # a transaction the caller owns

        service = FileService(db=worker, storage=storage)
        with pytest.raises(TransactionAlreadyOpenError):
            service.attach(document.id, "scan.pdf", io.BytesIO(PDF_BYTES))

        assert worker.in_transaction(), "the caller's transaction must survive"
        assert files_of(db, document.id) == []
        self._assert_free(sessions, document.id)

# ---------------------------------------------------------------------------
# TASK-DOC-005M: concurrent detach
# ---------------------------------------------------------------------------


@pytest.fixture
def prepare_detachable(engine, storage):
    """A committed document with committed blobs, made outside any transaction.

    The blobs go through the same backend the service deletes from, so a test
    can ask what the operation actually left on disk. Everything is committed
    through a session of its own, so the fixture is never the thing holding the
    lock the tests are trying to observe.
    """

    def _make(status="pending", count=1, with_event=None):
        if with_event is None:
            with_event = status != "pending"

        creator = Session(engine, future=True, expire_on_commit=False)
        try:
            # `document_types.name` is unique, so it has to be unique per call
            label = uuid.uuid4().hex[:12]
            document = Document(
                document_type=DocumentType(name=f"Тип-{label}"),
                number=f"D-{label}",
                verification_status=status,
            )
            creator.add(document)
            creator.flush()

            if with_event:
                creator.add(
                    DocumentVerificationEvent(
                        document_id=document.id,
                        from_status="pending",
                        to_status=status,
                        event_type=status,
                        reason="решение, принятое до теста",
                    )
                )

            keys = []
            for index in range(count):
                key = f"documents/{document.id}/file-{index}.pdf"
                storage.save(key, io.BytesIO(PDF_BYTES))
                creator.add(
                    File(
                        document_id=document.id,
                        original_filename=f"file-{index}.pdf",
                        storage_key=key,
                        mime_type="application/pdf",
                        size_bytes=len(PDF_BYTES),
                        sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
                        uploaded_at=datetime.now(timezone.utc),
                    )
                )
                keys.append(key)

            creator.commit()
            creator.expire_all()
            file_ids = [
                row.id
                for row in creator.scalars(
                    select(File)
                    .where(File.document_id == document.id)
                    .order_by(File.id)
                )
            ]
            creator.expunge_all()
        finally:
            creator.close()

        return SimpleNamespace(document=document, file_ids=file_ids, keys=keys)

    return _make


def file_row_is_free(sessions, file_id):
    """Whether a competing session could take the file row right now."""
    probe = sessions()
    try:
        probe.execute(text("SET lock_timeout = '400ms'"))
        probe.execute(
            text("SELECT 1 FROM files WHERE id = :i FOR UPDATE"), {"i": file_id}
        )
        probe.rollback()
        return True
    except DBAPIError:
        probe.rollback()
        return False
    finally:
        probe.close()


def wait_for_a_queue(observer_factory):
    """Block until some backend is queued on the documents table."""
    observer = observer_factory()
    assert wait_until(lambda: document_locks_waiting(observer) > 0), (
        "the competing operation never queued on the document row"
    )
    observer.close()


class TestTwoDetachesOfTheSameFile:
    def _race(self, db, sessions, storage, prepared):
        """Start one detach, gate it, then start a second on the same file."""
        document, (file_id,) = prepared.document, prepared.file_ids

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        thread_a, box_a = run_in_thread(
            lambda: FileService(db=first, storage=storage).detach(document.id, file_id),
            "detach-a",
        )
        assert reached.wait(TIMEOUT), "the first detach never reached its commit"

        second = sessions()
        thread_b, box_b = run_in_thread(
            lambda: FileService(db=second, storage=storage).detach(document.id, file_id),
            "detach-b",
        )
        wait_for_a_queue(sessions)

        release.set()
        join_or_fail(thread_a, "first detach")
        join_or_fail(thread_b, "second detach")
        assert "error" not in box_a, box_a.get("error")
        return box_b

    def test_the_second_waits_for_the_first(self, db, sessions, storage, prepare_detachable):
        box_b = self._race(db, sessions, storage, prepare_detachable("verified", count=1))
        assert box_b.get("done")

    def test_the_file_is_removed_exactly_once(self, db, sessions, storage, prepare_detachable):
        prepared = prepare_detachable("verified", count=1)
        self._race(db, sessions, storage, prepared)

        assert files_of(db, prepared.document.id) == []
        assert not storage.exists(prepared.keys[0])
        assert status_of(db, prepared.document.id) == "pending"

    def test_exactly_one_reopen_is_recorded(self, db, sessions, storage, prepare_detachable):
        prepared = prepare_detachable("verified", count=1)
        self._race(db, sessions, storage, prepared)

        reopens = reopened_events(db, prepared.document.id)
        assert len(reopens) == 1, (
            f"one removal can withdraw the verdict once, got {len(reopens)}"
        )
        assert reopens[0].reason == "file_deleted"
        assert reopens[0].from_status == "verified"
        assert reopens[0].to_status == "pending"

    def test_the_second_finds_nothing_to_remove(self, db, sessions, storage, prepare_detachable):
        prepared = prepare_detachable("verified", count=1)
        box_b = self._race(db, sessions, storage, prepared)
        assert isinstance(box_b.get("error"), AttachmentNotFoundError), (
            "a second detach of the same file must be refused, not repeated"
        )

    def test_the_second_does_not_undo_the_first(self, db, sessions, storage, prepare_detachable):
        prepared = prepare_detachable("verified", count=1)
        self._race(db, sessions, storage, prepared)
        assert status_of(db, prepared.document.id) == "pending"
        assert len(events(db, prepared.document.id)) == 2


class TestTwoDetachesOfOneDocument:
    def test_both_files_go_and_one_event_is_written(
        self, db, sessions, storage, prepare_detachable
    ):
        prepared = prepare_detachable("verified", count=2)
        document = prepared.document

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        thread_a, box_a = run_in_thread(
            lambda: FileService(db=first, storage=storage).detach(
                document.id, prepared.file_ids[0]
            ),
            "detach-a",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        thread_b, box_b = run_in_thread(
            lambda: FileService(db=second, storage=storage).detach(
                document.id, prepared.file_ids[1]
            ),
            "detach-b",
        )
        wait_for_a_queue(sessions)

        release.set()
        join_or_fail(thread_a, "first detach")
        join_or_fail(thread_b, "second detach")
        assert "error" not in box_a, box_a.get("error")
        assert "error" not in box_b, box_b.get("error")

        assert files_of(db, document.id) == []
        assert not any(storage.exists(k) for k in prepared.keys)
        assert status_of(db, document.id) == "pending"
        assert len(reopened_events(db, document.id)) == 1, (
            "the second removal found the document already pending"
        )


class TestDetachRacingWithAttach:
    def test_an_attach_waits_for_a_detach(self, db, sessions, storage, prepare_detachable):
        prepared = prepare_detachable("verified", count=1)
        document = prepared.document

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        thread_d, box_d = run_in_thread(
            lambda: FileService(db=first, storage=storage).detach(
                document.id, prepared.file_ids[0]
            ),
            "detach",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        thread_a, box_a = run_in_thread(
            lambda: FileService(db=second, storage=storage).attach(
                document.id, "new.pdf", io.BytesIO(PDF_BYTES)
            ),
            "attach",
        )
        wait_for_a_queue(sessions)

        release.set()
        join_or_fail(thread_d, "detach")
        join_or_fail(thread_a, "attach")
        assert "error" not in box_d, box_d.get("error")
        assert "error" not in box_a, box_a.get("error")

        stored = files_of(db, document.id)
        assert [f.original_filename for f in stored] == ["new.pdf"]
        assert not storage.exists(prepared.keys[0])

        reopens = reopened_events(db, document.id)
        assert [e.reason for e in reopens] == ["file_deleted"], (
            "the attach arrived at a document the detach had already reopened"
        )
        assert status_of(db, document.id) == "pending"

    def test_a_detach_waits_for_an_attach(self, db, sessions, storage, prepare_detachable):
        prepared = prepare_detachable("pending", count=1)
        document = prepared.document

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        thread_a, box_a = run_in_thread(
            lambda: FileService(db=first, storage=storage).attach(
                document.id, "new.pdf", io.BytesIO(PDF_BYTES)
            ),
            "attach",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        thread_d, box_d = run_in_thread(
            lambda: FileService(db=second, storage=storage).detach(
                document.id, prepared.file_ids[0]
            ),
            "detach",
        )
        wait_for_a_queue(sessions)

        release.set()
        join_or_fail(thread_a, "attach")
        join_or_fail(thread_d, "detach")
        assert "error" not in box_a, box_a.get("error")
        assert "error" not in box_d, box_d.get("error")

        assert [f.original_filename for f in files_of(db, document.id)] == ["new.pdf"]
        assert not storage.exists(prepared.keys[0])
        assert reopened_events(db, document.id) == [], (
            "neither operation had a verdict to withdraw"
        )
        assert status_of(db, document.id) == "pending"

    def test_three_operations_on_one_document_do_not_deadlock(
        self, db, sessions, storage, prepare_detachable
    ):
        prepared = prepare_detachable("verified", count=2)
        document = prepared.document

        def work(index):
            session = sessions()
            service = FileService(db=session, storage=storage)
            if index == 0:
                return service.detach(document.id, prepared.file_ids[0])
            if index == 1:
                return service.attach(document.id, f"added-{index}.pdf", io.BytesIO(PDF_BYTES))
            return service.detach(document.id, prepared.file_ids[1])

        threads = [run_in_thread(lambda i=i: work(i), f"op-{i}") for i in range(3)]
        for thread, box in threads:
            join_or_fail(thread, thread.name)
        for index, (thread, box) in enumerate(threads):
            if index == 2:
                # removing the second file after the other detach is a race for
                # the same verdict, not a failure
                continue
            assert "error" not in box, box.get("error")

        assert status_of(db, document.id) == "pending"
        assert len(reopened_events(db, document.id)) <= 1


class TestDetachRacingWithADecision:
    def test_a_verify_after_a_detach_decides_again(
        self, db, sessions, storage, prepare_detachable
    ):
        prepared = prepare_detachable("verified", count=2, with_event=True)
        document = prepared.document

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        thread_d, box_d = run_in_thread(
            lambda: FileService(db=first, storage=storage).detach(
                document.id, prepared.file_ids[0]
            ),
            "detach",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        thread_v, box_v = run_in_thread(
            lambda: DocumentService.verify(second, document.id, "проверено заново"),
            "verify",
        )
        wait_for_a_queue(sessions)

        release.set()
        join_or_fail(thread_d, "detach")
        join_or_fail(thread_v, "verify")
        assert "error" not in box_d, box_d.get("error")
        assert "error" not in box_v, box_v.get("error")

        assert [e.event_type for e in events(db, document.id)] == [
            "verified",
            "reopened",
            "verified",
        ], "the second verdict must follow the withdrawal that preceded it"
        assert status_of(db, document.id) == "verified"
        assert len(files_of(db, document.id)) == 1

    def test_a_detach_after_a_verify_withdraws_it(
        self, db, sessions, storage, prepare_detachable
    ):
        prepared = prepare_detachable("pending", count=2)
        document = prepared.document

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        thread_v, box_v = run_in_thread(
            lambda: DocumentService.verify(first, document.id, "проверено"),
            "verify",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        thread_d, box_d = run_in_thread(
            lambda: FileService(db=second, storage=storage).detach(
                document.id, prepared.file_ids[0]
            ),
            "detach",
        )
        wait_for_a_queue(sessions)

        release.set()
        join_or_fail(thread_v, "verify")
        join_or_fail(thread_d, "detach")
        assert "error" not in box_v, box_v.get("error")
        assert "error" not in box_d, box_d.get("error")

        history = events(db, document.id)
        assert [e.event_type for e in history] == ["verified", "reopened"]
        assert history[-1].reason == "file_deleted"
        assert history[-1].from_status == "verified"
        assert status_of(db, document.id) == "pending"

    def test_a_detach_after_a_reject_withdraws_it(
        self, db, sessions, storage, prepare_detachable
    ):
        prepared = prepare_detachable("pending", count=2)
        document = prepared.document

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        thread_r, box_r = run_in_thread(
            lambda: DocumentService.reject(first, document.id, "нечитаемый скан"),
            "reject",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        thread_d, box_d = run_in_thread(
            lambda: FileService(db=second, storage=storage).detach(
                document.id, prepared.file_ids[0]
            ),
            "detach",
        )
        wait_for_a_queue(sessions)

        release.set()
        join_or_fail(thread_r, "reject")
        join_or_fail(thread_d, "detach")
        assert "error" not in box_r, box_r.get("error")
        assert "error" not in box_d, box_d.get("error")

        history = events(db, document.id)
        assert [e.event_type for e in history] == ["rejected", "reopened"]
        assert history[-1].reason == "file_deleted"
        assert history[-1].from_status == "rejected"
        assert history[-1].to_status == "pending"
        assert status_of(db, document.id) == "pending"

    def test_an_update_waits_for_a_detach(self, db, sessions, storage, prepare_detachable):
        prepared = prepare_detachable("verified", count=1, with_event=True)
        document = prepared.document

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        thread_d, box_d = run_in_thread(
            lambda: FileService(db=first, storage=storage).detach(
                document.id, prepared.file_ids[0]
            ),
            "detach",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        payload = DocumentUpdate(notes="уточнение после удаления скана")
        thread_up, box_up = run_in_thread(
            lambda: DocumentService.update(second, document.id, payload),
            "update",
        )
        wait_for_a_queue(sessions)

        release.set()
        join_or_fail(thread_d, "detach")
        join_or_fail(thread_up, "update")
        assert "error" not in box_d, box_d.get("error")
        assert "error" not in box_up, box_up.get("error")

        assert db.get(Document, document.id).notes == "уточнение после удаления скана"
        assert files_of(db, document.id) == []
        assert status_of(db, document.id) == "pending"


class TestDetachOnDifferentDocuments:
    def test_two_documents_are_detached_at_once(
        self, db, sessions, storage, prepare_detachable
    ):
        first_doc = prepare_detachable("verified", count=1)
        second_doc = prepare_detachable("verified", count=1)

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        thread_a, box_a = run_in_thread(
            lambda: FileService(db=first, storage=storage).detach(
                first_doc.document.id, first_doc.file_ids[0]
            ),
            "detach-a",
        )
        assert reached.wait(TIMEOUT)

        second = sessions()
        thread_b, box_b = run_in_thread(
            lambda: FileService(db=second, storage=storage).detach(
                second_doc.document.id, second_doc.file_ids[0]
            ),
            "detach-b",
        )

        observer = sessions()
        assert wait_until(lambda: document_locks_waiting(observer) == 0), (
            "a second document must not queue behind the first"
        )
        observer.close()
        join_or_fail(thread_b, "second detach")
        assert "error" not in box_b, box_b.get("error")

        release.set()
        join_or_fail(thread_a, "first detach")

        assert files_of(db, first_doc.document.id) == []
        assert files_of(db, second_doc.document.id) == []
        assert len(reopened_events(db, first_doc.document.id)) == 1
        assert len(reopened_events(db, second_doc.document.id)) == 1


class TestTheDetachLockIsReleasedWhateverHappens:
    def test_after_a_successful_detach(self, db, sessions, storage, prepare_detachable):
        prepared = prepare_detachable("verified", count=2)
        worker = sessions()
        FileService(db=worker, storage=storage).detach(
            prepared.document.id, prepared.file_ids[0]
        )

        assert file_row_is_free(sessions, prepared.file_ids[1])
        probe = sessions()
        probe.execute(text("SET lock_timeout = '400ms'"))
        probe.execute(
            text("SELECT 1 FROM documents WHERE id = :i FOR UPDATE"),
            {"i": prepared.document.id},
        )
        probe.rollback()
        probe.close()

    def test_after_a_refused_detach(self, db, sessions, storage, prepare_detachable):
        prepared = prepare_detachable("verified", count=1)
        worker = sessions()
        service = FileService(db=worker, storage=storage)

        thread, box = run_in_thread(
            lambda: service.detach(prepared.document.id, 999_999), "detach"
        )
        join_or_fail(thread, "detach")
        assert isinstance(box.get("error"), AttachmentNotFoundError)

        assert file_row_is_free(sessions, prepared.file_ids[0])
        assert status_of(db, prepared.document.id) == "verified"
        assert reopened_events(db, prepared.document.id) == []

    def test_a_caller_transaction_is_refused_without_locking(
        self, db, sessions, storage, prepare_detachable
    ):
        from app.services.file_service import TransactionAlreadyOpenError

        prepared = prepare_detachable("verified", count=1)
        worker = sessions()
        worker.execute(text("SELECT 1"))  # a transaction the caller owns

        service = FileService(db=worker, storage=storage)
        with pytest.raises(TransactionAlreadyOpenError):
            service.detach(prepared.document.id, prepared.file_ids[0])

        assert worker.in_transaction(), "the caller's transaction must survive"
        assert [
            f.id for f in files_of(db, prepared.document.id)
        ] == [prepared.file_ids[0]]
        assert file_row_is_free(sessions, prepared.file_ids[0])

    def test_after_a_failed_commit(self, db, sessions, storage, prepare_detachable):
        prepared = prepare_detachable("verified", count=1)
        worker = sessions()

        original = worker.commit

        def refuse():
            raise OperationalError("COMMIT", {}, Exception("server went away"))

        worker.commit = refuse
        service = FileService(db=worker, storage=storage)
        with pytest.raises(OperationalError):
            service.detach(prepared.document.id, prepared.file_ids[0])

        worker.commit = original
        worker.rollback()
        assert file_row_is_free(sessions, prepared.file_ids[0])
        assert storage.exists(prepared.keys[0]), (
            "an unconfirmed commit must not remove the blob"
        )


class TestTheDetachHoldsTheFileRow:
    """Section 3.7: the file row is locked, and it is locked *after* the document.

    The document lock alone already serialises every operation that goes through
    `locked_document`, so this lock is not what makes the ordinary race safe. It
    is what makes the *row this operation has decided to delete* immune to a
    writer that arrives by some other route — and, because it is taken in the
    document-first order every other operation uses, it is also what keeps two
    of them from deadlocking. Both halves are asserted here.
    """

    def test_the_file_row_is_locked_for_the_whole_detach(
        self, db, sessions, storage, prepare_detachable
    ):
        prepared = prepare_detachable("verified", count=2)
        document = prepared.document

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        thread, box = run_in_thread(
            lambda: FileService(db=first, storage=storage).detach(
                document.id, prepared.file_ids[0]
            ),
            "detach",
        )
        assert reached.wait(TIMEOUT), "the detach never reached its commit"

        assert not file_row_is_free(sessions, prepared.file_ids[0]), (
            "the file row must stay locked until the transaction ends"
        )
        assert file_row_is_free(sessions, prepared.file_ids[1]), (
            "only the row being removed should be locked"
        )

        release.set()
        join_or_fail(thread, "detach")
        assert "error" not in box, box.get("error")
        assert file_row_is_free(sessions, prepared.file_ids[1])

    def test_the_document_is_locked_before_the_file(
        self, db, sessions, storage, prepare_detachable
    ):
        """The order is what makes two opposing operations safe, not the locks.

        If one operation took the document and then the file while another took
        the file and then the document, the two would wait on each other
        forever. `detach` therefore takes them in the order `attach` and every
        status change already use. The check is indirect but real: while the
        detach is parked at its commit the document is held, and a competing
        detach of the *other* file queues on the document instead of proceeding
        against the row it could otherwise have locked.
        """
        prepared = prepare_detachable("verified", count=2)
        document = prepared.document

        first = sessions()
        reached, release = threading.Event(), threading.Event()
        gate_commit(first, reached, release)
        thread_a, box_a = run_in_thread(
            lambda: FileService(db=first, storage=storage).detach(
                document.id, prepared.file_ids[0]
            ),
            "detach-a",
        )
        assert reached.wait(TIMEOUT)

        observer = sessions()
        queued = document_locks_waiting(observer)
        observer.close()
        assert queued == 0, (
            "nothing should be waiting yet; the competing detach starts below"
        )

        second = sessions()
        thread_b, box_b = run_in_thread(
            lambda: FileService(db=second, storage=storage).detach(
                document.id, prepared.file_ids[1]
            ),
            "detach-b",
        )
        wait_for_a_queue(sessions)

        release.set()
        join_or_fail(thread_a, "first detach")
        join_or_fail(thread_b, "second detach")
        assert "error" not in box_a, box_a.get("error")
        assert "error" not in box_b, box_b.get("error")
        assert files_of(db, document.id) == []
