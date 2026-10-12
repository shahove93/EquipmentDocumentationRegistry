from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.document_types.schemas import (
    DocumentTypeCreate,
    DocumentTypeUpdate,
)
from app.models.document_type import DocumentType

DEFAULT_LIMIT = 50

# Name PostgreSQL gave the UNIQUE(name) constraint on document_types, and the
# SQLSTATE reported for any unique violation. Both are checked together: see
# `_is_name_unique_violation`.
UNIQUE_CONSTRAINT = "document_types_name_key"
UNIQUE_VIOLATION_SQLSTATE = "23505"


class DocumentTypeServiceError(Exception):
    """Base error for DocumentTypeService operations."""


class DocumentTypeAlreadyExistsError(DocumentTypeServiceError):
    """A document type with the same name already exists.

    The conflicting name is kept on the instance so a caller can report it
    without parsing the message.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Document type with name {name!r} already exists")


def _is_name_unique_violation(error: IntegrityError) -> bool:
    """True only for document_types' own unique constraint on name.

    SQLSTATE 23505 on its own is not enough: any unique constraint in the
    database reports it, so the constraint name is checked too. Any other
    integrity error (not-null, other unique constraints, foreign keys) is left
    untouched so it surfaces as its own database error.
    """
    original = error.orig
    if getattr(original, "sqlstate", None) != UNIQUE_VIOLATION_SQLSTATE:
        return False
    diagnostics = getattr(original, "diag", None)
    return getattr(diagnostics, "constraint_name", None) == UNIQUE_CONSTRAINT


class DocumentTypeService:
    """Business logic for document types.

    Per ADR-007 this reference list is user-editable: types are created and
    renamed through this service, and nothing seeds or locks it.

    Sessions are passed in by the caller (see `app.database.connection.get_db`),
    so the service never opens or closes connections on its own.

    Transaction boundaries follow `ProductVariantService`: writes commit
    exactly once per operation, read methods never commit. Uniqueness of name is
    enforced by the database, so writes roll back and translate that specific
    violation; a pre-check alone would still race with a concurrent insert.
    """

    @staticmethod
    def create(db: Session, data: DocumentTypeCreate) -> DocumentType:
        """Create and persist a document type, returning the stored row."""
        document_type = DocumentType(**data.model_dump())
        db.add(document_type)
        DocumentTypeService._commit(db, data.name)
        db.refresh(document_type)
        return document_type

    @staticmethod
    def get_by_id(db: Session, document_type_id: int) -> DocumentType | None:
        """Return the document type or None when no such row exists."""
        return db.get(DocumentType, document_type_id)

    @staticmethod
    def list(
        db: Session, limit: int = DEFAULT_LIMIT, offset: int = 0
    ) -> list[DocumentType]:
        """Return document types ordered by ascending id.

        Ordering by id rather than name keeps pagination stable when entries are
        renamed, which ADR-007 allows at any time.
        """
        statement = (
            select(DocumentType)
            .order_by(DocumentType.id)
            .limit(limit)
            .offset(offset)
        )
        return list(db.scalars(statement))

    @staticmethod
    def update(
        db: Session, document_type_id: int, data: DocumentTypeUpdate
    ) -> DocumentType | None:
        """Apply a partial update, returning None when no such row exists.

        Fields absent from the payload are left untouched. An empty payload
        changes nothing and therefore commits nothing.
        """
        document_type = db.get(DocumentType, document_type_id)
        if document_type is None:
            return None

        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return document_type

        for field, value in changes.items():
            setattr(document_type, field, value)

        DocumentTypeService._commit(db, document_type.name)
        db.refresh(document_type)
        return document_type

    @staticmethod
    def _commit(db: Session, name: str) -> None:
        """Commit, translating a name conflict and rolling back on error."""
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            if _is_name_unique_violation(error):
                raise DocumentTypeAlreadyExistsError(name) from error
            raise