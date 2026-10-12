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

from app.api.variants.schemas import (
    ProductVariantCreateBody,
    ProductVariantRead,
    ProductVariantUpdate,
)
from app.database.connection import get_db
from app.services.variant_service import (
    DEFAULT_LIMIT,
    ProductNotFoundError,
    ProductVariantService,
    VariantAlreadyExistsError,
)

# Creation is nested under the product, retrieval is addressed directly by the
# variant id, so the router carries no prefix and declares both full paths.
variant_router = APIRouter(tags=["variants"])

MIN_LIMIT = 1
MAX_LIMIT = 100
MIN_OFFSET = 0


@variant_router.post(
    "/products/{product_id}/variants",
    response_model=ProductVariantRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product variant",
)
def create_product_variant(
    product_id: int,
    data: ProductVariantCreateBody,
    response: Response,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> ProductVariantRead:
    """Create a variant of the product named in the path.

    The product id travels in the URL, not in the body. An unknown product is
    404; a size already registered for that product is 409 (ADR-006).
    """
    try:
        variant = ProductVariantService.create(db, data.to_create(product_id))
    except ProductNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {error.product_id} not found",
        ) from error
    except VariantAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Variant with size_text {error.size_text!r} already exists "
                f"for product {error.product_id}"
            ),
        ) from error

    response.headers["Location"] = str(
        request.url_for("get_product_variant", variant_id=variant.id)
    )
    return ProductVariantRead.model_validate(variant)


@variant_router.get(
    "/variants/{variant_id}",
    response_model=ProductVariantRead,
    summary="Get a product variant by id",
)
def get_product_variant(
    variant_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> ProductVariantRead:
    """Return a single product variant or 404 when it does not exist."""
    variant = ProductVariantService.get_by_id(db, variant_id)
    if variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant {variant_id} not found",
        )
    return ProductVariantRead.model_validate(variant)


@variant_router.get(
    "/products/{product_id}/variants",
    response_model=list[ProductVariantRead],
    summary="List variants of a product",
)
def list_product_variants(
    product_id: int,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=MIN_LIMIT, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=MIN_OFFSET)] = MIN_OFFSET,
) -> list[ProductVariantRead]:
    """Return a page of variants of one product ordered by ascending id.

    Filtering and ordering live in the service; the product is verified there
    too, so an unknown product is reported as 404 rather than an empty list.
    """
    try:
        variants = ProductVariantService.list(
            db, product_id, limit=limit, offset=offset
        )
    except ProductNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {error.product_id} not found",
        ) from error

    return [ProductVariantRead.model_validate(item) for item in variants]


@variant_router.patch(
    "/variants/{variant_id}",
    response_model=ProductVariantRead,
    summary="Update a product variant",
)
def update_product_variant(
    variant_id: int,
    data: ProductVariantUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ProductVariantRead:
    """Apply a partial update, returning 404 for an unknown variant and 409 when
    the new size is already registered for the same product (ADR-006).

    An empty payload is valid and leaves the stored row untouched. `product_id`
    is absent from the update schema, so a variant never moves between products.
    """
    try:
        variant = ProductVariantService.update(db, variant_id, data)
    except VariantAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Variant with size_text {error.size_text!r} already exists "
                f"for product {error.product_id}"
            ),
        ) from error

    if variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant {variant_id} not found",
        )
    return ProductVariantRead.model_validate(variant)