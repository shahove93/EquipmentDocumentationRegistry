from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.api.variants.schemas import (
    MAX_SIZE_TEXT_LENGTH,
    NUMERIC_MAX,
    NUMERIC_SCALE,
    ProductVariantCreate,
    ProductVariantRead,
    ProductVariantUpdate,
)

BASE = {"product_id": 1, "size_text": "Ø63 × 5.8"}


class TestCreateValid:
    def test_required_fields_only(self):
        schema = ProductVariantCreate(**BASE)
        assert schema.product_id == 1
        assert schema.size_text == "Ø63 × 5.8"

    def test_optional_measurements_default_to_none(self):
        schema = ProductVariantCreate(**BASE)
        assert schema.diameter is None
        assert schema.nominal_diameter is None
        assert schema.wall_thickness is None

    def test_all_fields_supplied(self):
        schema = ProductVariantCreate(
            product_id=7,
            size_text="Ду50",
            diameter=Decimal("63"),
            nominal_diameter=Decimal("50"),
            wall_thickness=Decimal("5.80"),
        )
        assert schema.product_id == 7
        assert schema.size_text == "Ду50"
        assert schema.diameter == Decimal("63")
        assert schema.nominal_diameter == Decimal("50")
        assert schema.wall_thickness == Decimal("5.80")

    def test_all_three_measurements_from_strings(self):
        schema = ProductVariantCreate(
            **BASE, diameter="63", nominal_diameter="50", wall_thickness="5.8"
        )
        assert schema.diameter == Decimal("63")
        assert schema.nominal_diameter == Decimal("50")
        assert schema.wall_thickness == Decimal("5.8")

    def test_inner_whitespace_preserved(self):
        schema = ProductVariantCreate(product_id=1, size_text="  Ø63   ×   5.8  ")
        assert schema.size_text == "Ø63   ×   5.8"

    def test_no_sdr_field(self):
        assert ("sdr" in ProductVariantCreate.model_fields) is False
        schema = ProductVariantCreate(**BASE)
        assert not hasattr(schema, "sdr")

    def test_expected_fields(self):
        assert set(ProductVariantCreate.model_fields) == {
            "product_id",
            "size_text",
            "diameter",
            "nominal_diameter",
            "wall_thickness",
        }


class TestCreateSizeText:
    def test_whitespace_stripped(self):
        schema = ProductVariantCreate(product_id=1, size_text="  Ø63 × 5.8  ")
        assert schema.size_text == "Ø63 × 5.8"

    def test_empty_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantCreate(product_id=1, size_text="")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantCreate(product_id=1, size_text="   ")

    def test_tabs_only_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantCreate(product_id=1, size_text="\t\n ")

    def test_missing_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantCreate(product_id=1)

    def test_null_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantCreate(product_id=1, size_text=None)

    def test_length_100_accepted(self):
        value = "Ø" * MAX_SIZE_TEXT_LENGTH
        assert ProductVariantCreate(product_id=1, size_text=value).size_text == value

    def test_length_101_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantCreate(product_id=1, size_text="Ø" * 101)

    def test_length_measured_after_strip(self):
        schema = ProductVariantCreate(
            product_id=1, size_text="  " + "Ø" * 100 + "  "
        )
        assert len(schema.size_text) == 100


class TestCreateProductId:
    @pytest.mark.parametrize("value", [1, 2, 999_999])
    def test_positive_accepted(self, value):
        assert ProductVariantCreate(product_id=value, size_text="Ø63").product_id == value

    @pytest.mark.parametrize("value", [0, -1, -100])
    def test_non_positive_rejected(self, value):
        with pytest.raises(ValidationError):
            ProductVariantCreate(product_id=value, size_text="Ø63")

    @pytest.mark.parametrize("value", [True, False])
    def test_boolean_rejected(self, value):
        with pytest.raises(ValidationError):
            ProductVariantCreate(product_id=value, size_text="Ø63")

    @pytest.mark.parametrize("value", [1.5, 2.9])
    def test_fractional_rejected(self, value):
        with pytest.raises(ValidationError):
            ProductVariantCreate(product_id=value, size_text="Ø63")

    def test_null_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantCreate(product_id=None, size_text="Ø63")

    def test_existence_not_checked(self):
        # ADR: product existence belongs to the service layer
        assert ProductVariantCreate(product_id=987654, size_text="Ø63").product_id == 987654

    def test_missing_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantCreate(size_text="Ø63")


