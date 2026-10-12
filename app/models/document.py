from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.batch import Batch
from app.models.document_type import DocumentType
from app.models.issuer import Issuer
from app.models.product import Product
from app.models.variant import ProductVariant


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type_id: Mapped[int] = mapped_column(
        ForeignKey("document_types.id"), nullable=False
    )
    number: Mapped[str] = mapped_column(String(100), nullable=False)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    issuer_id: Mapped[int | None] = mapped_column(
        ForeignKey("issuers.id"), nullable=True
    )
    verification_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    document_type: Mapped[DocumentType] = relationship(backref="documents")
    issuer: Mapped[Issuer | None] = relationship(backref="documents")

    products: Mapped[list[Product]] = relationship(
        secondary="document_products", back_populates="documents"
    )
    variants: Mapped[list[ProductVariant]] = relationship(
        secondary="document_variants", back_populates="documents"
    )
    batches: Mapped[list[Batch]] = relationship(
        secondary="document_batches", back_populates="documents"
    )

    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('pending', 'verified', 'rejected')",
            name="ck_documents_verification_status",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_documents_valid_range",
        ),
    )