"""Linking one document to several product variants.

A certificate routinely covers a whole run of sizes — ПЭ100 SDR11 Ø32, Ø63 and
Ø110 — so the relation between a document and a `ProductVariant` is many to many
and is already modelled by `document_variants`. This module is the service layer
over that one table: read the set of variants a document covers, and replace it
wholesale. It creates no rows in `document_products` or `document_batches`, and
it never touches a document's verdict, its history or its files.

**Transaction ownership follows `FileService`, not `DocumentService`.** The two
policies in this project differ on purpose. `DocumentService` adopts a
transaction it can prove it opened and otherwise leaves the caller's alone;
`FileService` refuses to run inside a caller's transaction at all. A replacement
of the link set is a finished unit of work that commits once, so the second
policy fits: a session that already has a transaction is refused *before any
statement runs*, which both stops this method's `commit` from deciding the fate
of the caller's staged changes and leaves those changes exactly as they were.

**The document row is locked first, and the whole replacement is one
transaction.** Two concurrent replacements of the same document therefore line
up: the second waits for the first to commit and then computes its difference
against what the first wrote, so the document ends up holding one requested set
rather than a mixture of two. Removing the old links and adding the new ones
happens between the lock and the single `commit`, with no intermediate commit,
so an empty set and a full set are equally atomic.
"""

from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_links import DocumentVariant
from app.models.variant import ProductVariant
from app.services import transaction


class DocumentVariantServiceError(Exception):
    """Base error for DocumentVariantService operations."""


class DocumentNotFoundError(DocumentVariantServiceError):
    """The document whose links are being read or replaced does not exist.

    Deliberately distinct from `FileService.DocumentNotFoundError`: the two live
    in different modules and describe different operations, so a router that
    imports one never accidentally imports the other's meaning.

    The identifier is kept on the instance so a caller can report it without
    parsing the message.
    """

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(f"Document {document_id} does not exist")


class ProductVariantsNotFoundError(DocumentVariantServiceError):
    """At least one requested product variant does not exist.

    Every missing identifier is carried on the instance, not just the first one
    found: a client that sent three bad ids should be told about all three in one
    answer rather than discover them one round trip at a time. The set of missing
    ids is sorted so the message is stable regardless of the order they arrived
    in.
    """

    def __init__(self, variant_ids: Iterable[int]) -> None:
        self.variant_ids = sorted(set(variant_ids))
        super().__init__(
            f"Product variants {self.variant_ids} do not exist"
        )


class DuplicateVariantIdsError(DocumentVariantServiceError):
    """The requested set names the same variant more than once.

    A replacement set is a set, so a repeat is a defect in the request rather
    than something to silently collapse: accepting `[1, 1, 2]` would make the
    caller's intent ambiguous and hide a bug on its side. The duplicated ids are
    carried on the instance, sorted for a stable message.
    """

    def __init__(self, variant_ids: Iterable[int]) -> None:
        self.variant_ids = sorted(set(variant_ids))
        super().__init__(
            f"duplicate product variant ids in request: {self.variant_ids}"
        )


class TransactionAlreadyOpenError(DocumentVariantServiceError):
    """The caller's session already had a transaction when the call was made.

    A finished replacement owns its transaction, so this is refused rather than
    joined. Adopting the caller's transaction would let this method's `commit`
    decide the fate of changes the caller staged for its own reasons; refusing is
    also the only answer that leaves that work alone.

    Raised before any statement runs, so the session is left exactly as it was
    found — no rollback, no commit, no mutation.
    """


class UncommittedDocumentChangesError(DocumentVariantServiceError):
    """The session holds uncommitted edits to the document about to be locked.

    Taking the row lock refreshes the document from the database, and a refresh
    discards local edits rather than merging them. Losing them silently would be
    worse than refusing the call, so the shared locking read refuses first and
    this is what the caller is told. Nothing has been written when it is raised,
    and no rollback is issued — rolling back would discard the very edits this
    error exists to protect.
    """

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(
            f"Document {document_id} has uncommitted changes in this session; "
            "commit or discard them before replacing its variant links"
        )


def _duplicates(variant_ids: Iterable[int]) -> set[int]:
    """Return the identifiers that appear more than once."""
    seen: set[int] = set()
    repeated: set[int] = set()
    for variant_id in variant_ids:
        if variant_id in seen:
            repeated.add(variant_id)
        else:
            seen.add(variant_id)
    return repeated


