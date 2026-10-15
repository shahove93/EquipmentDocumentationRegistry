"""`app.services.transaction` on its own.

`DocumentService` keeps its own tests for behaviour; these cover the parts that
are new with the extraction and that no existing test could have asserted: that
the locking read exists in exactly one place, that the module commits nothing
on its own, that the refusal travels from the shared module to the service's
domain error without changing its identity, and that the extraction introduced
no import cycle.

The database checks run against the scratch schema from the `engine` fixture, so
the working `public` schema is never touched.
"""

import ast
import inspect
import subprocess
import sys
import textwrap
from contextlib import contextmanager

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_type import DocumentType
from app.services import document_service, file_service, transaction, verification_history
from app.services.document_service import (
    DocumentService,
    UncommittedDocumentChangesError,
)
from app.services.transaction import (
    UncommittedChangesInSession,
    locked_document,
    release,
    transaction_existed_on_entry,
)


@pytest.fixture
def sessions(engine):
    """Independent sessions on the scratch schema."""
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    made = []

    def _open():
        made.append(factory())
        return made[-1]

    yield _open
    for made_session in made:
        made_session.rollback()
        made_session.close()


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

    def _make(status: str = "pending") -> Document:
        counter["n"] += 1
        row = Document(
            document_type_id=document_type.id,
            number=f"ПС-{counter['n']:03d}",
            verification_status=status,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _make


@contextmanager
def captured(db: Session):
    """Record every statement this session sends to PostgreSQL."""
    recorded = []

    def listener(conn, cursor, statement, *args):
        recorded.append(statement)

    sa_event.listen(db.get_bind(), "before_cursor_execute", listener)
    try:
        yield recorded
    finally:
        sa_event.remove(db.get_bind(), "before_cursor_execute", listener)


class TestTheLockingRead:
    def test_it_emits_for_update(self, db, make_document):
        document = make_document()
        with captured(db) as sent:
            locked_document(db, document.id)
        assert any("FOR UPDATE" in s for s in sent)

    def test_it_refreshes_an_instance_cached_before_a_competitor_committed(
        self, db, sessions, make_document
    ):
        # the whole point of populate_existing: a document loaded before the
        # competing transaction committed must not decide on its old attributes
        document = make_document("verified")
        cached = DocumentService.get(db, document.id)

        other = sessions()
        DocumentService.reject(other, document.id, "причина")

        assert cached.verification_status == "verified"  # still the cached copy
        assert locked_document(db, document.id).verification_status == "rejected"

    def test_populate_existing_is_set_on_the_statement(self):
        statement = inspect.getsource(transaction.locked_document)
        assert "populate_existing=True" in statement
        assert ".with_for_update()" in statement

    def test_it_returns_none_for_a_missing_row(self, db):
        assert locked_document(db, 999_999) is None

    def test_it_never_commits_or_rolls_back(self, db, make_document, monkeypatch):
        # `flush` is deliberately not asserted here: the test session runs with
        # autoflush on, so `db.get` may flush on its own account. What matters
        # is that the function never decides anything about the transaction.
        document = make_document()
        calls = []
        for name in ("commit", "rollback"):
            monkeypatch.setattr(db, name, lambda name=name: calls.append(name))

        assert locked_document(db, document.id) is not None
        assert calls == []

    def test_its_own_code_never_flushes(self):
        assert "flush" not in {
            node.attr
            for node in ast.walk(ast.parse(inspect.getsource(transaction)))
            if isinstance(node, ast.Attribute)
        }

    def test_it_needs_no_commit_to_hold_the_row(self, db, make_document):
        # the lock is taken by the read; no write is required to keep it, which
        # is what makes the guard on `modified` necessary
        document = make_document()
        locked_document(db, document.id)
        assert db.in_transaction()

    def test_two_documents_are_independent(self, db, make_document):
        first, second = make_document("verified"), make_document("rejected")
        assert locked_document(db, first.id).verification_status == "verified"
        assert locked_document(db, second.id).verification_status == "rejected"


class TestTheGuard:
    def test_it_refuses_before_writing(self, db, make_document):
        document = make_document()
        db.get(Document, document.id).notes = "черновик"

        with pytest.raises(UncommittedChangesInSession) as info:
            locked_document(db, document.id)

        assert info.value.document_id == document.id
        assert db.get(Document, document.id).notes == "черновик"

    def test_it_fires_before_the_locking_statement(self, db, make_document):
        document = make_document()
        db.get(Document, document.id).notes = "черновик"

        with captured(db) as sent:
            with pytest.raises(UncommittedChangesInSession):
                locked_document(db, document.id)

        assert not any("FOR UPDATE" in s for s in sent), (
            "the lock was taken before the guard refused the call"
        )

    def test_it_does_not_fire_for_a_clean_session(self, db, make_document):
        document = make_document()
        assert locked_document(db, document.id) is not None

    def test_it_names_the_document_without_naming_a_service(self):
        # the shared module must not presume which service called it
        text_message = str(UncommittedChangesInSession(42))
        assert "42" in text_message
        assert "DocumentService" not in text_message
        assert "FileService" not in text_message


class TestTransactionOwnership:
    def test_it_reports_the_state_before_any_statement(self, db):
        assert transaction_existed_on_entry(db) is False
        db.execute(text("SELECT 1"))
        assert transaction_existed_on_entry(db) is True

    def test_release_ends_a_transaction_the_service_opened(self, db):
        db.execute(text("SELECT 1"))
        assert db.in_transaction()
        release(db, True)
        assert not db.in_transaction()

    def test_release_leaves_a_callers_transaction_alone(self, db, make_document):
        document = make_document()
        db.execute(text("SELECT 1"))
        assert db.in_transaction()
        release(db, False)
        assert db.in_transaction()

    def test_release_never_commits(self, db, monkeypatch):
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append("commit"))
        db.execute(text("SELECT 1"))
        release(db, True)
        assert calls == []


