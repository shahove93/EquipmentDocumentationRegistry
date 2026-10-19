"""HTTP routes for the sizes a document is linked to.

Two operations on one path, both addressed through the document:

* `GET  /documents/{document_id}/variants` — read the linked sizes;
* `PUT  /documents/{document_id}/variants` — replace them wholesale.

The router is deliberately thin. It opens no transaction of its own, runs no SQL
of its own, and never calls `commit`, `rollback` or `FOR UPDATE`: every check and
every write belongs to `DocumentVariantService`, which owns the transaction and
takes the document lock. That is not stylistic — `set_variants` refuses a session
that already has a transaction, so a stray `SELECT` here (or a dependency that
opened one) would turn every replacement into a `409`.

The two routes carry the same `/documents/{document_id}` prefix as the document
and file routers. The tails are disjoint (`variants` against `""`, `files`,
`verification`, `verification-history`), so a path can only ever match one
handler; there is no route that swallows another.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.document_variants.schemas import DocumentVariantLinkRequest
from app.api.variants.schemas import ProductVariantRead
from app.database.connection import get_db
from app.services.document_variant_service import (
    DocumentNotFoundError,
    DocumentVariantService,
    DuplicateVariantIdsError,
    ProductVariantsNotFoundError,
    TransactionAlreadyOpenError,
    UncommittedDocumentChangesError,
)

document_variant_router = APIRouter(prefix="/documents", tags=["documents"])


@document_variant_router.get(
    "/{document_id}/variants",
    response_model=list[ProductVariantRead],
    summary="List the sizes a document is linked to",
    name="list_document_variants",
)
def list_document_variants(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> list[ProductVariantRead]:
    """Return the sizes linked to the document, ordered by ascending id.

    A document that exists but covers nothing returns `[]`; only a document that
    does not exist is `404`. The two are kept apart because a certificate with no
    sizes yet and a mistyped id mean very different things to a client, and an
    empty array alone cannot tell them apart.

    Read-only: the service runs a single `SELECT` and leaves the transaction it
    opened for the request to close.
    """
    try:
        variants = DocumentVariantService.list_variants(db, document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {error.document_id} not found",
        ) from error
    return [ProductVariantRead.model_validate(variant) for variant in variants]


@document_variant_router.put(
    "/{document_id}/variants",
    response_model=list[ProductVariantRead],
    summary="Replace the sizes a document is linked to",
    name="replace_document_variants",
)
def replace_document_variants(
    document_id: int,
    data: DocumentVariantLinkRequest,
    db: Annotated[Session, Depends(get_db)],
) -> list[ProductVariantRead]:
    """Replace the document's linked sizes with exactly `variant_ids`.

    The body is a full replacement, not a patch: the listed variants are linked,
    everything else is unlinked, and `[]` unlinks all of them. Repeating the same
    list is accepted and writes nothing, so the call is safe to retry. Order in
    the request is irrelevant; the response is ordered by ascending id.

    The identifiers are `ProductVariant` primary keys, **not** diameters. An id
    that names no variant is `422`, and because the service checks every id
    before it deletes or inserts anything, such a request changes nothing.

    Errors carry no SQL, path or traceback — only the identifiers the client sent
    and the outcome, matching the rest of the API. `409` is reserved for the two
    session-state refusals the service can raise, neither of which a normal HTTP
    request should ever meet; the per-request session in `get_db` starts clean.
    """
    try:
        variants = DocumentVariantService.set_variants(
            db, document_id, data.variant_ids
        )
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {error.document_id} not found",
        ) from error
    except ProductVariantsNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Product variants {error.variant_ids} not found",
        ) from error
    except DuplicateVariantIdsError as error:
        # The request schema already refuses duplicates, so this is a backstop:
        # if the schema ever relaxes, the domain rule still holds.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"duplicate variant ids: {error.variant_ids}",
        ) from error
    except TransactionAlreadyOpenError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The session already has a transaction",
        ) from error
    except UncommittedDocumentChangesError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document {error.document_id} has uncommitted changes",
        ) from error
    return [ProductVariantRead.model_validate(variant) for variant in variants]
