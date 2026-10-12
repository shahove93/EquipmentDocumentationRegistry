import pytest
from pydantic import ValidationError

from app.api.products.schemas import ProductCreate, ProductRead, ProductUpdate

VALID = {
    "name": "Труба ПЭ100 SDR11",
    "standard": "ГОСТ 58121.2-2018",
    "manufacturer_id": 1,
}


class TestProductCreateValid:
    def test_minimal_payload(self):
        schema = ProductCreate(**VALID)
        assert schema.name == "Труба ПЭ100 SDR11"
        assert schema.standard == "ГОСТ 58121.2-2018"
        assert schema.manufacturer_id == 1

    def test_optional_fields_default_to_none(self):
        schema = ProductCreate(**VALID)
        assert schema.designation is None
        assert schema.product_type is None

    def test_optional_fields_accepted(self):
        schema = ProductCreate(
            **VALID, designation="ТРУБА_ПЭ_110_SDR11", product_type="труба"
        )
        assert schema.designation == "ТРУБА_ПЭ_110_SDR11"
        assert schema.product_type == "труба"

    def test_expected_fields_only(self):
        assert set(ProductCreate.model_fields) == {
            "name",
            "standard",
            "manufacturer_id",
            "designation",
            "product_type",
        }

    def test_no_sdr_field(self):
        assert "sdr" not in ProductCreate.model_fields
        assert not hasattr(ProductCreate(name="x", standard="y", manufacturer_id=1), "sdr")

    def test_sdr_is_part_of_name(self):
        schema = ProductCreate(**{**VALID, "name": "Труба ПЭ100 SDR17"})
        assert schema.name == "Труба ПЭ100 SDR17"

    def test_whitespace_stripped_in_all_text_fields(self):
        schema = ProductCreate(
            name="  Труба  ", standard="  ГОСТ  ", designation="  арт  ",
            product_type="  труба  ", manufacturer_id=1,
        )
        assert schema.name == "Труба"
        assert schema.standard == "ГОСТ"
        assert schema.designation == "арт"
        assert schema.product_type == "труба"

    def test_inner_whitespace_preserved(self):
        schema = ProductCreate(**{**VALID, "name": "  Труба   ПЭ100  "})
        assert schema.name == "Труба   ПЭ100"

    def test_dump_contains_supplied_values(self):
        dumped = ProductCreate(**VALID).model_dump()
        assert dumped["name"] == VALID["name"]
        assert dumped["manufacturer_id"] == 1


class TestProductCreateRequiredFields:
    @pytest.mark.parametrize("field", ["name", "standard", "manufacturer_id"])
    def test_missing_required_field_rejected(self, field):
        payload = {k: v for k, v in VALID.items() if k != field}
        with pytest.raises(ValidationError):
            ProductCreate(**payload)

    def test_empty_payload_rejected(self):
        with pytest.raises(ValidationError):
            ProductCreate()

    @pytest.mark.parametrize("field", ["name", "standard"])
    @pytest.mark.parametrize("value", ["", "   ", "\t\n "])
    def test_blank_required_text_rejected(self, field, value):
        with pytest.raises(ValidationError):
            ProductCreate(**{**VALID, field: value})

    @pytest.mark.parametrize("field", ["name", "standard"])
    def test_explicit_null_required_text_rejected(self, field):
        with pytest.raises(ValidationError):
            ProductCreate(**{**VALID, field: None})

    def test_non_string_name_rejected(self):
        with pytest.raises(ValidationError):
            ProductCreate(**{**VALID, "name": 42})

    def test_missing_field_reported_in_detail(self):
        with pytest.raises(ValidationError) as info:
            ProductCreate(name="Труба", manufacturer_id=1)
        assert "standard" in [error["loc"][-1] for error in info.value.errors()]


class TestProductCreateManufacturerId:
    @pytest.mark.parametrize("value", [1, 2, 999999])
    def test_positive_accepted(self, value):
        assert ProductCreate(**{**VALID, "manufacturer_id": value}).manufacturer_id == value

    @pytest.mark.parametrize("value", [0, -1, -999])
    def test_non_positive_rejected(self, value):
        with pytest.raises(ValidationError):
            ProductCreate(**{**VALID, "manufacturer_id": value})

    @pytest.mark.parametrize("value", [None, 1.5])
    def test_non_integer_rejected(self, value):
        with pytest.raises(ValidationError):
            ProductCreate(**{**VALID, "manufacturer_id": value})

    @pytest.mark.parametrize("value", [True, False])
    def test_boolean_rejected(self, value):
        # bool is a subclass of int; without the guard True would store as id=1
        with pytest.raises(ValidationError):
            ProductCreate(**{**VALID, "manufacturer_id": value})

    @pytest.mark.parametrize("value", ["1", 1.0])
    def test_numeric_string_and_whole_float_coerced(self, value):
        # lax coercion is kept on purpose: JSON clients legitimately send 1.0
        assert ProductCreate(**{**VALID, "manufacturer_id": value}).manufacturer_id == 1

    @pytest.mark.parametrize("value", [1.5, 2.9])
    def test_fractional_float_rejected(self, value):
        with pytest.raises(ValidationError):
            ProductCreate(**{**VALID, "manufacturer_id": value})

    def test_existence_not_checked(self):
        # ADR: existence of the manufacturer is a service/DB concern
        assert ProductCreate(**{**VALID, "manufacturer_id": 987654}).manufacturer_id == 987654


