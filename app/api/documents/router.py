from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from pydantic import StringConstraints
from sqlalchemy.orm import Session

from app.api.documents.schemas import (
    DocumentCreate,
    DocumentListOut,
    DocumentOut,
    DocumentUpdate,
    DocumentVerificationEventListOut,
    DocumentVerificationRequest,
)
from app.database.connection import get_db
from app.services.document_service import (
    DEFAULT_LIMIT,
    DocumentHasNoFilesError,
    DocumentService,
    DocumentTypeNotFoundError,
    InvalidValidityPeriodError,
    IssuerNotFoundError,
    RejectionReasonRequiredError,
    UncommittedDocumentChangesError,
)

# The router carries a prefix because every path below the collection is
# addressed by the document's own id, exactly like `issuers` and
# `document-types`. The attachment routes live in `app/api/files` and hang off
# the same `/documents/{document_id}` segment; the two routers declare disjoint
# tails (`""`, `/{document_id}` here; `/files`, `/files/{file_id}`, ... there),
# so they never compete for a request.
document_router = APIRouter(prefix="/documents", tags=["documents"])

MIN_LIMIT = 1
MAX_LIMIT = 100
MIN_OFFSET = 0

# Search terms are non-empty after trimming. `min_length` is applied *after*
# `strip_whitespace`, so `""` and `"   "` are both `422`: a blank filter is a
# mistake to report, never a silent "no filter". A term that merely has
# surrounding spaces is trimmed and used.
MAX_SEARCH_TEXT_LENGTH = 255

SearchText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_SEARCH_TEXT_LENGTH,
    ),
]

DocumentStatus = Literal["pending", "verified", "rejected"]


@document_router.post(
    "",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a document",
)
def create_document(
    data: DocumentCreate,
    response: Response,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentOut:
    """Create a document and return the stored representation.

    `DocumentService.create` owns the whole operation: it checks the referenced
    document type and issuer, inserts the row and commits exactly once. The
    router performs no SQL beforehand, so the service opens the transaction it
    then ends. `verification_status` is not taken from the payload — a document
    is always born `pending` — and no verification event is written, because
    nothing has been decided yet.

    A referenced document type or issuer that does not exist is `422`, not
    `404`: the missing resource is named in the request body rather than in the
    request target, and the target itself resolved. The two domain errors the
    service documents are translated here; any other failure propagates and
    becomes the framework's generic `500`, whose body carries no SQL, connection
    string or exception detail.

    No document type, issuer or other reference is created on the side: a
    document only points at rows that already exist.
    """
    try:
        document = DocumentService.create(db, data)
    except DocumentTypeNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Document type {error.document_type_id} not found",
        ) from error
    except IssuerNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Issuer {error.issuer_id} not found",
        ) from error

    response.headers["Location"] = str(
        request.url_for("get_document", document_id=document.id)
    )
    return DocumentOut.model_validate(document)


