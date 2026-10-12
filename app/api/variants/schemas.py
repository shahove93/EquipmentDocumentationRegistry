from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

MAX_SIZE_TEXT_LENGTH = 100

# product_variants numeric columns are NUMERIC(10, 2): ten significant digits
# with two of them after the decimal point.
NUMERIC_PRECISION = 10
NUMERIC_SCALE = 2
NUMERIC_MAX = Decimal("99999999.99")


def _validate_measurement(value: Decimal | None) -> Decimal | None:
    """Reject anything PostgreSQL would round, overflow or store as garbage.

    Values are never rounded or truncated here: a client that sends more than
    two decimal places gets a 422 instead of silently losing precision, which
    keeps the API honest about what the column can actually store.
    """
    if value is None:
        return None

    if not value.is_finite():
        raise ValueError("value must be a finite number")

    if value <= 0:
        raise ValueError("value must be greater than 0")

    exponent = value.as_tuple().exponent
    if exponent < -NUMERIC_SCALE:
        raise ValueError(
            f"value must not have more than {NUMERIC_SCALE} decimal places"
        )

    if abs(value) > NUMERIC_MAX:
        raise ValueError(
            f"value must not exceed {NUMERIC_MAX} "
            f"(NUMERIC({NUMERIC_PRECISION}, {NUMERIC_SCALE}))"
        )

    return value


# Optional numeric measurement, kept as Decimal end to end. An explicit null is
# allowed and clears the column.
Measurement = Annotated[Decimal | None, AfterValidator(_validate_measurement)]


def _reject_bool(value: Any) -> Any:
    """Booleans are ints in Python; Pydantic would silently store True as 1."""
    if isinstance(value, bool):
        raise ValueError("product_id must be an integer, not a boolean")
    return value


ProductId = Annotated[int, BeforeValidator(_reject_bool), Field(gt=0)]

# Required free-form size designation, e.g. "Ø63 × 5.8", "Ду50", "63/57/25".
SizeText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_SIZE_TEXT_LENGTH,
    ),
]


class ProductVariantCreate(BaseModel):
    """Request body for creating a product variant.

    Per ADR-005 the SDR belongs to the product name, so no SDR attribute is
    declared here. Per ADR-006 a variant is unique per (product_id, size_text),
    but uniqueness is enforced by the database, not here. Existence of the
    product is a service-layer concern.
    """

    product_id: ProductId
    size_text: SizeText
    diameter: Measurement = None
    nominal_diameter: Measurement = None
    wall_thickness: Measurement = None


class ProductVariantCreateBody(BaseModel):
    """Request body for creating a variant under a nested product route.

    `product_id` comes from the path, so it is deliberately absent here; the
    router merges it into `ProductVariantCreate` before calling the service.
    Field types are reused from the schemas above, so no validation rule is
    duplicated.
    """

    size_text: SizeText
    diameter: Measurement = None
    nominal_diameter: Measurement = None
    wall_thickness: Measurement = None

    def to_create(self, product_id: int) -> ProductVariantCreate:
        """Build the service-level payload with the product id from the path."""
        return ProductVariantCreate(product_id=product_id, **self.model_dump())


class ProductVariantUpdate(BaseModel):
    """Request body for a partial update of a product variant.

    Fields may be omitted, in which case `model_dump(exclude_unset=True)` omits
    them and the stored row is left untouched. `product_id` is deliberately
    absent: moving a variant between products is outside this contract. An
    explicit null is rejected for size_text (NOT NULL column) but accepted for
    the nullable measurements to clear them.
    """

    size_text: SizeText | None = None
    diameter: Measurement = None
    nominal_diameter: Measurement = None
    wall_thickness: Measurement = None

    @field_validator("size_text")
    @classmethod
    def _reject_explicit_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("size_text must not be null")
        return value


class ProductVariantRead(BaseModel):
    """Response body representing a stored product variant."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    size_text: str
    diameter: Decimal | None = None
    nominal_diameter: Decimal | None = None
    wall_thickness: Decimal | None = None