class TestDecimalHandling:
    def test_values_are_decimal_not_float(self):
        schema = ProductVariantCreate(**BASE, diameter="63")
        assert isinstance(schema.diameter, Decimal)
        assert not isinstance(schema.diameter, float)

    def test_string_converted_to_decimal(self):
        assert ProductVariantCreate(**BASE, diameter="5.8").diameter == Decimal("5.8")

    def test_float_converted_to_decimal(self):
        assert ProductVariantCreate(**BASE, diameter=5.8).diameter == Decimal("5.8")

    def test_int_converted_to_decimal(self):
        schema = ProductVariantCreate(**BASE, diameter=63)
        assert schema.diameter == Decimal("63")
        assert isinstance(schema.diameter, Decimal)

    def test_decimal_passed_through_unchanged(self):
        assert ProductVariantCreate(**BASE, diameter=Decimal("5.80")).diameter == Decimal("5.80")

    def test_trailing_zeros_preserved(self):
        assert ProductVariantCreate(**BASE, diameter=Decimal("5.80")).diameter.as_tuple().exponent == -2

    @pytest.mark.parametrize("field", ["diameter", "nominal_diameter", "wall_thickness"])
    def test_null_accepted_in_create(self, field):
        assert getattr(ProductVariantCreate(**BASE, **{field: None}), field) is None

    @pytest.mark.parametrize("field", ["diameter", "nominal_diameter", "wall_thickness"])
    @pytest.mark.parametrize("value", ["abc", "", "5,8"])
    def test_non_numeric_rejected(self, field, value):
        with pytest.raises(ValidationError):
            ProductVariantCreate(**BASE, **{field: value})

    @pytest.mark.parametrize("field", ["diameter", "nominal_diameter", "wall_thickness"])
    def test_boolean_rejected(self, field):
        with pytest.raises(ValidationError):
            ProductVariantCreate(**BASE, **{field: True})


class TestMeasurementPositivity:
    @pytest.mark.parametrize("field", ["diameter", "nominal_diameter", "wall_thickness"])
    @pytest.mark.parametrize("value", ["0", "0.00", 0, 0.0, Decimal("0")])
    def test_zero_rejected(self, field, value):
        with pytest.raises(ValidationError):
            ProductVariantCreate(**BASE, **{field: value})

    @pytest.mark.parametrize("field", ["diameter", "nominal_diameter", "wall_thickness"])
    @pytest.mark.parametrize("value", ["-1", "-0.01", -1, -0.5, Decimal("-63")])
    def test_negative_rejected(self, field, value):
        with pytest.raises(ValidationError):
            ProductVariantCreate(**BASE, **{field: value})

    @pytest.mark.parametrize("field", ["diameter", "nominal_diameter", "wall_thickness"])
    @pytest.mark.parametrize("value", ["NaN", "nan", "Infinity", "-Infinity", "inf"])
    def test_non_finite_rejected(self, field, value):
        with pytest.raises(ValidationError):
            ProductVariantCreate(**BASE, **{field: value})

    @pytest.mark.parametrize("value", ["0.01", "0.1", "0.5", "1", "99999999.99"])
    def test_smallest_positive_accepted(self, value):
        assert ProductVariantCreate(**BASE, diameter=value).diameter == Decimal(value)


class TestMeasurementScale:
    @pytest.mark.parametrize("field", ["diameter", "nominal_diameter", "wall_thickness"])
    @pytest.mark.parametrize("value", ["1.005", "0.001", "5.123", "0.0001", "63.999"])
    def test_more_than_two_decimals_rejected(self, field, value):
        with pytest.raises(ValidationError):
            ProductVariantCreate(**BASE, **{field: value})

    @pytest.mark.parametrize("value", ["1.5", "5.8", "63", "0.01", "5.25"])
    def test_up_to_two_decimals_accepted(self, value):
        assert ProductVariantCreate(**BASE, diameter=value).diameter == Decimal(value)

    def test_scale_constant_is_two(self):
        assert NUMERIC_SCALE == 2

    def test_value_not_rounded_but_rejected(self):
        # the whole point: no silent rounding of 5.805 to 5.81
        with pytest.raises(ValidationError):
            ProductVariantCreate(**BASE, diameter="5.805")


