from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.variants.schemas import ProductVariantCreate, ProductVariantUpdate
from app.models.product import Product
from app.models.variant import ProductVariant
from app.services.product_service import ProductService

DEFAULT_LIMIT = 50

# ADR-006 constraint on product_variants, and the PostgreSQL SQLSTATE for any
# unique violation.
UNIQUE_CONSTRAINT = "uq_product_variants_product_id_size_text"
UNIQUE_VIOLATION_SQLSTATE = "23505"


class VariantServiceError(Exception):
    """Base error for ProductVariantService operations."""


class ProductNotFoundError(VariantServiceError):
    """The referenced product does not exist."""

    def __init__(self, product_id: int) -> None:
        self.product_id = product_id
        super().__init__(f"Product {product_id} not found")


class VariantAlreadyExistsError(VariantServiceError):
    """A variant with the same (product_id, size_text) already exists."""

    def __init__(self, product_id: int, size_text: str) -> None:
        self.product_id = product_id
        self.size_text = size_text
        super().__init__(
            f"Variant with size_text {size_text!r} already exists "
            f"for product {product_id}"
        )


def _is_variant_unique_violation(error: IntegrityError) -> bool:
    """True only for ADR-006's unique constraint.

    SQLSTATE 23505 on its own is not enough: any unique constraint in the
    database reports it, so the constraint name is checked too. Any other
    integrity error (foreign key, not-null, other unique constraints) is left
    untouched so it surfaces as its own database error.
    """
    original = error.orig
    if getattr(original, "sqlstate", None) != UNIQUE_VIOLATION_SQLSTATE:
        return False
    diagnostics = getattr(original, "diag", None)
    return getattr(diagnostics, "constraint_name", None) == UNIQUE_CONSTRAINT


class ProductVariantService:
    """Business logic for product variants.

    Sessions are passed in by the caller (see `app.database.connection.get_db`),
    so the service never opens or closes connections on its own.

    Transaction boundaries follow `ProductService`: writes commit exactly once
    per operation, read methods never commit. Uniqueness of
    (product_id, size_text) is enforced by the database (ADR-006), so writes
    roll back and translate that specific violation; a pre-check alone would
    still race with a concurrent insert.
    """

    @staticmethod
    def create(db: Session, data: ProductVariantCreate) -> ProductVariant:
        """Create and persist a variant, returning the stored row."""
        ProductVariantService._require_product(db, data.product_id)

        variant = ProductVariant(**data.model_dump())
        db.add(variant)
        ProductVariantService._commit(db, data.product_id, data.size_text)
        db.refresh(variant)
        return variant

    @staticmethod
    def get_by_id(db: Session, variant_id: int) -> ProductVariant | None:
        """Return the variant or None when no such row exists."""
        return db.get(ProductVariant, variant_id)

    @staticmethod
    def list(
        db: Session, product_id: int, limit: int = DEFAULT_LIMIT, offset: int = 0
    ) -> list[ProductVariant]:
        """Return variants of one product ordered by ascending id."""
        ProductVariantService._require_product(db, product_id)

        statement = (
            select(ProductVariant)
            .where(ProductVariant.product_id == product_id)
            .order_by(ProductVariant.id)
            .limit(limit)
            .offset(offset)
        )
        return list(db.scalars(statement))

    @staticmethod
    def update(
        db: Session, variant_id: int, data: ProductVariantUpdate
    ) -> ProductVariant | None:
        """Apply a partial update, returning None when no such row exists.

        `product_id` is never modified: it is absent from the update schema and
        is not part of the applied changes. An empty payload changes nothing and
        therefore commits nothing.
        """
        variant = db.get(ProductVariant, variant_id)
        if variant is None:
            return None

        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return variant

        product_id = variant.product_id
        for field, value in changes.items():
            setattr(variant, field, value)

        ProductVariantService._commit(db, product_id, variant.size_text)
        db.refresh(variant)
        return variant

    @staticmethod
    def _require_product(db: Session, product_id: int) -> Product:
        """Return the product or raise ProductNotFoundError."""
        product = ProductService.get_by_id(db, product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        return product

    @staticmethod
    def _commit(db: Session, product_id: int, size_text: str) -> None:
        """Commit, translating an ADR-006 violation and rolling back on error."""
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            if _is_variant_unique_violation(error):
                raise VariantAlreadyExistsError(product_id, size_text) from error
            raise