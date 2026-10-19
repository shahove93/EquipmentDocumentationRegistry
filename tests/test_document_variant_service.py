"""Service-level checks for `DocumentVariantService`.

The table `document_variants` already carries the many-to-many relation between
documents and sizes; this module pins the service contract over it. The two
things worth proving here beyond the obvious happy path:

* a replacement is **all or nothing** — a missing variant must leave the old set
  exactly as it was, and a repeat of the same set must write nothing at all;
* linking is **not** a verdict change — no status moves and no history row is
  added, whatever state the document is in.

Fixtures build documents and variants in short-lived sessions of their own, so
the session handed to the service starts without a transaction. `set_variants`
refuses a caller's transaction by design, and a fixture that merely flushed would
trip that rule before the test began.
"""

import ast
import inspect
import itertools

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_links import DocumentVariant
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.document_type import DocumentType
from app.models.manufacturer import Manufacturer
from app.models.product import Product
from app.models.variant import ProductVariant
from app.services.document_variant_service import (
    DocumentNotFoundError,
    DocumentVariantService,
    DocumentVariantServiceError,
    DuplicateVariantIdsError,
    ProductVariantsNotFoundError,
    TransactionAlreadyOpenError,
    UncommittedDocumentChangesError,
)

PENDING = "pending"
VERIFIED = "verified"
REJECTED = "rejected"


# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #


def _creator(engine) -> Session:
    """A session that keeps its objects usable after commit.

    `expire_on_commit=False` is what lets a returned `.id` be read without
    issuing a query — and therefore without opening a transaction on the session
    the test itself will use.
    """
    return Session(engine, future=True, expire_on_commit=False)


@pytest.fixture
def make_document(engine):
    """Create a committed document and return its id."""
    counter = itertools.count(1)

    def _make(status: str = PENDING) -> int:
        n = next(counter)
        session = _creator(engine)
        try:
            document = Document(
                document_type=DocumentType(name=f"Тип {n}"),
                number=f"D-{n}",
                verification_status=status,
            )
            session.add(document)
            session.commit()
            return document.id
        finally:
            session.close()

    return _make


@pytest.fixture
def make_variants(engine):
    """Create one product with the given sizes, return variant ids in order.

    Each call makes its own product, so two calls give variants of two different
    products — which is what the "different products" test needs.
    """
    counter = itertools.count(1)

    def _make(sizes: list[str]) -> list[int]:
        n = next(counter)
        session = _creator(engine)
        try:
            product = Product(
                name=f"Труба ПЭ100 SDR11 #{n}",
                standard="ГОСТ 58121.2-2018",
                manufacturer=Manufacturer(name=f"Завод #{n}"),
            )
            variants = [
                ProductVariant(product=product, size_text=size) for size in sizes
            ]
            session.add_all(variants)
            session.commit()
            return [variant.id for variant in variants]
        finally:
            session.close()

    return _make


def linked_ids(db: Session, document_id: int) -> list[int]:
    """The variant ids currently linked to a document, ascending."""
    return list(
        db.scalars(
            select(DocumentVariant.variant_id)
            .where(DocumentVariant.document_id == document_id)
            .order_by(DocumentVariant.variant_id)
        )
    )


def status_of(db: Session, document_id: int) -> str:
    return db.get(Document, document_id).verification_status


def event_count(db: Session, document_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(DocumentVerificationEvent)
        .where(DocumentVerificationEvent.document_id == document_id)
    )