@document_router.get(
    "",
    response_model=DocumentListOut,
    summary="List documents",
)
def list_documents(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=MIN_LIMIT, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=MIN_OFFSET)] = MIN_OFFSET,
    material: Annotated[
        SearchText | None,
        Query(description="Case-insensitive substring of the covered product name"),
    ] = None,
    size_text: Annotated[
        SearchText | None,
        Query(description="Exact size text of a covered product variant"),
    ] = None,
    variant_id: Annotated[
        int | None,
        Query(gt=0, description="Exact covered product variant id"),
    ] = None,
    manufacturer_id: Annotated[
        int | None,
        Query(gt=0, description="Exact manufacturer id of a covered product"),
    ] = None,
    standard: Annotated[
        SearchText | None,
        Query(
            description="Case-insensitive substring of the covered product standard"
        ),
    ] = None,
    number: Annotated[
        SearchText | None,
        Query(description="Case-insensitive substring of the document number"),
    ] = None,
    status: Annotated[
        DocumentStatus | None,
        Query(description="Verification status of the document"),
    ] = None,
) -> DocumentListOut:
    """Return a page of documents as a bare JSON array, ordered by id.

    Without query parameters this is the plain collection. With them it is a
    search: every supplied filter has to hold, so the parameters combine with
    `AND`. The page is produced by `DocumentService.list`, which owns both the
    ordering (`id` ascending) and the SQL — the router builds no query of its own
    and filters nothing in Python. Paging is applied after filtering, so `limit`
    counts matching documents. The response carries no total, so paging stays the
    caller's concern.

    The `material`, `standard`, `size_text`, `variant_id` and `manufacturer_id`
    filters all describe product variants the document covers, and the service
    requires **one** variant to match all of them at once — a document is not
    returned because two different covered variants match two different filters.
    An id that names no row is not an error: it simply matches nothing, so the
    result is `200 []`, never `404`. That keeps "no such variant" and "no
    document covers it" the same answer, which is what a search should say.

    `number` and `status` describe the document itself. Text filters are
    case-insensitive substrings; `size_text` is an exact match (so `Ø63` is not
    `Ø 63`); `status` is one of `pending`, `verified`, `rejected`.

    Out-of-range paging, a non-positive id, an unknown `status`, or a text filter
    that is empty or only whitespace is refused as `422` by the query validation.
    No attachments, links or verification history are embedded, and nothing about
    any document is changed by reading it.
    """
    documents = DocumentService.list(
        db,
        limit=limit,
        offset=offset,
        material=material,
        size_text=size_text,
        variant_id=variant_id,
        manufacturer_id=manufacturer_id,
        standard=standard,
        number=number,
        status=status,
    )
    return DocumentListOut.model_validate(documents)


@document_router.get(
    "/{document_id}",
    response_model=DocumentOut,
    summary="Get a document by id",
)
def get_document(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentOut:
    """Return a single document or `404` when it does not exist.

    The card is the document row alone: no file content, no `storage_key`, no
    linked products, variants or batches and no verification history. Files are
    served by the File HTTP API; the links and the history have no routes yet.

    Declared after the collection route so `""` resolves on its own path segment
    and is not captured by the parameterised one.
    """
    document = DocumentService.get(db, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return DocumentOut.model_validate(document)


@document_router.patch(
    "/{document_id}",
    response_model=DocumentOut,
    summary="Update a document",
)
def update_document(
    document_id: int,
    data: DocumentUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentOut:
    """Apply a partial update and return the stored document, or `404`.

    `DocumentService.update` owns the whole operation: it locks the row, merges
    the payload with the stored values, applies the change and commits exactly
    once. The router performs no SQL beforehand — a preliminary read would open
    a transaction the service would then treat as the caller's, defeating its
    own release of the row lock on the paths that change nothing. `None` means
    the document does not exist and is answered `404`, which is why existence is
    never asked about separately. Nothing is committed, rolled back or locked
    here, no second session is opened, and no verification event is written from
    this layer.

    An empty body `{}` is valid and changes nothing: the service skips the
    commit entirely, so the document and its history are untouched. A payload
    that only repeats the stored values is the same no-op, because the service
    compares the requested fields against the row rather than against the
    request. `verification_status` is not part of `DocumentUpdate`, so it cannot
    be moved through this route.

    The lifecycle rules stay in the service and the ADRs: when a significant
    requisite really changes on a `verified` or `rejected` document, `update`
    resets the status to `pending` and records exactly one `reopened` event with
    the reason `significant_fields_changed`. A change to `notes` alone keeps the
    verdict. Those rules are not restated or replicated here.

    Domain errors are translated, each to the status this API assigns it:

    - `DocumentTypeNotFoundError`, `IssuerNotFoundError` → `422`, because the
      missing reference is named in the body rather than the request target;
    - `InvalidValidityPeriodError` → `422`, for a window that is inverted only
      once the patch is merged with the stored value;
    - `UncommittedDocumentChangesError` → `409`, for a session that still holds
      edits to the document. Over HTTP the request session is fresh and no SQL
      runs before the service, so this is not expected here; it is translated
      defensively rather than left to become a generic `500`.

    Anything else propagates untouched and becomes the framework's generic
    `500`, whose body carries no SQL, traceback or storage path.
    """
    try:
        document = DocumentService.update(db, document_id, data)
    except DocumentTypeNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Document type {error.document_type_id} not found",
        ) from error
    except IssuerNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Issuer {error.issuer_id} not found",
        ) from error
    except InvalidValidityPeriodError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except UncommittedDocumentChangesError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The document has uncommitted changes",
        ) from error

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return DocumentOut.model_validate(document)