class TestMeasurementPrecision:
    @pytest.mark.parametrize("field", ["diameter", "nominal_diameter", "wall_thickness"])
    def test_numeric_max_accepted(self, field):
        assert getattr(
            ProductVariantCreate(**BASE, **{field: str(NUMERIC_MAX)}), field
        ) == NUMERIC_MAX

    @pytest.mark.parametrize("field", ["diameter", "nominal_diameter", "wall_thickness"])
    @pytest.mark.parametrize(
        "value", ["100000000.00", "100000000", "999999999.99", "1000000000"]
    )
    def test_overflow_rejected(self, field, value):
        with pytest.raises(ValidationError):
            ProductVariantCreate(**BASE, **{field: value})

    def test_numeric_max_value(self):
        assert NUMERIC_MAX == Decimal("99999999.99")
        assert len(NUMERIC_MAX.as_tuple().digits) == 10

    def test_ten_digits_accepted(self):
        value = "12345678.90"
        assert ProductVariantCreate(**BASE, diameter=value).diameter == Decimal(value)

    def test_eleven_digits_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantCreate(**BASE, diameter="123456789.01")


class TestUpdateAbsentFields:
    def test_empty_body_accepted(self):
        assert ProductVariantUpdate().model_dump(exclude_unset=True) == {}

    def test_absent_fields_are_none(self):
        schema = ProductVariantUpdate()
        for field in ("size_text", "diameter", "nominal_diameter", "wall_thickness"):
            assert getattr(schema, field) is None

    def test_exclude_unset_omits_everything(self):
        assert "size_text" not in ProductVariantUpdate().model_dump(exclude_unset=True)

    def test_fields_set_tracks_provided(self):
        assert ProductVariantUpdate().model_fields_set == set()
        assert ProductVariantUpdate(size_text="X").model_fields_set == {"size_text"}

    def test_partial_payload_dumps_only_that_field(self):
        assert ProductVariantUpdate(diameter="63").model_dump(exclude_unset=True) == {
            "diameter": Decimal("63")
        }

    def test_whitespace_stripped_in_update(self):
        assert ProductVariantUpdate(size_text="  X  ").model_dump(exclude_unset=True) == {
            "size_text": "X"
        }

    def test_no_product_id_in_update(self):
        assert "product_id" not in ProductVariantUpdate.model_fields

    def test_expected_fields(self):
        assert set(ProductVariantUpdate.model_fields) == {
            "size_text",
            "diameter",
            "nominal_diameter",
            "wall_thickness",
        }


class TestUpdateNullHandling:
    def test_explicit_null_rejected_for_size_text(self):
        with pytest.raises(ValidationError):
            ProductVariantUpdate(size_text=None)

    @pytest.mark.parametrize("field", ["diameter", "nominal_diameter", "wall_thickness"])
    def test_explicit_null_accepted_for_measurements(self, field):
        schema = ProductVariantUpdate(**{field: None})
        assert getattr(schema, field) is None
        assert schema.model_dump(exclude_unset=True) == {field: None}

    def test_absent_and_null_are_distinguishable(self):
        absent = ProductVariantUpdate(size_text="X").model_dump(exclude_unset=True)
        cleared = ProductVariantUpdate(size_text="X", diameter=None).model_dump(
            exclude_unset=True
        )
        assert "diameter" not in absent
        assert cleared["diameter"] is None

    def test_null_size_text_with_valid_measurement_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantUpdate(size_text=None, diameter="63")


class TestUpdateValidation:
    @pytest.mark.parametrize("value", ["", "   ", "\t\n "])
    def test_blank_size_text_rejected(self, value):
        with pytest.raises(ValidationError):
            ProductVariantUpdate(size_text=value)

    def test_length_101_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantUpdate(size_text="Ø" * 101)

    def test_length_100_accepted(self):
        assert ProductVariantUpdate(size_text="Ø" * 100).size_text == "Ø" * 100

    @pytest.mark.parametrize("value", ["0", "-1", "1.005", "NaN", "100000000.00"])
    def test_invalid_measurements_rejected(self, value):
        with pytest.raises(ValidationError):
            ProductVariantUpdate(diameter=value)

    def test_measurement_null_not_validated(self):
        assert ProductVariantUpdate(diameter=None).diameter is None


