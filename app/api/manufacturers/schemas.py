from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_NAME_LENGTH = 255

NameField = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_NAME_LENGTH,
    ),
]


class ManufacturerCreate(BaseModel):
    """Request body for creating a manufacturer.

    Only the name is accepted; the identifier is assigned by the database.
    """

    name: NameField


class ManufacturerUpdate(BaseModel):
    """Request body for a partial update of a manufacturer.

    The field may be omitted entirely, in which case `model_dump(exclude_unset=True)`
    yields an empty dict and nothing is changed. An explicit `null` is rejected
    because `manufacturers.name` is NOT NULL in the database.
    """

    name: NameField | None = None

    @field_validator("name")
    @classmethod
    def _reject_explicit_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name must not be null")
        return value


class ManufacturerRead(BaseModel):
    """Response body representing a stored manufacturer."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str