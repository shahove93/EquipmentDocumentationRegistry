from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.variant import ProductVariant


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id"), nullable=False
    )
    batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manufacture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    quantity_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)

    variant: Mapped[ProductVariant] = relationship(backref="batches")

    documents: Mapped[list["Document"]] = relationship(
        secondary="document_batches", back_populates="batches"
    )