def capture_statements(engine):
    """Collect every statement sent to the database, and a stop function."""
    statements: list[str] = []

    def before(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa_event.listen(engine, "before_cursor_execute", before)
    return statements, lambda: sa_event.remove(engine, "before_cursor_execute", before)


def link_writes(statements: list[str]) -> list[str]:
    """The subset of statements that would change the link table."""
    return [
        statement
        for statement in statements
        if "document_variants" in statement
        and statement.lstrip().upper().startswith(("INSERT", "DELETE", "UPDATE"))
    ]


def assert_document_is_unlocked(engine, document_id: int) -> None:
    """Fail if the row lock on the document is still held elsewhere.

    A fresh session takes the lock with a short `statement_timeout`; if another
    session still holds it, the wait times out and the test fails rather than
    hanging.
    """
    other = Session(engine, future=True)
    try:
        other.execute(text("SET statement_timeout = '2s'"))
        other.execute(
            select(Document).where(Document.id == document_id).with_for_update()
        )
        other.rollback()
    finally:
        other.close()


# --------------------------------------------------------------------------- #
# 1-6, 10-13: basic linking and reading
# --------------------------------------------------------------------------- #


class TestLinkingAndReading:
    def test_links_one_variant(self, db, make_document, make_variants):
        document_id = make_document()
        (variant_id,) = make_variants(["Ø63"])

        result = DocumentVariantService.set_variants(db, document_id, [variant_id])

        assert [variant.id for variant in result] == [variant_id]
        assert linked_ids(db, document_id) == [variant_id]

    def test_links_three_variants_of_one_product(self, db, make_document, make_variants):
        document_id = make_document()
        variant_ids = make_variants(["Ø32", "Ø63", "Ø110"])

        result = DocumentVariantService.set_variants(db, document_id, variant_ids)

        assert [variant.id for variant in result] == sorted(variant_ids)
        assert linked_ids(db, document_id) == sorted(variant_ids)

    def test_links_variants_of_different_products(
        self, db, make_document, make_variants
    ):
        document_id = make_document()
        first = make_variants(["Ø63"])
        second = make_variants(["Ø110"])

        result = DocumentVariantService.set_variants(
            db, document_id, [first[0], second[0]]
        )

        assert [variant.id for variant in result] == sorted([first[0], second[0]])
        assert linked_ids(db, document_id) == sorted([first[0], second[0]])

    def test_reads_an_empty_set(self, db, make_document):
        document_id = make_document()

        assert DocumentVariantService.list_variants(db, document_id) == []

    def test_reads_an_existing_set(self, db, make_document, make_variants):
        document_id = make_document()
        variant_ids = make_variants(["Ø32", "Ø63"])
        DocumentVariantService.set_variants(db, document_id, variant_ids)

        result = DocumentVariantService.list_variants(db, document_id)

        assert [variant.id for variant in result] == sorted(variant_ids)

    def test_reads_are_sorted_by_id(self, db, make_document, make_variants):
        document_id = make_document()
        variant_ids = make_variants(["Ø110", "Ø32", "Ø63"])
        # request them out of order on purpose
        DocumentVariantService.set_variants(
            db, document_id, [variant_ids[2], variant_ids[0], variant_ids[1]]
        )

        result = DocumentVariantService.list_variants(db, document_id)

        assert [variant.id for variant in result] == sorted(variant_ids)

    def test_missing_document_on_read(self, db):
        with pytest.raises(DocumentNotFoundError):
            DocumentVariantService.list_variants(db, 999_999)

    def test_missing_document_on_write(self, db, make_variants):
        (variant_id,) = make_variants(["Ø63"])

        with pytest.raises(DocumentNotFoundError):
            DocumentVariantService.set_variants(db, 999_999, [variant_id])

    def test_missing_variant(self, db, make_document, make_variants):
        document_id = make_document()
        (variant_id,) = make_variants(["Ø63"])

        with pytest.raises(ProductVariantsNotFoundError) as info:
            DocumentVariantService.set_variants(db, document_id, [variant_id, 999_999])

        assert info.value.variant_ids == [999_999]
        assert linked_ids(db, document_id) == []

    def test_every_missing_variant_is_reported(self, db, make_document):
        document_id = make_document()

        with pytest.raises(ProductVariantsNotFoundError) as info:
            DocumentVariantService.set_variants(db, document_id, [111, 222, 333])

        assert info.value.variant_ids == [111, 222, 333]

    def test_mixed_list_changes_nothing(
        self, db, make_document, make_variants
    ):
        document_id = make_document()
        first = make_variants(["Ø32"])
        second = make_variants(["Ø63"])
        DocumentVariantService.set_variants(db, document_id, [first[0], second[0]])

        with pytest.raises(ProductVariantsNotFoundError):
            DocumentVariantService.set_variants(
                db, document_id, [first[0], 999_999]
            )

        # the old set is untouched: neither the good id was re-added nor anything
        # removed
        assert linked_ids(db, document_id) == sorted([first[0], second[0]])

    def test_duplicate_ids_are_refused(self, db, make_document, make_variants):
        document_id = make_document()
        (variant_id,) = make_variants(["Ø63"])

        with pytest.raises(DuplicateVariantIdsError) as info:
            DocumentVariantService.set_variants(
                db, document_id, [variant_id, variant_id]
            )

        assert info.value.variant_ids == [variant_id]
        assert linked_ids(db, document_id) == []

    def test_duplicates_are_checked_before_the_session_is_touched(
        self, db, make_document, make_variants
    ):
        document_id = make_document()
        (variant_id,) = make_variants(["Ø63"])
        # a transaction is open; a duplicate request must still be answered as a
        # request defect rather than as a transaction conflict
        db.execute(text("SELECT 1"))

        with pytest.raises(DuplicateVariantIdsError):
            DocumentVariantService.set_variants(
                db, document_id, [variant_id, variant_id]
            )

        db.rollback()


# --------------------------------------------------------------------------- #
# 7-9: replacement semantics
# --------------------------------------------------------------------------- #


class TestReplacement:
    def test_repeating_the_same_set_writes_nothing(
        self, engine, db, make_document, make_variants
    ):
        document_id = make_document()
        variant_ids = make_variants(["Ø32", "Ø63"])
        DocumentVariantService.set_variants(db, document_id, variant_ids)

        statements, stop = capture_statements(engine)
        try:
            result = DocumentVariantService.set_variants(db, document_id, variant_ids)
        finally:
            stop()

        assert [variant.id for variant in result] == sorted(variant_ids)
        assert link_writes(statements) == []
        assert linked_ids(db, document_id) == sorted(variant_ids)

    def test_replaces_ab_with_bc(self, db, make_document, make_variants):
        document_id = make_document()
        a, b, c = make_variants(["Ø32", "Ø63", "Ø110"])
        DocumentVariantService.set_variants(db, document_id, [a, b])

        result = DocumentVariantService.set_variants(db, document_id, [b, c])

        assert [variant.id for variant in result] == sorted([b, c])
        assert linked_ids(db, document_id) == sorted([b, c])

    def test_empty_list_clears_every_link(self, db, make_document, make_variants):
        document_id = make_document()
        variant_ids = make_variants(["Ø32", "Ø63", "Ø110"])
        DocumentVariantService.set_variants(db, document_id, variant_ids)

        result = DocumentVariantService.set_variants(db, document_id, [])

        assert result == []
        assert linked_ids(db, document_id) == []

    def test_empty_list_on_an_empty_document_writes_nothing(
        self, engine, db, make_document
    ):
        document_id = make_document()

        statements, stop = capture_statements(engine)
        try:
            result = DocumentVariantService.set_variants(db, document_id, [])
        finally:
            stop()

        assert result == []
        assert link_writes(statements) == []


# --------------------------------------------------------------------------- #
# 15-16: isolation between documents and variants
# --------------------------------------------------------------------------- #


class TestIsolation:
    def test_neighbouring_documents_keep_their_own_sets(
        self, db, make_document, make_variants
    ):
        first = make_document()
        second = make_document()
        a, b = make_variants(["Ø32", "Ø63"])
        DocumentVariantService.set_variants(db, first, [a])

        DocumentVariantService.set_variants(db, second, [b])

        assert linked_ids(db, first) == [a]
        assert linked_ids(db, second) == [b]

    def test_clearing_one_document_leaves_the_other(
        self, db, make_document, make_variants
    ):
        first = make_document()
        second = make_document()
        (variant_id,) = make_variants(["Ø63"])
        DocumentVariantService.set_variants(db, first, [variant_id])
        DocumentVariantService.set_variants(db, second, [variant_id])

        DocumentVariantService.set_variants(db, first, [])

        assert linked_ids(db, first) == []
        assert linked_ids(db, second) == [variant_id]

    def test_one_variant_can_belong_to_many_documents(
        self, db, make_document, make_variants
    ):
        (variant_id,) = make_variants(["Ø63"])
        first = make_document()
        second = make_document()

        DocumentVariantService.set_variants(db, first, [variant_id])
        DocumentVariantService.set_variants(db, second, [variant_id])

        assert linked_ids(db, first) == [variant_id]
        assert linked_ids(db, second) == [variant_id]


# --------------------------------------------------------------------------- #
# 17-21: the verdict, the history and the other link tables are not involved
# --------------------------------------------------------------------------- #


class TestVerificationIsUntouched:
    @pytest.mark.parametrize("status", [PENDING, VERIFIED, REJECTED])
    def test_status_is_preserved(
        self, db, make_document, make_variants, status
    ):
        document_id = make_document(status=status)
        (variant_id,) = make_variants(["Ø63"])

        DocumentVariantService.set_variants(db, document_id, [variant_id])

        assert status_of(db, document_id) == status

    @pytest.mark.parametrize("status", [PENDING, VERIFIED, REJECTED])
    def test_no_verification_event_is_written(
        self, db, make_document, make_variants, status
    ):
        document_id = make_document(status=status)
        variant_ids = make_variants(["Ø32", "Ø63"])

        DocumentVariantService.set_variants(db, document_id, variant_ids)
        DocumentVariantService.set_variants(db, document_id, [])

        assert event_count(db, document_id) == 0

    def test_replacement_does_not_add_a_history_row(
        self, db, make_document, make_variants
    ):
        document_id = make_document(status=VERIFIED)
        a, b = make_variants(["Ø32", "Ø63"])

        DocumentVariantService.set_variants(db, document_id, [a])
        DocumentVariantService.set_variants(db, document_id, [b])

        assert event_count(db, document_id) == 0

    def test_reopened_is_never_recorded(
        self, db, make_document, make_variants
    ):
        document_id = make_document(status=VERIFIED)
        (variant_id,) = make_variants(["Ø63"])

        DocumentVariantService.set_variants(db, document_id, [variant_id])

        events = list(
            db.scalars(
                select(DocumentVerificationEvent).where(
                    DocumentVerificationEvent.document_id == document_id
                )
            )
        )
        assert events == []

    def test_product_and_batch_links_are_not_touched(
        self, db, make_document, make_variants
    ):
        document_id = make_document()
        (variant_id,) = make_variants(["Ø63"])

        DocumentVariantService.set_variants(db, document_id, [variant_id])

        assert db.scalar(text("select count(*) from document_products")) == 0
        assert db.scalar(text("select count(*) from document_batches")) == 0


# --------------------------------------------------------------------------- #
# 22-23: transactions and locks
# --------------------------------------------------------------------------- #


class TestTransactionOwnership:
    def test_set_refuses_an_open_transaction(self, db, make_document, make_variants):
        document_id = make_document()
        (variant_id,) = make_variants(["Ø63"])
        db.execute(text("SELECT 1"))

        with pytest.raises(TransactionAlreadyOpenError):
            DocumentVariantService.set_variants(db, document_id, [variant_id])

        db.rollback()
        assert linked_ids(db, document_id) == []

    def test_the_refusal_leaves_the_caller_changes_alone(
        self, db, make_document, make_variants
    ):
        document_id = make_document()
        (variant_id,) = make_variants(["Ø63"])
        document = db.get(Document, document_id)
        document.notes = "staged by the caller"

        with pytest.raises(TransactionAlreadyOpenError):
            DocumentVariantService.set_variants(db, document_id, [variant_id])

        assert document.notes == "staged by the caller"
        assert db.is_modified(document)
        db.rollback()

    def test_the_document_is_unlocked_after_a_successful_replace(
        self, engine, db, make_document, make_variants
    ):
        document_id = make_document()
        variant_ids = make_variants(["Ø32", "Ø63"])
        DocumentVariantService.set_variants(db, document_id, variant_ids)

        assert_document_is_unlocked(engine, document_id)

    def test_the_document_is_unlocked_after_an_idempotent_repeat(
        self, engine, db, make_document, make_variants
    ):
        document_id = make_document()
        variant_ids = make_variants(["Ø32"])
        DocumentVariantService.set_variants(db, document_id, variant_ids)

        DocumentVariantService.set_variants(db, document_id, variant_ids)

        assert_document_is_unlocked(engine, document_id)

    def test_the_document_is_unlocked_after_a_missing_variant(
        self, engine, db, make_document, make_variants
    ):
        document_id = make_document()
        (variant_id,) = make_variants(["Ø63"])
        # a fresh session, so the failure path is what releases the lock
        with pytest.raises(ProductVariantsNotFoundError):
            DocumentVariantService.set_variants(db, document_id, [variant_id, 999_999])

        assert_document_is_unlocked(engine, document_id)

    def test_read_does_not_commit_or_roll_back(self, db, make_document, make_variants):
        document_id = make_document()
        (variant_id,) = make_variants(["Ø63"])
        DocumentVariantService.set_variants(db, document_id, [variant_id])

        # stage a change, then read: a read path that rolled back would discard it
        db.get(Document, document_id).notes = "staged"
        DocumentVariantService.list_variants(db, document_id)

        assert db.in_transaction() is True
        assert db.get(Document, document_id).notes == "staged"
        db.rollback()


class TestUncommittedDocumentEdits:
    def test_the_shared_signal_is_translated(self, db, make_document, monkeypatch):
        """The lock's pending-change guard becomes this service's own error.

        The guard is unreachable through normal use here — a caller's open
        transaction is refused first — so the shared signal is injected directly
        to pin the translation rather than a contrived session state.
        """
        from app.services import transaction as transaction_module

        document_id = make_document()

        def refuse(session, id_):
            raise transaction_module.UncommittedChangesInSession(id_)

        monkeypatch.setattr(transaction_module, "locked_document", refuse)

        with pytest.raises(UncommittedDocumentChangesError) as info:
            DocumentVariantService.set_variants(db, document_id, [])

        assert info.value.document_id == document_id


# --------------------------------------------------------------------------- #
# 25: the service is self-contained
# --------------------------------------------------------------------------- #


class TestTheServiceIsSelfContained:
    def test_it_does_not_import_document_or_file_service(self):
        from app.services import document_variant_service

        tree = ast.parse(inspect.getsource(document_variant_service))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)

        assert "app.services.document_service" not in imported
        assert "app.services.file_service" not in imported

    def test_it_does_not_import_the_verification_machinery(self):
        from app.services import document_variant_service

        tree = ast.parse(inspect.getsource(document_variant_service))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)

        assert "app.services.verification_history" not in imported
        assert "app.models.document_verification_event" not in imported

    def test_its_errors_all_share_one_base(self):
        for error in (
            DocumentNotFoundError,
            ProductVariantsNotFoundError,
            DuplicateVariantIdsError,
            TransactionAlreadyOpenError,
            UncommittedDocumentChangesError,
        ):
            assert issubclass(error, DocumentVariantServiceError)