class TestTranslation:
    def test_the_domain_error_is_what_a_caller_catches(self, db, make_document):
        document = make_document()
        db.get(Document, document.id).notes = "черновик"

        with pytest.raises(UncommittedDocumentChangesError) as info:
            DocumentService._locked_document(db, document.id)

        assert info.value.document_id == document.id

    def test_the_identifier_survives_the_translation(self, db, make_document):
        document = make_document()
        db.get(Document, document.id).notes = "черновик"

        with pytest.raises(UncommittedDocumentChangesError) as info:
            DocumentService._locked_document(db, document.id)
        assert str(document.id) in str(info.value)

    def test_the_signal_is_the_cause(self, db, make_document):
        document = make_document()
        db.get(Document, document.id).notes = "черновик"

        with pytest.raises(UncommittedDocumentChangesError) as info:
            DocumentService._locked_document(db, document.id)
        assert isinstance(info.value.__cause__, UncommittedChangesInSession)

    def test_the_class_is_reachable_from_its_original_path(self):
        # §6.4: existing imports must keep working, unchanged
        from app.services.document_service import (
            UncommittedDocumentChangesError as original,
        )

        assert original is UncommittedDocumentChangesError
        assert original.__name__ == "UncommittedDocumentChangesError"
        assert original.__module__ == "app.services.document_service"

    def test_it_is_still_a_document_service_error(self):
        assert issubclass(
            UncommittedDocumentChangesError, document_service.DocumentServiceError
        )

    def test_the_unchanged_call_succeeds(self, db, make_document):
        document = make_document()
        assert DocumentService._locked_document(db, document.id) is not None
        assert DocumentService._locked_document(db, 999_999) is None


