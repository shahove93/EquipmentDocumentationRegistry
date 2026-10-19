"""Request schema for replacing the sizes a document is linked to.

The response is the existing `ProductVariantRead`, so nothing new is declared for
output here. Only the body of `PUT /documents/{document_id}/variants` needs a
shape, and it needs an unusually strict one: the numbers in `variant_ids` are
primary keys of `ProductVariant` rows, not diameters, and a value that is a
plausible diameter but not a real id would silently target the wrong row.

Hence the item type is validated before Pydantic's own coercion ever runs. In
lax mode `int` fields happily accept `"63"`, `63.0` and — because `bool` is a
subclass of `int` in Python — `true`, all of which would become `63` here. Each
of those is refused instead: an id is an integer, and a client that sends
something else has a bug worth surfacing rather than a request worth guessing at.
"""

from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)


def _require_int(value: Any) -> Any:
    """Refuse anything that is not already a plain integer.

    Runs before coercion, so `True`, `"3"` and `3.0` are all rejected rather than
    quietly becoming `1`, `3` and `3`.
    """
    if isinstance(value, bool):
        raise ValueError("variant ids must be integers, not booleans")
    if not isinstance(value, int):
        raise ValueError("variant ids must be integers")
    return value


# A primary key: a real integer, at least 1. The database assigns ids from 1, so
# 0 and negatives can only be a mistake.
VariantId = Annotated[int, BeforeValidator(_require_int), Field(gt=0)]


class DocumentVariantLinkRequest(BaseModel):
    """Body of `PUT /documents/{document_id}/variants`.

    The list is mandatory — omitting it or sending `null` is refused with 422
    rather than read as "clear everything", because an empty replacement is a
    deliberate act (`"variant_ids": []`) and must not be reachable by accident.

    Duplicate ids are refused as well. The set being replaced is a set, and the
    service refuses a repeated id too (see `DuplicateVariantIdsError`); catching
    it here means the request is rejected before a session is even opened, with a
    message that names the repeated ids. Duplicates are never collapsed silently,
    so a client that builds the list wrongly is told so.
    """

    model_config = ConfigDict(extra="forbid")

    variant_ids: list[VariantId]

    @model_validator(mode="after")
    def _reject_duplicates(self) -> "DocumentVariantLinkRequest":
        seen: set[int] = set()
        repeated: set[int] = set()
        for variant_id in self.variant_ids:
            if variant_id in seen:
                repeated.add(variant_id)
            else:
                seen.add(variant_id)
        if repeated:
            raise ValueError(
                f"duplicate variant ids: {sorted(repeated)}"
            )
        return self
