from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.batches.schemas import BatchCreate, BatchUpdate
from app.models.batch import Batch
from app.models.variant import ProductVariant
from app.services.variant_service import ProductVariantService

DEFAULT_LIMIT = 50


class BatchServiceError(Exception):
    """Base error for batch operations."""


class VariantNotFoundError(BatchServiceError):
    def __init__(self, variant_id: int) -> None:
        self.variant_id = variant_id
        super().__init__(f"Variant {variant_id} not found")


def _is_variant_fk_violation(error: SQLAlchemyError) -> bool:
    """Classify only the batches.variant_id foreign key, using diagnostics."""
    original = getattr(error, "orig", None)
    diagnostics = getattr(original, "diag", None)
    return (
        getattr(original, "sqlstate", None) == "23503"
        and getattr(diagnostics, "constraint_name", None) == "batches_variant_id_fkey"
        and getattr(diagnostics, "table_name", None) == "batches"
    )


class BatchService:
    """Batch persistence using the caller's clean Session; writes commit once."""

    @staticmethod
    def create(db: Session, data: BatchCreate) -> Batch:
        BatchService._require_variant(db, data.variant_id)
        batch = Batch(**data.model_dump())
        db.add(batch)
        BatchService._commit(db, data.variant_id)
        db.refresh(batch)
        return batch

    @staticmethod
    def get_by_id(db: Session, batch_id: int) -> Batch | None:
        return db.get(Batch, batch_id)

    @staticmethod
    def list(db: Session, limit: int = DEFAULT_LIMIT, offset: int = 0) -> list[Batch]:
        statement = select(Batch).order_by(Batch.id.asc()).limit(limit).offset(offset)
        return list(db.scalars(statement))

    @staticmethod
    def update(db: Session, batch_id: int, data: BatchUpdate) -> Batch | None:
        batch = db.get(Batch, batch_id)
        if batch is None:
            return None
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return batch
        if "variant_id" in changes:
            BatchService._require_variant(db, changes["variant_id"])
        for field, value in changes.items():
            setattr(batch, field, value)
        BatchService._commit(db, batch.variant_id)
        db.refresh(batch)
        return batch

    @staticmethod
    def _require_variant(db: Session, variant_id: int) -> ProductVariant:
        variant = ProductVariantService.get_by_id(db, variant_id)
        if variant is None:
            raise VariantNotFoundError(variant_id)
        return variant

    @staticmethod
    def _commit(db: Session, variant_id: int) -> None:
        try:
            db.commit()
        except SQLAlchemyError as error:
            db.rollback()
            if _is_variant_fk_violation(error):
                raise VariantNotFoundError(variant_id) from error
            raise