class TestNoDuplication:
    """Each locking read must live where it is owned, and nowhere else.

    Checked on the parsed tree rather than on the source text: the prose in
    `document_service` legitimately names `populate_existing` while explaining
    that it does not issue it.
    """

    DOCUMENT_READERS = (transaction, document_service, file_service, verification_history)

    def names_in(self, module):
        """Every attribute and identifier the module's code actually uses."""
        tree = ast.parse(inspect.getsource(module))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                found.add(node.attr)
            elif isinstance(node, ast.Name):
                found.add(node.id)
            elif isinstance(node, ast.keyword) and node.arg:
                found.add(node.arg)
        return found

    def locks_a_document(self, module):
        """Whether the module issues the locking read of a `documents` row.

        Both halves are required, so neither is misleading on its own:
        `document_service` legitimately lists documents with a plain
        `select(Document)`, and `file_service` legitimately locks a `files` row.
        A document lock is the two together — a select of `Document` issued by a
        module that also reaches for `with_for_update`.
        """
        return (
            "select(Document)" in inspect.getsource(module)
            and "with_for_update" in self.names_in(module)
        )

    def test_the_document_locking_read_is_issued_once(self):
        """The document lock belongs to `transaction.py` and to nobody else.

        This is the invariant TASK-DOC-005J established, and it is still
        enforced literally for the document: `locked_document()` is the only
        statement anywhere that locks a `documents` row, so the two services
        cannot drift into two different answers to "may I write this document".
        """
        readers = [
            module.__name__
            for module in self.DOCUMENT_READERS
            if self.locks_a_document(module)
        ]
        assert readers == ["app.services.transaction"], (
            f"документ должно блокировать только transaction.py, найдено: {readers}"
        )

    def test_the_file_locking_read_lives_in_the_file_service(self):
        """TASK-DOC-005M added a second locking read, and it is still confined.

        `detach` has to hold the file row as well as the document row, and it
        must hold them in that order. `transaction.py` is scoped to documents —
        its `locked_document()` takes a `Document` and has nothing to offer a
        `File` — so the file lock could not go there without widening a module
        this task was told to leave alone. It is allowed in `file_service.py`
        and nowhere else, which is what this pair of assertions pins down: the
        exception is one named place, not a licence to lock anywhere.
        """
        assert "with_for_update" in self.names_in(file_service), (
            "the file row must be locked in the same statement that reads it"
        )
        for module in (document_service, verification_history):
            assert "with_for_update" not in self.names_in(module), module.__name__

    def test_no_module_issues_a_second_document_locking_read(self):
        """The file lock must not be the document read smuggled elsewhere.

        `file_service` reaches the document through `transaction.locked_document`
        rather than issuing a locking select of its own, so the document lock
        keeps exactly one implementation even now that a second locking read
        exists.
        """
        source = inspect.getsource(file_service)
        assert "locked_document" in source
        assert not self.locks_a_document(file_service)
        assert "select(Document)" not in source

    def test_document_service_issues_no_lock_sql_itself(self):
        names = self.names_in(document_service)
        for forbidden in ("with_for_update", "populate_existing", "modified"):
            assert forbidden not in names, forbidden

    def test_populate_existing_is_set_where_the_lock_is(self):
        assert "populate_existing" in self.names_in(transaction)

    def test_all_three_mutating_methods_go_through_the_shared_entry(self):
        for name in ("update", "verify", "reject"):
            body = inspect.getsource(getattr(DocumentService, name))
            assert "DocumentService._locked_document(db, document_id)" in body, name

    def test_the_shared_module_does_not_reach_back_into_services(self):
        source = inspect.getsource(transaction)
        for forbidden in ("document_service", "file_service", "verification_history"):
            assert f"import {forbidden}" not in source
            assert f"from app.services.{forbidden}" not in source

    def test_release_is_delegated_not_reimplemented(self):
        assert "transaction.release" in inspect.getsource(DocumentService._release)
        assert "db.rollback" not in inspect.getsource(DocumentService._release)


class TestNoImportCycle:
    def test_the_module_imports_standalone_in_a_fresh_interpreter(self):
        # importing it first, with nothing else loaded, is what a future
        # FileService will do
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                textwrap.dedent(
                    """
                    import app.services.transaction as t
                    assert hasattr(t, "locked_document")
                    assert hasattr(t, "release")
                    assert hasattr(t, "transaction_existed_on_entry")
                    assert hasattr(t, "UncommittedChangesInSession")
                    print("ok")
                    """
                ),
            ],
            capture_output=True,
            text=True,
            cwd="/mnt/d/Antigravity/EquipmentDocumentationRegistry",
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "ok"

    @pytest.mark.parametrize(
        "module",
        [
            "app.services.transaction",
            "app.services.document_service",
            "app.services.verification_history",
            "app.services.file_service",
        ],
    )
    def test_each_module_imports_on_its_own(self, module):
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}; print('ok')"],
            capture_output=True,
            text=True,
            cwd="/mnt/d/Antigravity/EquipmentDocumentationRegistry",
        )
        assert result.returncode == 0, result.stderr
