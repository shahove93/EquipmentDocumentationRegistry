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

from app.api.issuers.schemas import IssuerCreate, IssuerRead, IssuerUpdate
from app.database.connection import get_db
from app.services.issuer_service import (
    DEFAULT_LIMIT,
    IssuerAlreadyExistsError,
    IssuerService,
)

issuer_router = APIRouter(prefix="/issuers", tags=["issuers"])

MIN_LIMIT = 1
MAX_LIMIT = 100
MIN_OFFSET = 0


@issuer_router.post(
    "",
    response_model=IssuerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an issuer",
)
def create_issuer(
    data: IssuerCreate,
    response: Response,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> IssuerRead:
    """Create an issuer and return the stored representation.

    An issuer is an organisation that issued a document, which is a separate
    concept from a manufacturer; the two reference lists are never merged.

    A name already taken is 409. The check itself stays in the service and the
    database constraint, so a duplicate is still caught if two requests race.
    """
    try:
        issuer = IssuerService.create(db, data)
    except IssuerAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Issuer with name {error.name!r} already exists",
        ) from error

    response.headers["Location"] = str(
        request.url_for("get_issuer", issuer_id=issuer.id)
    )
    return IssuerRead.model_validate(issuer)


@issuer_router.get(
    "/{issuer_id}",
    response_model=IssuerRead,
    summary="Get an issuer by id",
)
def get_issuer(
    issuer_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> IssuerRead:
    """Return a single issuer or 404 when it does not exist."""
    issuer = IssuerService.get_by_id(db, issuer_id)
    if issuer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issuer {issuer_id} not found",
        )
    return IssuerRead.model_validate(issuer)


@issuer_router.get(
    "",
    response_model=list[IssuerRead],
    summary="List issuers",
)
def list_issuers(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=MIN_LIMIT, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=MIN_OFFSET)] = MIN_OFFSET,
) -> list[IssuerRead]:
    """Return a page of issuers ordered by ascending id.

    Declared after `/{issuer_id}` so the collection route resolves on its own
    path segment and cannot be captured by the parameterised one. The page is
    produced by `IssuerService.list`, which owns the ordering and the SQL; the
    response carries no total, so paging stays the caller's concern.
    """
    issuers = IssuerService.list(db, limit=limit, offset=offset)
    return [IssuerRead.model_validate(item) for item in issuers]


@issuer_router.patch(
    "/{issuer_id}",
    response_model=IssuerRead,
    summary="Update an issuer",
)
def update_issuer(
    issuer_id: int,
    data: IssuerUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> IssuerRead:
    """Apply a partial update, returning 404 for an unknown issuer and 409 when
    the new name is already taken.

    An empty payload is valid and leaves the stored row untouched; the service
    then skips the commit entirely. Surrounding whitespace is removed by
    `IssuerUpdate`, so the name compared and stored is the normalised one.
    Renaming an issuer is a normal operation on this reference list, so no other
    field is affected and `id` never changes.
    """
    try:
        issuer = IssuerService.update(db, issuer_id, data)
    except IssuerAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Issuer with name {error.name!r} already exists",
        ) from error

    if issuer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issuer {issuer_id} not found",
        )
    return IssuerRead.model_validate(issuer)