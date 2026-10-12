from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

MAX_NAME_LENGTH = 255

# Shared by Create and Update so the two cannot drift apart. Mirrors
# issuers.name VARCHAR(255) NOT NULL in the database.
NameField = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_NAME_LENGTH,
    ),
]


class IssuerCreate(BaseModel):
    """Request body for creating an issuer.

    An issuer is an organisation that issued a document. It is a separate
    reference list from manufacturers on purpose: the body performing the
    testing and the body signing the certificate are not the same concept, so
    the two must not be merged.

    Uniqueness of `name` is enforced by the database and the service, not here,
    so a duplicate reaches the database and produces a proper conflict rather
    than being silently rejected by the schema. The identifier is assigned by
    the database.
    """

    name: NameField


class IssuerUpdate(BaseModel):
    """Request body for a partial update of an issuer.

    The field may be omitted entirely, in which case `model_dump(exclude_unset=True)`
    yields an empty dict and nothing is changed. An explicit `null` is rejected
    because `issuers.name` is NOT NULL in the database.
    """

    name: NameField | None = None

    @field_validator("name")
    @classmethod
    def _reject_explicit_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name must not be null")
        return value


class IssuerRead(BaseModel):
    """Response body representing a stored issuer."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str