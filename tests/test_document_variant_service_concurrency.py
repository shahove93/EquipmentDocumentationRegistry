"""Concurrent replacement of a document's variant links against real PostgreSQL.

`set_variants` takes the document row lock before it reads the current set, so
two replacements of the same document cannot both decide what to delete and
insert from the same starting point. Everything here exists to show what that
buys: one writer waits for the other, and the document ends up holding exactly
one requested set rather than a mixture of two.

Real PostgreSQL, separate connections, bounded waits. A test that passed because
the two calls happened to run one after another would prove nothing about the
lock, so the window is forced open: a third session holds the row lock, both
writers pile up behind it, and only then is it released.
"""

import itertools
import threading
import time

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_links import DocumentVariant
from app.models.document_type import DocumentType
from app.models.manufacturer import Manufacturer
from app.models.product import Product
from app.models.variant import ProductVariant
from app.services.document_variant_service import DocumentVariantService

# Upper bound for a thread to reach its gate; it only ever bounds a failure.
TIMEOUT = 10.0

# How long to watch the writers and expect them to still be blocked.
BLOCKED_WINDOW = 0.5


def wait_until(predicate, timeout=TIMEOUT, interval=0.01):
    """Poll `predicate` until it is true, or fail after `timeout`."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _creator(engine) -> Session:
    return Session(engine, future=True, expire_on_commit=False)


@pytest.fixture
def make_document(engine):
    counter = itertools.count(1)

    def _make() -> int:
        n = next(counter)
        session = _creator(engine)
        try:
            document = Document(
                document_type=DocumentType(name=f"Тип {n}"), number=f"D-{n}"
            )
            session.add(document)
            session.commit()
            return document.id
        finally:
            session.close()

    return _make


@pytest.fixture
def make_variants(engine):
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


def current_links(engine, document_id: int) -> list[int]:
    session = Session(engine, future=True)
    try:
        return sorted(
            session.scalars(
                select(DocumentVariant.variant_id)
                .where(DocumentVariant.document_id == document_id)
                .order_by(DocumentVariant.variant_id)
            )
        )
    finally:
        session.close()


def run_replacements(engine, document_id, requests, holder):
    """Start one replacement per request, all blocked behind `holder`.

    Returns the outcome box and the joined threads. Each worker runs in its own
    session on its own connection; the gate makes them pass the starting line
    together, and the rows are locked by `holder` so they meet on the lock rather
    than on the CPU.
    """
    box: dict[str, object] = {}
    started: dict[str, bool] = {}
    gate = threading.Barrier(len(requests))

    def worker(key, variant_ids):
        session = Session(engine, future=True)
        try:
            gate.wait(timeout=TIMEOUT)
            started[key] = True
            result = DocumentVariantService.set_variants(
                session, document_id, variant_ids
            )
            box[key] = sorted(variant.id for variant in result)
        except BaseException as error:  # reported through the box, not swallowed
            box[key] = error
        finally:
            session.close()

    threads = [
        threading.Thread(target=worker, args=(key, ids))
        for key, ids in requests.items()
    ]
    for thread in threads:
        thread.start()

    assert wait_until(lambda: len(started) == len(requests))

    return box, threads


def release_and_join(box, threads):
    for thread in threads:
        thread.join(timeout=TIMEOUT)
        assert not thread.is_alive(), "a replacement never returned"
    for key, outcome in box.items():
        assert not isinstance(outcome, BaseException), (key, outcome)


class TestConcurrentReplacement:
    def test_one_complete_set_lands_not_a_mixture(
        self, engine, make_document, make_variants
    ):
        document_id = make_document()
        a, b, c = make_variants(["Ø32", "Ø63", "Ø110"])

        # A third session holds the document lock, so both writers have to wait
        # on it and the window between their read and their write is forced open.
        holder = Session(engine, future=True)
        try:
            holder.execute(
                select(Document)
                .where(Document.id == document_id)
                .with_for_update()
            )

            box, threads = run_replacements(
                engine,
                document_id,
                {"first": [a, b], "second": [b, c]},
                holder,
            )

            # While the lock is held, neither writer can have finished.
            time.sleep(BLOCKED_WINDOW)
            assert box == {}, f"a replacement ran without the lock: {box}"

            holder.rollback()
        finally:
            holder.close()

        release_and_join(box, threads)

        # Each writer reports the set it was asked for and committed.
        assert box["first"] == sorted([a, b])
        assert box["second"] == sorted([b, c])

        # The document holds exactly one of the two sets — never {a, b, c}, never
        # an empty or half-applied set.
        final = current_links(engine, document_id)
        assert final in (sorted([a, b]), sorted([b, c]))

    def test_identical_concurrent_replacements_do_not_conflict(
        self, engine, make_document, make_variants
    ):
        document_id = make_document()
        a, b = make_variants(["Ø32", "Ø63"])

        holder = Session(engine, future=True)
        try:
            holder.execute(
                select(Document)
                .where(Document.id == document_id)
                .with_for_update()
            )
            box, threads = run_replacements(
                engine, document_id, {"first": [a, b], "second": [a, b]}, holder
            )
            time.sleep(BLOCKED_WINDOW)
            assert box == {}
            holder.rollback()
        finally:
            holder.close()

        release_and_join(box, threads)

        # No duplicate-pair violation from the second writer: it sees the first
        # writer's committed set and finds nothing to change.
        assert box["first"] == sorted([a, b])
        assert box["second"] == sorted([a, b])
        assert current_links(engine, document_id) == sorted([a, b])

    def test_a_second_writer_sees_the_first_writers_result(
        self, engine, make_document, make_variants
    ):
        """The waiting writer is not deciding on a stale snapshot.

        The first writer replaces `[a]` with `[b]`. The second is held behind the
        lock, then released, and must compute its difference against `[b]` — so
        replacing `[a]` with `[c]` afterwards leaves `[c]` alone, not `[a, c]`
        resurrected.
        """
        document_id = make_document()
        a, b, c = make_variants(["Ø32", "Ø63", "Ø110"])

        # Start from `[a]`.
        setup = Session(engine, future=True)
        try:
            DocumentVariantService.set_variants(setup, document_id, [a])
        finally:
            setup.close()

        holder = Session(engine, future=True)
        try:
            holder.execute(
                select(Document)
                .where(Document.id == document_id)
                .with_for_update()
            )
            box, threads = run_replacements(
                engine,
                document_id,
                {"first": [b], "second": [c]},
                holder,
            )
            time.sleep(BLOCKED_WINDOW)
            assert box == {}
            holder.rollback()
        finally:
            holder.close()

        release_and_join(box, threads)

        final = current_links(engine, document_id)
        assert final in ([b], [c])
        # whatever the order, `a` is gone: the waiter did not resurrect the set
        # it read before the other writer committed
        assert a not in final
