from datetime import date
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
    field_validator,
    model_validator,
)

# Mirrors documents.number VARCHAR(100) NOT NULL in the database. The limit is
# measured after surrounding whitespace is removed, so padding cannot be used to
# smuggle an over-long value past the constraint.
MAX_NUMBER_LENGTH = 100

# Shared by Create and Update so the two cannot drift apart.
NumberField = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_NUMBER_LENGTH,
    ),
]


def _reject_bool(value: Any) -> Any:
    """Booleans are ints in Python; Pydantic would silently store True as 1."""
    if isinstance(value, bool):
        raise ValueError("identifier must be an integer, not a boolean")
    return value


# Foreign key values must be positive; the database assigns them from 1.
ForeignKeyId = Annotated[int, BeforeValidator(_reject_bool), Field(gt=0)]


def _check_period(valid_from: date, valid_to: date) -> None:
    """Raise unless the validity window is not inverted.

    Mirrors `ck_documents_valid_range` on the table. The database allows either
    bound to be NULL; that case never reaches this helper.
    """
    if valid_to < valid_from:
        raise ValueError("valid_to must not be earlier than valid_from")


class DocumentCreate(BaseModel):
    """Request body for creating a document.

    `verification_status` is deliberately absent: the column is NOT NULL and the
    server assigns `pending` on insert (`server_default='pending'`). Accepting it
    from a client would let a document be born already verified.

    Uploaded files are not part of this body. `document_products`,
    `document_variants` and `document_batches` are likewise absent: linking is a
    separate concern handled by a separate operation.

    `notes` maps to a TEXT column, which has no length limit, so none is imposed
    here. Existence of `document_type_id` and `issuer_id` is a service-layer
    concern; this schema only checks that they are positive integers.
    """

    model_config = ConfigDict(extra="forbid")

    document_type_id: ForeignKeyId
    number: NumberField
    issue_date: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    issuer_id: ForeignKeyId | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _validate_period(self) -> Self:
        """Check the validity window only when both bounds are present.

        A missing bound is a legitimate open-ended window, so the other bound
        must not be demanded.
        """
        if self.valid_from is not None and self.valid_to is not None:
            _check_period(self.valid_from, self.valid_to)
        return self


class DocumentUpdate(BaseModel):
    """Request body for a partial update of a document.

    Every field is optional. A field that is absent is not mentioned by
    `model_dump(exclude_unset=True)` and therefore leaves the stored row
    untouched; a field sent as an explicit `null` is mentioned with the value
    `None` and clears the column. `model_fields_set` keeps the two apart.

    `document_type_id` and `number` map to NOT NULL columns, so an explicit
    `null` is rejected for them. `issue_date`, `valid_from`, `valid_to`,
    `issuer_id` and `notes` are nullable and may be cleared.

    The validity window is checked only when both bounds are supplied together.
    Changing one bound leaves the result dependent on the other, which lives in
    the database; validating the merged document is the service's job, not the
    schema's. Rejecting a one-sided PATCH here would refuse legitimate
    corrections.

    `verification_status` is absent on purpose. Moving a document between
    `pending`, `verified` and `rejected` changes its lifecycle, and the rules for
    that transition — including any automatic reset when validity data changes —
    belong to DocumentService.
    """

    model_config = ConfigDict(extra="forbid")

    document_type_id: ForeignKeyId | None = None
    number: NumberField | None = None
    issue_date: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    issuer_id: ForeignKeyId | None = None
    notes: str | None = None

    @field_validator("document_type_id", "number")
    @classmethod
    def _reject_explicit_null(cls, value: object) -> object:
        """Refuse an explicit null for a NOT NULL column.

        Not called when the field is absent, which is what makes `{}` a valid
        no-op patch.
        """
        if value is None:
            raise ValueError("value must not be null for a NOT NULL column")
        return value

    @model_validator(mode="after")
    def _validate_period_when_both_supplied(self) -> Self:
        """Check the window only when both bounds are explicitly sent as dates."""
        supplied = self.model_fields_set
        if "valid_from" in supplied and "valid_to" in supplied:
            if self.valid_from is not None and self.valid_to is not None:
                _check_period(self.valid_from, self.valid_to)
        return self


class DocumentOut(BaseModel):
    """Response body representing a stored document.

    `from_attributes` lets the same schema serialise an ORM row and validate a
    plain mapping.

    `verification_status` is a plain string rather than an enum: the allowed
    values are enforced by `ck_documents_verification_status` in the database,
    and mirroring that constraint here would duplicate it in a second place.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    document_type_id: int
    number: str
    issue_date: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    issuer_id: int | None = None
    verification_status: str
    notes: str | None = None


class DocumentListOut(RootModel[list[DocumentOut]]):
    """Response body for a page of documents.

    A bare JSON array, matching every existing collection endpoint in the
    project: `/manufacturers`, `/products`, `/product_variants`, `/document-types`
    and `/issuers` all return the page directly and carry no total, so paging
    stays the caller's concern. `limit=50` by default, at most 100, `offset=0`,
    ordered by ascending id.
    """