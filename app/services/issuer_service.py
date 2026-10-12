from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.issuers.schemas import IssuerCreate, IssuerUpdate
from app.models.issuer import Issuer

DEFAULT_LIMIT = 50

# Name PostgreSQL gave the UNIQUE(name) constraint on issuers, and the SQLSTATE
# reported for any unique violation. Both are checked together: see
# `_is_name_unique_violation`.
UNIQUE_CONSTRAINT = "issuers_name_key"
UNIQUE_VIOLATION_SQLSTATE = "23505"


class IssuerServiceError(Exception):
    """Base error for IssuerService operations."""


class IssuerAlreadyExistsError(IssuerServiceError):
    """An issuer with the same name already exists.

    The conflicting name is kept on the instance so a caller can report it
    without parsing the message.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Issuer with name {name!r} already exists")


def _is_name_unique_violation(error: IntegrityError) -> bool:
    """True only for issuers' own unique constraint on name.

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


class IssuerService:
    """Business logic for issuers.

    An issuer is an organisation that issued a document. It is deliberately a
    separate reference list from manufacturers: the body that builds the product
    and the body that signs the certificate are different concepts, so nothing
    here reads from or writes to the manufacturers table.

    Sessions are passed in by the caller (see `app.database.connection.get_db`),
    so the service never opens or closes connections on its own.

    Transaction boundaries follow `DocumentTypeService`: writes commit exactly
    once per operation, read methods never commit. Uniqueness of name is
    enforced by the database, so writes roll back and translate that specific
    violation; a pre-check alone would still race with a concurrent insert.
    """

    @staticmethod
    def create(db: Session, data: IssuerCreate) -> Issuer:
        """Create and persist an issuer, returning the stored row."""
        issuer = Issuer(**data.model_dump())
        db.add(issuer)
        IssuerService._commit(db, data.name)
        db.refresh(issuer)
        return issuer

    @staticmethod
    def get_by_id(db: Session, issuer_id: int) -> Issuer | None:
        """Return the issuer or None when no such row exists."""
        return db.get(Issuer, issuer_id)

    @staticmethod
    def list(
        db: Session, limit: int = DEFAULT_LIMIT, offset: int = 0
    ) -> list[Issuer]:
        """Return issuers ordered by ascending id.

        Ordering by id rather than name keeps pagination stable when entries are
        renamed.
        """
        statement = select(Issuer).order_by(Issuer.id).limit(limit).offset(offset)
        return list(db.scalars(statement))

    @staticmethod
    def update(
        db: Session, issuer_id: int, data: IssuerUpdate
    ) -> Issuer | None:
        """Apply a partial update, returning None when no such row exists.

        Fields absent from the payload are left untouched. An empty payload
        changes nothing and therefore commits nothing.
        """
        issuer = db.get(Issuer, issuer_id)
        if issuer is None:
            return None

        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return issuer

        for field, value in changes.items():
            setattr(issuer, field, value)

        IssuerService._commit(db, issuer.name)
        db.refresh(issuer)
        return issuer

    @staticmethod
    def _commit(db: Session, name: str) -> None:
        """Commit, translating a name conflict and rolling back on error."""
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            if _is_name_unique_violation(error):
                raise IssuerAlreadyExistsError(name) from error
            raise