class TestVariantRead:
    def test_from_attributes_config(self):
        assert ProductVariantRead.model_config.get("from_attributes") is True

    def test_expected_fields(self):
        assert set(ProductVariantRead.model_fields) == {
            "id",
            "product_id",
            "size_text",
            "diameter",
            "nominal_diameter",
            "wall_thickness",
        }

    def test_from_orm_object(self):
        from app.models import ProductVariant

        variant = ProductVariant(
            id=4,
            product_id=7,
            size_text="Ø63 × 5.8",
            diameter=Decimal("63"),
            nominal_diameter=Decimal("50"),
            wall_thickness=Decimal("5.80"),
        )
        schema = ProductVariantRead.model_validate(variant)
        assert schema.id == 4
        assert schema.product_id == 7
        assert schema.size_text == "Ø63 × 5.8"
        assert schema.diameter == Decimal("63")
        assert schema.nominal_diameter == Decimal("50")
        assert schema.wall_thickness == Decimal("5.80")

    def test_from_orm_object_with_null_measurements(self):
        from app.models import ProductVariant

        variant = ProductVariant(id=5, product_id=1, size_text="Ду50")
        schema = ProductVariantRead.model_validate(variant)
        assert schema.diameter is None
        assert schema.nominal_diameter is None
        assert schema.wall_thickness is None

    def test_measurements_stay_decimal(self):
        from app.models import ProductVariant

        variant = ProductVariant(id=6, product_id=1, size_text="Ду50", diameter=Decimal("63"))
        schema = ProductVariantRead.model_validate(variant)
        assert isinstance(schema.diameter, Decimal)
        assert not isinstance(schema.diameter, float)

    def test_dump_round_trip(self):
        from app.models import ProductVariant

        variant = ProductVariant(id=1, product_id=2, size_text="Ø63", diameter=Decimal("63"))
        assert ProductVariantRead.model_validate(variant).model_dump() == {
            "id": 1,
            "product_id": 2,
            "size_text": "Ø63",
            "diameter": Decimal("63"),
            "nominal_diameter": None,
            "wall_thickness": None,
        }

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            ProductVariantRead.model_validate({"size_text": "Ø63"})

    def test_unknown_attributes_ignored(self):
        row = type(
            "Row",
            (),
            {
                "id": 1,
                "product_id": 1,
                "size_text": "Ø63",
                "diameter": None,
                "nominal_diameter": None,
                "wall_thickness": None,
                "extra": "ignored",
            },
        )()
        assert "extra" not in ProductVariantRead.model_validate(row).model_dump()


class TestSchemasMirrorModel:
    def test_read_columns_match_model(self):
        from app.models import ProductVariant

        assert set(ProductVariantRead.model_fields) == set(
            ProductVariant.__table__.columns.keys()
        )

    def test_create_columns_match_model_minus_id(self):
        from app.models import ProductVariant

        assert set(ProductVariantCreate.model_fields) == (
            set(ProductVariant.__table__.columns.keys()) - {"id"}
        )

    def test_update_columns_match_model_minus_id_and_fk(self):
        from app.models import ProductVariant

        assert set(ProductVariantUpdate.model_fields) == (
            set(ProductVariant.__table__.columns.keys()) - {"id", "product_id"}
        )

    def test_model_numeric_columns_are_ten_two(self):
        from app.models import ProductVariant

        table = ProductVariant.__table__
        for name in ("diameter", "nominal_diameter", "wall_thickness"):
            column = table.c[name]
            assert column.type.precision == NUMERIC_MAX.as_tuple().exponent * -1 + 8
            assert column.type.scale == NUMERIC_SCALE

    def test_model_size_text_length_matches(self):
        from app.models import ProductVariant

        assert ProductVariant.__table__.c.size_text.type.length == MAX_SIZE_TEXT_LENGTH

    def test_adr006_constraint_present_in_model(self):
        from app.models import ProductVariant

        names = {
            c.name
            for c in ProductVariant.__table__.constraints
            if type(c).__name__ == "UniqueConstraint"
        }
        assert "uq_product_variants_product_id_size_text" in names