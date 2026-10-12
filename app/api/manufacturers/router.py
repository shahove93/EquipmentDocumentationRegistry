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

from app.api.manufacturers.schemas import (
    ManufacturerCreate,
    ManufacturerRead,
    ManufacturerUpdate,
)
from app.database.connection import get_db
from app.services.manufacturer_service import DEFAULT_LIMIT, ManufacturerService

manufacturer_router = APIRouter(prefix="/manufacturers", tags=["manufacturers"])

MIN_LIMIT = 1
MAX_LIMIT = 100
MIN_OFFSET = 0


@manufacturer_router.post(
    "",
    response_model=ManufacturerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manufacturer",
)
def create_manufacturer(
    data: ManufacturerCreate,
    response: Response,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> ManufacturerRead:
    """Create a manufacturer and return the stored representation."""
    manufacturer = ManufacturerService.create(db, data)
    response.headers["Location"] = str(
        request.url_for("get_manufacturer", manufacturer_id=manufacturer.id)
    )
    return ManufacturerRead.model_validate(manufacturer)


@manufacturer_router.get(
    "/{manufacturer_id}",
    response_model=ManufacturerRead,
    summary="Get a manufacturer by id",
)
def get_manufacturer(
    manufacturer_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> ManufacturerRead:
    """Return a single manufacturer or 404 when it does not exist."""
    manufacturer = ManufacturerService.get_by_id(db, manufacturer_id)
    if manufacturer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manufacturer {manufacturer_id} not found",
        )
    return ManufacturerRead.model_validate(manufacturer)


@manufacturer_router.get(
    "",
    response_model=list[ManufacturerRead],
    summary="List manufacturers",
)
def list_manufacturers(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=MIN_LIMIT, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=MIN_OFFSET)] = MIN_OFFSET,
) -> list[ManufacturerRead]:
    """Return a page of manufacturers ordered by ascending id.

    Declared after `/{manufacturer_id}` so the collection route resolves on its
    own path segment and cannot be captured by the parameterised one.
    """
    manufacturers = ManufacturerService.list(db, limit=limit, offset=offset)
    return [ManufacturerRead.model_validate(item) for item in manufacturers]


@manufacturer_router.patch(
    "/{manufacturer_id}",
    response_model=ManufacturerRead,
    summary="Update a manufacturer",
)
def update_manufacturer(
    manufacturer_id: int,
    data: ManufacturerUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ManufacturerRead:
    """Apply a partial update, returning 404 when the manufacturer is unknown.

    An empty payload is valid and leaves the stored row untouched.
    """
    manufacturer = ManufacturerService.update(db, manufacturer_id, data)
    if manufacturer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manufacturer {manufacturer_id} not found",
        )
    return ManufacturerRead.model_validate(manufacturer)