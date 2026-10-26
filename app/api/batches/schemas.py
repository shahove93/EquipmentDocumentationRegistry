from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints,
    field_validator,
)

from app.api.variants.schemas import Measurement as Quantity


def _reject_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("variant_id must be an integer, not a boolean")
    return value


VariantId = Annotated[int, BeforeValidator(_reject_bool), Field(gt=0)]
BatchNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
QuantityUnit = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)
]


class BatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: VariantId
    batch_number: BatchNumber | None = None
    manufacture_date: date | None = None
    quantity: Quantity = None
    quantity_unit: QuantityUnit | None = None


class BatchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: VariantId | None = None
    batch_number: BatchNumber | None = None
    manufacture_date: date | None = None
    quantity: Quantity = None
    quantity_unit: QuantityUnit | None = None

    @field_validator("variant_id")
    @classmethod
    def _reject_explicit_null(cls, value: int | None) -> int:
        if value is None:
            raise ValueError("variant_id must not be null")
        return value


class BatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    batch_number: str | None = None
    manufacture_date: date | None = None
    quantity: Decimal | None = None
    quantity_unit: str | None = None