@document_router.get(
    "/{document_id}/verification-history",
    response_model=DocumentVerificationEventListOut,
    summary="List a document's verification history",
)
def list_verification_history(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentVerificationEventListOut:
    """Return every recorded verification event of a document, oldest first.

    The history is read-only and additive: `DocumentVerificationEvent` rows are
    written by `DocumentService.verify`, `reject` and `update` (through
    `verification_history.record_reopened`), never here. This route only asks
    `DocumentService.history` for the rows and serialises them; it runs no SQL of
    its own, touches no document, calls no `commit`, `rollback` or
    `SELECT ... FOR UPDATE`, and opens no session of its own.

    `None` from the service means the document does not exist and is answered
    `404`, worded like the other document routes. A document that exists but has
    no events is not an error: it yields `200` and an empty array, because a
    freshly created document has a status without a history behind it.

    The result is a bare JSON array ordered `created_at ASC, id ASC`, with no
    paging, no `total` and no filters — the history of one document is short, and
    the order is the order events happened in. Nothing internal is exposed: the
    event rows carry no storage keys, paths or foreign objects.
    """
    events = DocumentService.history(db, document_id)
    if events is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return DocumentVerificationEventListOut.model_validate(events)


@document_router.post(
    "/{document_id}/verification",
    response_model=DocumentOut,
    summary="Verify or reject a document",
)
def verify_document(
    document_id: int,
    body: DocumentVerificationRequest,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentOut:
    """Record a verdict on a document and return the stored representation.

    The route is a dispatcher, not a decision maker. `decision="verified"` calls
    `DocumentService.verify`, anything else calls `DocumentService.reject`, and
    each owns the entire operation: it locks the document row, checks the rules,
    writes the single history event and commits exactly once. The router runs no
    SQL — the attachment count that guards a confirmation and the non-blank
    reason that guards a rejection are both checked inside the service, not
    here — and it neither opens a second session nor calls `commit`, `rollback`
    or `SELECT ... FOR UPDATE`. No event is written from this layer.

    Idempotency is the service's too: confirming an already `verified` document
    or rejecting an already `rejected` one returns the document unchanged and
    writes no second event, so a repeated request is still `200`. `rejected`
    and `verified` may be reached from each other directly; ADR-008 allows both.

    `reason` carries no meaning invented here. For a rejection it is the
    auditor-facing explanation and is required by the request validator; for a
    confirmation it is optional and passed through as given, which is exactly
    what `DocumentService.verify(..., reason=...)` accepts. If omitted it stays
    `None`.

    Domain errors are translated, each to the status this API assigns it:

    - `DocumentHasNoFilesError` → `422`, because a verdict needs the scan it
      refers to and there is none;
    - `RejectionReasonRequiredError` → `422`; in practice the request validator
      refuses a blank reason first, so this is the defensive mapping;
    - `UncommittedDocumentChangesError` → `409`, for a session that still holds
      edits to the document. Over HTTP the request session is fresh and no SQL
      runs before the service, so this is not expected here.

    `None` means the document does not exist and is answered `404`. Anything
    else propagates untouched and becomes the framework's generic `500`, whose
    body carries no SQL, traceback or storage path.
    """
    try:
        if body.decision == "verified":
            document = DocumentService.verify(db, document_id, reason=body.reason)
        else:
            # The validator guarantees a non-blank reason on this branch.
            document = DocumentService.reject(
                db, document_id, reason=body.reason  # type: ignore[arg-type]
            )
    except DocumentHasNoFilesError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The document has no attached files and cannot be verified",
        ) from error
    except RejectionReasonRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A rejection requires a reason",
        ) from error
    except UncommittedDocumentChangesError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The document has uncommitted changes",
        ) from error

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return DocumentOut.model_validate(document)
