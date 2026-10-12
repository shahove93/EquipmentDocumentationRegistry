from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.document_types.schemas import (
    DocumentTypeCreate,
    DocumentTypeRead,
    DocumentTypeUpdate,
)
from app.database.connection import get_db
from app.services.document_type_service import (
    DEFAULT_LIMIT,
    DocumentTypeAlreadyExistsError,
    DocumentTypeService,
)

document_type_router = APIRouter(
    prefix="/document-types", tags=["document-types"]
)

MIN_LIMIT = 1
MAX_LIMIT = 100
MIN_OFFSET = 0


@document_type_router.post(
    "",
    response_model=DocumentTypeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a document type",
)
def create_document_type(
    data: DocumentTypeCreate,
    response: Response,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentTypeRead:
    """Create a document type and return the stored representation.

    Per ADR-007 the reference list is user-editable, so types are added through
    this endpoint rather than seeded. A name already taken is 409; the check
    itself stays in the service and the database constraint, so a duplicate is
    still caught if two requests race.
    """
    try:
        document_type = DocumentTypeService.create(db, data)
    except DocumentTypeAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document type with name {error.name!r} already exists",
        ) from error

    response.headers["Location"] = str(
        request.url_for("get_document_type", document_type_id=document_type.id)
    )
    return DocumentTypeRead.model_validate(document_type)


@document_type_router.get(
    "/{document_type_id}",
    response_model=DocumentTypeRead,
    summary="Get a document type by id",
)
def get_document_type(
    document_type_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentTypeRead:
    """Return a single document type or 404 when it does not exist."""
    document_type = DocumentTypeService.get_by_id(db, document_type_id)
    if document_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document type {document_type_id} not found",
        )
    return DocumentTypeRead.model_validate(document_type)


@document_type_router.get(
    "",
    response_model=list[DocumentTypeRead],
    summary="List document types",
)
def list_document_types(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=MIN_LIMIT, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=MIN_OFFSET)] = MIN_OFFSET,
) -> list[DocumentTypeRead]:
    """Return a page of document types ordered by ascending id.

    Declared after `/{document_type_id}` so the collection route resolves on its
    own path segment and cannot be captured by the parameterised one. The page
    is produced by `DocumentTypeService.list`, which owns the ordering and the
    SQL; the response carries no total, so paging stays the caller's concern.
    """
    document_types = DocumentTypeService.list(db, limit=limit, offset=offset)
    return [DocumentTypeRead.model_validate(item) for item in document_types]


@document_type_router.patch(
    "/{document_type_id}",
    response_model=DocumentTypeRead,
    summary="Update a document type",
)
def update_document_type(
    document_type_id: int,
    data: DocumentTypeUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentTypeRead:
    """Apply a partial update, returning 404 for an unknown document type and
    409 when the new name is already taken.

    An empty payload is valid and leaves the stored row untouched; the service
    then skips the commit entirely. Surrounding whitespace is removed by
    `DocumentTypeUpdate`, so the name compared and stored is the normalised one.
    Per ADR-007 renaming is a normal operation on this reference list, so no
    other field is affected and `id` never changes.
    """
    try:
        document_type = DocumentTypeService.update(db, document_type_id, data)
    except DocumentTypeAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document type with name {error.name!r} already exists",
        ) from error

    if document_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document type {document_type_id} not found",
        )
    return DocumentTypeRead.model_validate(document_type)