from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.api.batches.schemas import BatchCreate, BatchRead, BatchUpdate
from app.models import Batch

NULLABLE = {"batch_number", "manufacture_date", "quantity", "quantity_unit"}
FIELDS = NULLABLE | {"variant_id"}


class TestBatchCreate:
    def test_required_and_defaults(self):
        with pytest.raises(ValidationError):
            BatchCreate()
        data = BatchCreate(variant_id=1)
        assert set(type(data).model_fields) == FIELDS
        assert data.model_dump() == {"variant_id": 1, **dict.fromkeys(NULLABLE)}

    @pytest.mark.parametrize("value", [None, True, False, 0, -1, 1.5, "1.5", "abc"])
    def test_invalid_variant(self, value):
        with pytest.raises(ValidationError):
            BatchCreate(variant_id=value)

    @pytest.mark.parametrize("value", [1, "1", 1.0])
    def test_variant_coercion(self, value):
        assert BatchCreate(variant_id=value).variant_id == 1

    @pytest.mark.parametrize("model", [BatchCreate, BatchUpdate])
    @pytest.mark.parametrize("field", ["id", "product_id", "sdr", "document_ids", "variant", "documents", "other"])
    def test_extra_forbidden(self, model, field):
        with pytest.raises(ValidationError):
            model(variant_id=1, **{field: 1})

    @pytest.mark.parametrize("model", [BatchCreate, BatchUpdate])
    @pytest.mark.parametrize("field,maximum", [("batch_number", 100), ("quantity_unit", 30)])
    def test_trim_and_length_boundaries(self, model, field, maximum):
        assert getattr(model(variant_id=1, **{field: "\u2003" + "Я" * maximum + "\u00a0"}), field) == "Я" * maximum
        assert getattr(model(variant_id=1, **{field: "  Ab  Cd  "}), field) == "Ab  Cd"
        for invalid in ["", " \t\n\u2003", "Я" * (maximum + 1), 42, True]:
            with pytest.raises(ValidationError):
                model(variant_id=1, **{field: invalid})

    @pytest.mark.parametrize("model", [BatchCreate, BatchUpdate])
    @pytest.mark.parametrize("value", ["0.01", "99999999.99", "5", 5, 1.25, Decimal("12.30"), None])
    def test_quantity_valid(self, model, value):
        data = model(variant_id=1, quantity=value)
        assert data.quantity == (None if value is None else Decimal(str(value)))
        assert data.quantity_unit is None

    @pytest.mark.parametrize("model", [BatchCreate, BatchUpdate])
    @pytest.mark.parametrize("value", [True, False, "0", "-0", 0, -1, "100000000", "99999999.999", "1.005", "1.000", "NaN", "Infinity", "-Infinity", Decimal("NaN"), float("inf"), ""])
    def test_quantity_invalid(self, model, value):
        with pytest.raises(ValidationError):
            model(variant_id=1, quantity=value)

    @pytest.mark.parametrize("model", [BatchCreate, BatchUpdate])
    @pytest.mark.parametrize("value,expected", [
        ("2024-02-29", date(2024, 2, 29)),
        (date(2099, 1, 1), date(2099, 1, 1)),
        (datetime(2024, 1, 1), date(2024, 1, 1)),
        ("2024-01-01T00:00:00", date(2024, 1, 1)),
        (0, date(1970, 1, 1)), (None, None),
    ])
    def test_date_coercion(self, model, value, expected):
        assert model(variant_id=1, manufacture_date=value).manufacture_date == expected

    @pytest.mark.parametrize("model", [BatchCreate, BatchUpdate])
    @pytest.mark.parametrize("value", [True, False, "", "2023-02-29", "2024-13-01", "2024-01-01T01:00:00", datetime(2024, 1, 1, 1)])
    def test_invalid_date(self, model, value):
        with pytest.raises(ValidationError):
            model(variant_id=1, manufacture_date=value)

    def test_unit_without_quantity(self):
        assert BatchCreate(variant_id=1, quantity_unit="шт").quantity is None


class TestBatchUpdate:
    def test_absent_and_explicit_null(self):
        empty = BatchUpdate()
        assert set(type(empty).model_fields) == FIELDS
        assert empty.model_fields_set == set()
        assert empty.model_dump(exclude_unset=True) == {}
        cleared = BatchUpdate(**dict.fromkeys(NULLABLE))
        assert cleared.model_fields_set == NULLABLE
        assert cleared.model_dump(exclude_unset=True) == dict.fromkeys(NULLABLE)

    @pytest.mark.parametrize("value", [None, True, False, 0, -1, 1.5])
    def test_invalid_explicit_variant(self, value):
        with pytest.raises(ValidationError):
            BatchUpdate(variant_id=value)

    def test_only_set_field_dumped(self):
        assert BatchUpdate(variant_id="2").model_dump(exclude_unset=True) == {"variant_id": 2}


class TestBatchRead:
    def test_orm_and_json(self):
        batch = Batch(id=3, variant_id=2, batch_number="B", manufacture_date=date(2024, 2, 29), quantity=Decimal("5.00"), quantity_unit="шт")
        data = BatchRead.model_validate(batch)
        assert data.model_dump(mode="json") == {"id": 3, "variant_id": 2, "batch_number": "B", "manufacture_date": "2024-02-29", "quantity": "5.00", "quantity_unit": "шт"}
        assert set(type(data).model_fields) == FIELDS | {"id"}

    def test_nullable_keys_present(self):
        assert BatchRead.model_validate(Batch(id=1, variant_id=1)).model_dump(mode="json") == {"id": 1, "variant_id": 1, **dict.fromkeys(NULLABLE)}

    def test_read_does_not_apply_write_validation(self):
        data = BatchRead.model_validate(Batch(id=1, variant_id=1, batch_number="  ", quantity=Decimal("-1.005"), quantity_unit="x" * 31))
        assert data.batch_number == "  "
        assert data.quantity == Decimal("-1.005")
        assert data.quantity_unit == "x" * 31
