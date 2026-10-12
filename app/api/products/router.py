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

from app.api.products.schemas import ProductCreate, ProductRead, ProductUpdate
from app.database.connection import get_db
from app.services.product_service import (
    DEFAULT_LIMIT,
    ManufacturerNotFoundError,
    ProductService,
)

product_router = APIRouter(prefix="/products", tags=["products"])

MIN_LIMIT = 1
MAX_LIMIT = 100
MIN_OFFSET = 0


@product_router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
)
def create_product(
    data: ProductCreate,
    response: Response,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> ProductRead:
    """Create a product and return the stored representation.

    A reference to an unknown manufacturer is reported as 404; the service
    raises `ManufacturerNotFoundError` before any row is written.
    """
    try:
        product = ProductService.create(db, data)
    except ManufacturerNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manufacturer {error.manufacturer_id} not found",
        ) from error

    response.headers["Location"] = str(
        request.url_for("get_product", product_id=product.id)
    )
    return ProductRead.model_validate(product)


@product_router.get(
    "/{product_id}",
    response_model=ProductRead,
    summary="Get a product by id",
)
def get_product(
    product_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> ProductRead:
    """Return a single product or 404 when it does not exist."""
    product = ProductService.get_by_id(db, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    return ProductRead.model_validate(product)


@product_router.get(
    "",
    response_model=list[ProductRead],
    summary="List products",
)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=MIN_LIMIT, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=MIN_OFFSET)] = MIN_OFFSET,
) -> list[ProductRead]:
    """Return a page of products ordered by ascending id.

    Declared after `/{product_id}` so the collection route resolves on its own
    path segment and cannot be captured by the parameterised one.
    """
    products = ProductService.list(db, limit=limit, offset=offset)
    return [ProductRead.model_validate(item) for item in products]


@product_router.patch(
    "/{product_id}",
    response_model=ProductRead,
    summary="Update a product",
)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ProductRead:
    """Apply a partial update, returning 404 when the product or the referenced
    manufacturer is unknown.

    An empty payload is valid and leaves the stored row untouched. The service
    validates the new manufacturer before mutating any column, so a rejected
    change is never partially applied.
    """
    try:
        product = ProductService.update(db, product_id, data)
    except ManufacturerNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manufacturer {error.manufacturer_id} not found",
        ) from error

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    return ProductRead.model_validate(product)