from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

MAX_TEXT_LENGTH = 255
MAX_PRODUCT_TYPE_LENGTH = 100

# Required text: stripped, non-empty, bounded. Used for name and standard.
RequiredText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_TEXT_LENGTH,
    ),
]

# Optional text: when supplied it must still be meaningful. An explicit null is
# accepted and clears the column, so the value is Optional in the annotations.
OptionalText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_TEXT_LENGTH,
    ),
]

# product_type is a shorter column in the model.
OptionalShortText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_PRODUCT_TYPE_LENGTH,
    ),
]


def _reject_bool(value: Any) -> Any:
    """Booleans are ints in Python; Pydantic would silently store True as 1."""
    if isinstance(value, bool):
        raise ValueError("manufacturer_id must be an integer, not a boolean")
    return value


# Foreign key values must be positive; the database assigns them from 1.
ManufacturerId = Annotated[int, BeforeValidator(_reject_bool), Field(gt=0)]


class ProductCreate(BaseModel):
    """Request body for creating a product.

    Per ADR-005 the SDR of a polyethylene pipe is part of the product name, not a
    separate field, so no SDR attribute is declared here. Manufacturer existence
    is not checked at this layer.
    """

    name: RequiredText
    standard: RequiredText
    manufacturer_id: ManufacturerId
    designation: OptionalText | None = None
    product_type: OptionalShortText | None = None


class ProductUpdate(BaseModel):
    """Request body for a partial update of a product.

    Fields may be omitted, in which case `model_dump(exclude_unset=True)` omits
    them and the stored row is left untouched. An explicit null is rejected for
    NOT NULL columns (name, standard, manufacturer_id) but accepted for the
    nullable ones (designation, product_type) to clear their value.
    """

    name: RequiredText | None = None
    standard: RequiredText | None = None
    manufacturer_id: ManufacturerId | None = None
    designation: OptionalText | None = None
    product_type: OptionalShortText | None = None

    @field_validator("name", "standard", "manufacturer_id")
    @classmethod
    def _reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("value must not be null for a NOT NULL column")
        return value


class ProductRead(BaseModel):
    """Response body representing a stored product."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    standard: str
    manufacturer_id: int
    designation: str | None = None
    product_type: str | None = None