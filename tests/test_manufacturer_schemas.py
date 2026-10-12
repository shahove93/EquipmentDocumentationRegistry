from pydantic import ValidationError
import pytest

from app.api.manufacturers.schemas import (
    ManufacturerCreate,
    ManufacturerRead,
    ManufacturerUpdate,
)


class TestManufacturerCreate:
    def test_valid_name(self):
        schema = ManufacturerCreate(name="ООО ИММИД")
        assert schema.name == "ООО ИММИД"

    def test_only_expected_field(self):
        assert set(ManufacturerCreate.model_fields) == {"name"}

    def test_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerCreate()

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerCreate(name="")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerCreate(name="   ")

    def test_tabs_and_newlines_only_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerCreate(name="\t\n ")

    def test_surrounding_whitespace_is_stripped(self):
        schema = ManufacturerCreate(name="  ООО ИММИД  ")
        assert schema.name == "ООО ИММИД"

    def test_inner_whitespace_preserved(self):
        schema = ManufacturerCreate(name="  ООО  ИММИД  ")
        assert schema.name == "ООО  ИММИД"

    def test_length_255_accepted(self):
        name = "Я" * 255
        schema = ManufacturerCreate(name=name)
        assert schema.name == name
        assert len(schema.name) == 255

    def test_length_256_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerCreate(name="Я" * 256)

    def test_length_measured_after_strip(self):
        padded = "  " + "Я" * 255 + "  "
        schema = ManufacturerCreate(name=padded)
        assert len(schema.name) == 255

    def test_explicit_null_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerCreate(name=None)

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerCreate(name=42)

    def test_dump_contains_name(self):
        schema = ManufacturerCreate(name="ООО ИММИД")
        assert schema.model_dump() == {"name": "ООО ИММИД"}


class TestManufacturerUpdate:
    def test_name_optional(self):
        schema = ManufacturerUpdate()
        assert schema.name is None

    def test_empty_body_accepted(self):
        schema = ManufacturerUpdate(**{})
        assert schema.model_dump(exclude_unset=True) == {}

    def test_exclude_unset_empty_dict(self):
        schema = ManufacturerUpdate()
        assert schema.model_dump(exclude_unset=True) == {}

    def test_exclude_unset_contains_provided_name(self):
        schema = ManufacturerUpdate(name="ООО ИММИД")
        assert schema.model_dump(exclude_unset=True) == {"name": "ООО ИММИД"}

    def test_exclude_unset_drops_absent_field(self):
        schema = ManufacturerUpdate()
        assert "name" not in schema.model_dump(exclude_unset=True)

    def test_fields_set_tracks_provided_name(self):
        assert ManufacturerUpdate().model_fields_set == set()
        assert ManufacturerUpdate(name="ООО ИММИД").model_fields_set == {"name"}

    def test_exclude_none_cannot_silently_drop_an_intended_update(self):
        # exclude_none is not used: with this schema an explicit null is rejected
        # outright, so exclude_unset alone decides what was actually requested
        schema = ManufacturerUpdate(name="ООО ИММИД")
        assert schema.model_dump(exclude_unset=True) == {"name": "ООО ИММИД"}
        with pytest.raises(ValidationError):
            ManufacturerUpdate(name=None)

    def test_explicit_null_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerUpdate(name=None)

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerUpdate(name="")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerUpdate(name="    ")

    def test_whitespace_is_stripped(self):
        schema = ManufacturerUpdate(name="  ООО ИММИД  ")
        assert schema.name == "ООО ИММИД"

    def test_stripped_value_is_what_gets_dumped(self):
        schema = ManufacturerUpdate(name="  ООО ИММИД  ")
        assert schema.model_dump(exclude_unset=True) == {"name": "ООО ИММИД"}

    def test_length_255_accepted(self):
        name = "Я" * 255
        assert ManufacturerUpdate(name=name).name == name

    def test_length_256_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerUpdate(name="Я" * 256)


class TestManufacturerRead:
    def test_from_attributes(self):
        schema = ManufacturerRead.model_validate(
            type("Row", (), {"id": 7, "name": "ООО ИММИД"})()
        )
        assert schema.id == 7
        assert schema.name == "ООО ИММИД"

    def test_from_sqlalchemy_model(self):
        from app.models import Manufacturer

        manufacturer = Manufacturer(id=3, name="ALIAXIS")
        schema = ManufacturerRead.model_validate(manufacturer)
        assert schema.id == 3
        assert schema.name == "ALIAXIS"

    def test_only_expected_fields(self):
        assert set(ManufacturerRead.model_fields) == {"id", "name"}

    def test_dump_round_trip(self):
        schema = ManufacturerRead.model_validate(
            type("Row", (), {"id": 1, "name": "ООО ИММИД"})()
        )
        assert schema.model_dump() == {"id": 1, "name": "ООО ИММИД"}

    def test_missing_id_rejected(self):
        with pytest.raises(ValidationError):
            ManufacturerRead.model_validate(type("Row", (), {"name": "x"})())

    def test_unknown_attribute_ignored(self):
        row = type("Row", (), {"id": 1, "name": "ООО ИММИД", "extra": "ignored"})()
        schema = ManufacturerRead.model_validate(row)
        assert schema.model_dump() == {"id": 1, "name": "ООО ИММИД"}

    def test_create_output_is_valid_read_input(self):
        created = ManufacturerCreate(name="ООО ИММИД")
        read = ManufacturerRead(id=1, name=created.name)
        assert read.name == created.name


class TestSchemasAreIndependent:
    def test_update_is_not_create(self):
        assert ManufacturerUpdate is not ManufacturerCreate

    def test_read_has_no_validators_but_from_attributes(self):
        config = ManufacturerRead.model_config
        assert config.get("from_attributes") is True