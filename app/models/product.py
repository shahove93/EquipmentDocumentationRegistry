from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.manufacturer import Manufacturer


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    standard: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer_id: Mapped[int] = mapped_column(
        ForeignKey("manufacturers.id"), nullable=False
    )

    manufacturer: Mapped[Manufacturer] = relationship(backref="products")

    documents: Mapped[list["Document"]] = relationship(
        secondary="document_products", back_populates="products"
    )