class TestProductCreateBoundaries:
    def test_name_255_accepted(self):
        name = "Я" * 255
        assert ProductCreate(**{**VALID, "name": name}).name == name

    def test_name_256_rejected(self):
        with pytest.raises(ValidationError):
            ProductCreate(**{**VALID, "name": "Я" * 256})

    def test_standard_255_accepted(self):
        standard = "Я" * 255
        assert ProductCreate(**{**VALID, "standard": standard}).standard == standard

    def test_standard_256_rejected(self):
        with pytest.raises(ValidationError):
            ProductCreate(**{**VALID, "standard": "Я" * 256})

    def test_designation_255_accepted(self):
        value = "Я" * 255
        assert ProductCreate(**VALID, designation=value).designation == value

    def test_designation_256_rejected(self):
        with pytest.raises(ValidationError):
            ProductCreate(**VALID, designation="Я" * 256)

    def test_product_type_100_accepted(self):
        value = "Я" * 100
        assert ProductCreate(**VALID, product_type=value).product_type == value

    def test_product_type_101_rejected(self):
        with pytest.raises(ValidationError):
            ProductCreate(**VALID, product_type="Я" * 101)

    def test_length_measured_after_strip(self):
        schema = ProductCreate(**{**VALID, "name": "  " + "Я" * 255 + "  "})
        assert len(schema.name) == 255

    @pytest.mark.parametrize("field", ["designation", "product_type"])
    @pytest.mark.parametrize("value", ["", "   "])
    def test_blank_optional_text_rejected_when_supplied(self, field, value):
        with pytest.raises(ValidationError):
            ProductCreate(**{**VALID, field: value})

    @pytest.mark.parametrize("field", ["designation", "product_type"])
    def test_optional_text_null_accepted(self, field):
        assert getattr(ProductCreate(**{**VALID, field: None}), field) is None


class TestProductUpdateAbsentFields:
    def test_empty_body_accepted(self):
        assert ProductUpdate().model_dump(exclude_unset=True) == {}

    def test_absent_fields_are_none(self):
        schema = ProductUpdate()
        for field in ("name", "standard", "manufacturer_id", "designation", "product_type"):
            assert getattr(schema, field) is None

    def test_exclude_unset_omits_everything(self):
        assert "name" not in ProductUpdate().model_dump(exclude_unset=True)

    def test_fields_set_tracks_provided_values(self):
        assert ProductUpdate().model_fields_set == set()
        assert ProductUpdate(name="X").model_fields_set == {"name"}

    def test_partial_payload_dumps_only_that_field(self):
        assert ProductUpdate(name="X").model_dump(exclude_unset=True) == {"name": "X"}

    def test_multiple_fields_dumped(self):
        payload = {"name": "X", "standard": "Y", "manufacturer_id": 3}
        assert ProductUpdate(**payload).model_dump(exclude_unset=True) == payload

    def test_unset_field_does_not_appear_alongside_set_field(self):
        dumped = ProductUpdate(name="X").model_dump(exclude_unset=True)
        assert "standard" not in dumped


class TestProductUpdateNullHandling:
    @pytest.mark.parametrize("field", ["name", "standard", "manufacturer_id"])
    def test_explicit_null_rejected_for_not_null_columns(self, field):
        with pytest.raises(ValidationError):
            ProductUpdate(**{field: None})

    @pytest.mark.parametrize("field", ["designation", "product_type"])
    def test_explicit_null_accepted_for_nullable_columns(self, field):
        schema = ProductUpdate(**{field: None})
        assert getattr(schema, field) is None
        assert schema.model_dump(exclude_unset=True) == {field: None}

    def test_absent_and_null_are_distinguishable(self):
        absent = ProductUpdate(name="X").model_dump(exclude_unset=True)
        cleared = ProductUpdate(name="X", designation=None).model_dump(exclude_unset=True)
        assert "designation" not in absent
        assert cleared["designation"] is None

    def test_null_in_payload_does_not_blank_required_field(self):
        with pytest.raises(ValidationError):
            ProductUpdate(name="X", standard=None)


