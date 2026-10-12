from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

MAX_NAME_LENGTH = 100

# Shared by Create and Update so the two cannot drift apart. Mirrors
# document_types.name VARCHAR(100) NOT NULL in the database.
NameField = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_NAME_LENGTH,
    ),
]


class DocumentTypeCreate(BaseModel):
    """Request body for creating a document type.

    Per ADR-007 document types are a user-editable reference list. Uniqueness of
    `name` is enforced by the database and the service, not here, so a duplicate
    reaches the database and produces a proper conflict rather than being
    silently rejected by the schema. The identifier is assigned by the database.
    """

    name: NameField


class DocumentTypeUpdate(BaseModel):
    """Request body for a partial update of a document type.

    The field may be omitted entirely, in which case `model_dump(exclude_unset=True)`
    yields an empty dict and nothing is changed. An explicit `null` is rejected
    because `document_types.name` is NOT NULL in the database.
    """

    name: NameField | None = None

    @field_validator("name")
    @classmethod
    def _reject_explicit_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name must not be null")
        return value


class DocumentTypeRead(BaseModel):
    """Response body representing a stored document type."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str