class DocumentVariantService:
    """Read and replace the product variants a document covers.

    Static methods taking the caller's session, matching `DocumentService`: the
    caller owns the connection (see `app.database.connection.get_db`), and this
    service never opens or closes one of its own. Read paths commit nothing and
    roll back nothing; the one write path commits exactly once.
    """

    @staticmethod
    def list_variants(db: Session, document_id: int) -> list[ProductVariant]:
        """Return the variants the document covers, ordered by ascending id.

        An existing document with no links returns `[]`; only a missing document
        is an error. Telling the two apart at this layer is what lets the HTTP
        layer answer `404` for a document that is not there and `200 []` for one
        that simply covers nothing — a distinction the caller cannot make from an
        empty list alone.

        Read-only: no commit, no rollback, no lock. The join uses the composite
        primary key `(document_id, variant_id)`, so the lookup is a single
        indexed read.
        """
        if db.get(Document, document_id) is None:
            raise DocumentNotFoundError(document_id)

        statement = (
            select(ProductVariant)
            .join(DocumentVariant, DocumentVariant.variant_id == ProductVariant.id)
            .where(DocumentVariant.document_id == document_id)
            .order_by(ProductVariant.id)
        )
        return list(db.scalars(statement))

    @staticmethod
    def set_variants(
        db: Session, document_id: int, variant_ids: Iterable[int]
    ) -> list[ProductVariant]:
        """Replace the document's variant links with exactly `variant_ids`.

        The requested identifiers are `ProductVariant` primary keys, not
        diameters. The operation is a full replacement: after it returns, the
        document covers exactly the requested variants and no others — links
        absent from the request are removed, missing ones are added, and a
        variant present in both the old and the new set is left untouched, so a
        repeated identical request writes nothing.

        Order of work, all before the single `commit`:

        1. Duplicate identifiers are refused as a defect in the request, before
           the session is touched at all.
        2. A caller's transaction is refused before any SQL runs.
        3. The document row is locked (`transaction.locked_document`), which is
           what serialises concurrent replacements of the same document.
        4. A missing document is `DocumentNotFoundError`.
        5. If any requested variant does not exist, the whole operation is
           refused and **not one** link is changed — the existence check runs
           before the first delete or insert.
        6. Only the difference between the old and new sets is written.

        The returned list is the final set ordered by ascending id, read back
        from the database so a caller sees what was committed rather than what it
        asked for.

        `verification_status` and the verification history are deliberately not
        involved. Linking a certificate to a size describes what it covers, not
        what it says, so it is not a significant field and must not withdraw a
        verdict — see ADR-008. Files, products and batches are untouched.
        """
        duplicates = _duplicates(variant_ids)
        if duplicates:
            raise DuplicateVariantIdsError(duplicates)

        if transaction.transaction_existed_on_entry(db):
            raise TransactionAlreadyOpenError(
                "the session already has a transaction; replacing variant links "
                "must own its own, so commit or roll back first"
            )

        requested = set(variant_ids)

        try:
            document = transaction.locked_document(db, document_id)
        except transaction.UncommittedChangesInSession as signal:
            # No rollback on purpose: the guard fires before anything is
            # written, and rolling back would discard the edits it protects.
            raise UncommittedDocumentChangesError(signal.document_id) from signal

        if document is None:
            db.rollback()
            raise DocumentNotFoundError(document_id)

        try:
            if requested:
                found = set(
                    db.scalars(
                        select(ProductVariant.id).where(
                            ProductVariant.id.in_(requested)
                        )
                    )
                )
                missing = requested - found
                if missing:
                    # Raised inside the try so the handler below frees the row
                    # lock; no link has been written yet.
                    raise ProductVariantsNotFoundError(missing)

            current = set(
                db.scalars(
                    select(DocumentVariant.variant_id).where(
                        DocumentVariant.document_id == document_id
                    )
                )
            )

            to_remove = current - requested
            to_add = requested - current

            if not to_remove and not to_add:
                # Idempotent repeat: report the set that is already there and end
                # the transaction without writing anything.
                return DocumentVariantService._final_set(db, requested)

            if to_remove:
                db.execute(
                    delete(DocumentVariant).where(
                        DocumentVariant.document_id == document_id,
                        DocumentVariant.variant_id.in_(to_remove),
                    )
                )
            for variant_id in to_add:
                db.add(
                    DocumentVariant(document_id=document_id, variant_id=variant_id)
                )

            db.commit()
        except Exception:
            db.rollback()
            raise

        return DocumentVariantService._final_set(db, requested)

    @staticmethod
    def _variants(db: Session, variant_ids: set[int]) -> list[ProductVariant]:
        """Return the named variants ordered by ascending id, `[]` for none."""
        if not variant_ids:
            return []
        statement = (
            select(ProductVariant)
            .where(ProductVariant.id.in_(variant_ids))
            .order_by(ProductVariant.id)
        )
        return list(db.scalars(statement))

    @staticmethod
    def _final_set(db: Session, variant_ids: set[int]) -> list[ProductVariant]:
        """Return the committed set, detached, leaving no open transaction.

        The rows are read back so the caller sees what was committed, then
        detached from the session and the read transaction is ended. Ending it
        matters: a finished replacement must hand the session back exactly as it
        found it, otherwise a second replacement in the same session would be
        refused by this service's own ownership rule. Detaching keeps the
        returned objects usable after the session lets go of them.
        """
        variants = DocumentVariantService._variants(db, variant_ids)
        for variant in variants:
            db.expunge(variant)
        db.rollback()
        return variants