class TestProductUpdateValidation:
    @pytest.mark.parametrize("field", ["name", "standard"])
    @pytest.mark.parametrize("value", ["", "   ", "\t\n "])
    def test_blank_required_text_rejected(self, field, value):
        with pytest.raises(ValidationError):
            ProductUpdate(**{field: value})

    @pytest.mark.parametrize("field", ["designation", "product_type"])
    @pytest.mark.parametrize("value", ["", "   "])
    def test_blank_optional_text_rejected(self, field, value):
        with pytest.raises(ValidationError):
            ProductUpdate(**{field: value})

    @pytest.mark.parametrize("value", [0, -1])
    def test_non_positive_manufacturer_id_rejected(self, value):
        with pytest.raises(ValidationError):
            ProductUpdate(manufacturer_id=value)

    def test_whitespace_stripped(self):
        assert ProductUpdate(name="  X  ").model_dump(exclude_unset=True) == {"name": "X"}

    def test_name_255_accepted(self):
        assert ProductUpdate(name="Я" * 255).name == "Я" * 255

    def test_name_256_rejected(self):
        with pytest.raises(ValidationError):
            ProductUpdate(name="Я" * 256)

    def test_product_type_101_rejected(self):
        with pytest.raises(ValidationError):
            ProductUpdate(product_type="Я" * 101)

    def test_designation_255_accepted(self):
        assert ProductUpdate(designation="Я" * 255).designation == "Я" * 255


class TestProductRead:
    def test_from_attributes_config(self):
        assert ProductRead.model_config.get("from_attributes") is True

    def test_expected_fields(self):
        assert set(ProductRead.model_fields) == {
            "id",
            "name",
            "standard",
            "manufacturer_id",
            "designation",
            "product_type",
        }

    def test_from_orm_object(self):
        from app.models import Product

        product = Product(
            id=5,
            name="Труба ПЭ100 SDR11",
            standard="ГОСТ 58121.2-2018",
            manufacturer_id=2,
            designation="ТРУБА_ПЭ_110",
            product_type="труба",
        )
        schema = ProductRead.model_validate(product)
        assert schema.id == 5
        assert schema.name == "Труба ПЭ100 SDR11"
        assert schema.standard == "ГОСТ 58121.2-2018"
        assert schema.manufacturer_id == 2
        assert schema.designation == "ТРУБА_ПЭ_110"
        assert schema.product_type == "труба"

    def test_from_orm_object_with_nulls(self):
        from app.models import Product

        product = Product(
            id=6, name="Труба", standard="ТУ 22.21.29", manufacturer_id=1
        )
        schema = ProductRead.model_validate(product)
        assert schema.designation is None
        assert schema.product_type is None

    def test_from_plain_object(self):
        row = type(
            "Row",
            (),
            {
                "id": 7,
                "name": "Труба",
                "standard": "ГОСТ",
                "manufacturer_id": 3,
                "designation": None,
                "product_type": None,
            },
        )()
        assert ProductRead.model_validate(row).id == 7

    def test_dump_round_trip(self):
        from app.models import Product

        product = Product(id=1, name="Труба", standard="ГОСТ", manufacturer_id=1)
        dumped = ProductRead.model_validate(product).model_dump()
        assert dumped == {
            "id": 1,
            "name": "Труба",
            "standard": "ГОСТ",
            "manufacturer_id": 1,
            "designation": None,
            "product_type": None,
        }

    def test_unknown_orm_attributes_ignored(self):
        product = type(
            "Row",
            (),
            {
                "id": 1,
                "name": "Труба",
                "standard": "ГОСТ",
                "manufacturer_id": 1,
                "extra": "ignored",
            },
        )()
        assert "extra" not in ProductRead.model_validate(product).model_dump()

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            ProductRead.model_validate({"name": "Труба"})

    def test_create_output_matches_read_input(self):
        created = ProductCreate(**VALID)
        read = ProductRead(
            id=1,
            name=created.name,
            standard=created.standard,
            manufacturer_id=created.manufacturer_id,
        )
        assert read.name == created.name
        assert read.standard == created.standard
        assert read.manufacturer_id == created.manufacturer_id


class TestSchemasMirrorModel:
    def test_create_columns_match_model_columns(self):
        from app.models import Product

        model_columns = set(Product.__table__.columns.keys()) - {"id"}
        assert set(ProductCreate.model_fields) == model_columns

    def test_read_columns_match_model_columns(self):
        from app.models import Product

        assert set(ProductRead.model_fields) == set(Product.__table__.columns.keys())

    def test_lengths_match_model(self):
        from app.models import Product

        table = Product.__table__
        assert table.c.name.type.length == 255
        assert table.c.standard.type.length == 255
        assert table.c.designation.type.length == 255
        assert table.c.product_type.type.length == 100

    def test_schema_limits_match_model_lengths(self):
        from pydantic import TypeAdapter

        from app.api.products.schemas import (
            MAX_PRODUCT_TYPE_LENGTH,
            MAX_TEXT_LENGTH,
            RequiredText,
        )

        assert MAX_TEXT_LENGTH == 255
        assert MAX_PRODUCT_TYPE_LENGTH == 100
        with pytest.raises(ValidationError):
            TypeAdapter(RequiredText).validate_python("Я" * 256)