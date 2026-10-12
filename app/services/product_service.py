from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.products.schemas import ProductCreate, ProductUpdate
from app.models.manufacturer import Manufacturer
from app.models.product import Product
from app.services.manufacturer_service import ManufacturerService

DEFAULT_LIMIT = 50


class ProductServiceError(Exception):
    """Base error for ProductService operations."""


class ManufacturerNotFoundError(ProductServiceError):
    """The referenced manufacturer does not exist."""

    def __init__(self, manufacturer_id: int) -> None:
        self.manufacturer_id = manufacturer_id
        super().__init__(f"Manufacturer {manufacturer_id} not found")


class ProductService:
    """Business logic for products.

    Sessions are passed in by the caller (see `app.database.connection.get_db`),
    so the service never opens or closes connections on its own.

    Transaction boundaries follow `ManufacturerService`: writes commit exactly
    once per operation, and read methods never commit. Referential checks for
    `manufacturer_id` run before any column is mutated, so a rejected request
    leaves neither a partially updated row nor a pending change in the session.
    """

    @staticmethod
    def create(db: Session, data: ProductCreate) -> Product:
        """Create and persist a product, returning the stored row."""
        ProductService._require_manufacturer(db, data.manufacturer_id)

        product = Product(**data.model_dump())
        db.add(product)
        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def get_by_id(db: Session, product_id: int) -> Product | None:
        """Return the product or None when no such row exists."""
        return db.get(Product, product_id)

    @staticmethod
    def list(
        db: Session, limit: int = DEFAULT_LIMIT, offset: int = 0
    ) -> list[Product]:
        """Return products ordered by ascending id."""
        statement = (
            select(Product).order_by(Product.id).limit(limit).offset(offset)
        )
        return list(db.scalars(statement))

    @staticmethod
    def update(
        db: Session, product_id: int, data: ProductUpdate
    ) -> Product | None:
        """Apply a partial update, returning None when no such row exists.

        Fields absent from the payload are left untouched. An empty payload
        changes nothing and therefore commits nothing.
        """
        product = db.get(Product, product_id)
        if product is None:
            return None

        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return product

        if "manufacturer_id" in changes:
            # validated before mutating so a rejected change is never applied
            ProductService._require_manufacturer(db, changes["manufacturer_id"])

        for field, value in changes.items():
            setattr(product, field, value)

        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def _require_manufacturer(db: Session, manufacturer_id: int) -> Manufacturer:
        """Return the manufacturer or raise ManufacturerNotFoundError."""
        manufacturer = ManufacturerService.get_by_id(db, manufacturer_id)
        if manufacturer is None:
            raise ManufacturerNotFoundError(manufacturer_id)
        return manufacturer