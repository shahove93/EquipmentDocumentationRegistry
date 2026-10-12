from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.product import Product


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    diameter: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    nominal_diameter: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    wall_thickness: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    size_text: Mapped[str] = mapped_column(String(100), nullable=False)

    product: Mapped[Product] = relationship(backref="variants")

    documents: Mapped[list["Document"]] = relationship(
        secondary="document_variants", back_populates="variants"
    )

    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "size_text",
            name="uq_product_variants_product_id_size_text",
        ),
    )