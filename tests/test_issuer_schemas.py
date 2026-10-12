import pytest
from pydantic import ValidationError

from app.api.issuers.schemas import (
    MAX_NAME_LENGTH,
    IssuerCreate,
    IssuerRead,
    IssuerUpdate,
)

RUSSIAN = "Федеральный центр сертификации"
LATIN = "TÜV SÜD Product Services GmbH"


class TestCreateValid:
    def test_plain_name(self):
        assert IssuerCreate(name="Росаккредитация").name == "Росаккредитация"

    def test_russian_name(self):
        assert IssuerCreate(name=RUSSIAN).name == RUSSIAN

    def test_latin_name(self):
        assert IssuerCreate(name=LATIN).name == LATIN

    def test_name_with_digits_and_symbols(self):
        name = "ООО «Центр сертификации №1»"
        assert IssuerCreate(name=name).name == name

    def test_surrounding_whitespace_stripped(self):
        assert IssuerCreate(name="  Росаккредитация  ").name == "Росаккредитация"

    def test_inner_whitespace_preserved(self):
        assert IssuerCreate(name="  Центр  сертификации  ").name == (
            "Центр  сертификации"
        )

    def test_case_is_not_changed(self):
        # a user-editable reference list: no case normalisation
        assert IssuerCreate(name="РОСАККРЕДИТАЦИЯ").name == "РОСАККРЕДИТАЦИЯ"
        assert IssuerCreate(name="Росаккредитация").name == "Росаккредитация"
        assert IssuerCreate(name="росаккредитация").name == "росаккредитация"

    def test_dump_contains_only_name(self):
        assert IssuerCreate(name=RUSSIAN).model_dump() == {"name": RUSSIAN}

    def test_create_has_no_id_field(self):
        assert "id" not in IssuerCreate.model_fields

    def test_create_fields(self):
        assert set(IssuerCreate.model_fields) == {"name"}


class TestCreateMissingName:
    def test_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            IssuerCreate()

    def test_empty_payload_rejected(self):
        with pytest.raises(ValidationError):
            IssuerCreate(**{})

    def test_explicit_null_rejected(self):
        with pytest.raises(ValidationError):
            IssuerCreate(name=None)

    def test_integer_rejected(self):
        with pytest.raises(ValidationError):
            IssuerCreate(name=42)

    def test_missing_name_does_not_default_to_empty_string(self):
        assert IssuerCreate.model_fields["name"].is_required()


class TestCreateBlankName:
    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            IssuerCreate(name="")

    def test_ascii_spaces_rejected(self):
        with pytest.raises(ValidationError):
            IssuerCreate(name="   ")

    def test_tabs_and_newlines_rejected(self):
        with pytest.raises(ValidationError):
            IssuerCreate(name=" \t\n ")

    def test_unicode_whitespace_rejected(self):
        # every character below is Unicode whitespace, so str.strip() removes it
        # and the value collapses to the empty string
        for codepoint in (0x00A0, 0x2009, 0x3000, 0x202F):
            with pytest.raises(ValidationError):
                IssuerCreate(name=chr(codepoint))

    def test_mixed_unicode_whitespace_rejected(self):
        with pytest.raises(ValidationError):
            IssuerCreate(name=chr(0x00A0) + chr(0x2009) + " ")

    def test_unicode_whitespace_stripped_around_real_name(self):
        padded = chr(0x00A0) + RUSSIAN + chr(0x3000)
        assert IssuerCreate(name=padded).name == RUSSIAN


class TestCreateNameLength:
    def test_length_255_accepted(self):
        name = "Я" * MAX_NAME_LENGTH
        assert len(name) == 255
        assert IssuerCreate(name=name).name == name

    def test_length_256_rejected(self):
        with pytest.raises(ValidationError):
            IssuerCreate(name="Я" * 256)

    def test_length_1_accepted(self):
        assert IssuerCreate(name="Я").name == "Я"

    def test_max_length_constant(self):
        assert MAX_NAME_LENGTH == 255

    def test_length_measured_after_strip(self):
        padded = "  " + "Я" * MAX_NAME_LENGTH + "  "
        assert len(IssuerCreate(name=padded).name) == MAX_NAME_LENGTH

    def test_padded_over_limit_rejected(self):
        padded = "  " + "Я" * (MAX_NAME_LENGTH + 1) + "  "
        with pytest.raises(ValidationError):
            IssuerCreate(name=padded)

    def test_latin_max_length_accepted(self):
        name = "A" * MAX_NAME_LENGTH
        assert IssuerCreate(name=name).name == name

    def test_length_error_is_string_too_long(self):
        with pytest.raises(ValidationError) as info:
            IssuerCreate(name="Я" * 256)
        assert info.value.errors()[0]["type"] == "string_too_long"

    def test_blank_error_is_string_too_short(self):
        with pytest.raises(ValidationError) as info:
            IssuerCreate(name="")
        assert info.value.errors()[0]["type"] == "string_too_short"


class TestUpdate:
    def test_name_optional(self):
        assert IssuerUpdate().name is None

    def test_empty_patch_dumps_to_empty_dict(self):
        assert IssuerUpdate().model_dump(exclude_unset=True) == {}

    def test_exclude_unset_omits_absent_field(self):
        assert "name" not in IssuerUpdate().model_dump(exclude_unset=True)

    def test_exclude_unset_contains_provided_name(self):
        assert IssuerUpdate(name=RUSSIAN).model_dump(exclude_unset=True) == {
            "name": RUSSIAN
        }

    def test_new_name_accepted(self):
        assert IssuerUpdate(name=LATIN).name == LATIN

    def test_whitespace_stripped(self):
        assert IssuerUpdate(name=f"  {RUSSIAN}  ").name == RUSSIAN

    def test_stripped_value_is_what_gets_dumped(self):
        assert IssuerUpdate(name=f"  {RUSSIAN}  ").model_dump(
            exclude_unset=True
        ) == {"name": RUSSIAN}

    def test_fields_set_tracks_provided_name(self):
        assert IssuerUpdate().model_fields_set == set()
        assert IssuerUpdate(name=RUSSIAN).model_fields_set == {"name"}

    def test_explicit_null_rejected(self):
        with pytest.raises(ValidationError):
            IssuerUpdate(name=None)

    def test_absent_and_null_are_distinguishable(self):
        # absent -> simply not dumped; explicit null -> rejected outright
        assert IssuerUpdate().model_dump(exclude_unset=True) == {}
        with pytest.raises(ValidationError):
            IssuerUpdate(name=None)

    def test_null_error_message_mentions_null(self):
        with pytest.raises(ValidationError) as info:
            IssuerUpdate(name=None)
        assert "null" in str(info.value.errors()[0]["msg"]).lower()

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            IssuerUpdate(name="")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            IssuerUpdate(name="   ")

    def test_length_255_accepted(self):
        assert len(IssuerUpdate(name="Я" * 255).name) == 255

    def test_length_256_rejected(self):
        with pytest.raises(ValidationError):
            IssuerUpdate(name="Я" * 256)

    def test_update_fields(self):
        assert set(IssuerUpdate.model_fields) == {"name"}

    def test_case_is_not_changed(self):
        assert IssuerUpdate(name="ПАСПОРТ").name == "ПАСПОРТ"


class TestRead:
    def test_from_attributes_config(self):
        assert IssuerRead.model_config.get("from_attributes") is True

    def test_from_orm_object(self):
        from app.models import Issuer

        schema = IssuerRead.model_validate(Issuer(id=4, name=RUSSIAN))
        assert schema.id == 4
        assert schema.name == RUSSIAN

    def test_from_plain_object(self):
        row = type("Row", (), {"id": 9, "name": LATIN})()
        schema = IssuerRead.model_validate(row)
        assert schema.id == 9
        assert schema.name == LATIN

    def test_dump_round_trip(self):
        from app.models import Issuer

        dumped = IssuerRead.model_validate(Issuer(id=1, name=RUSSIAN)).model_dump()
        assert dumped == {"id": 1, "name": RUSSIAN}

    def test_read_fields(self):
        assert set(IssuerRead.model_fields) == {"id", "name"}

    def test_no_extra_read_fields(self):
        # Issuer must stay a two-column reference table: no status, no country,
        # no separate fields borrowed from Manufacturer
        assert not set(IssuerRead.model_fields) - {"id", "name"}

    def test_id_is_required(self):
        assert IssuerRead.model_fields["id"].is_required()

    def test_name_is_required(self):
        assert IssuerRead.model_fields["name"].is_required()

    def test_missing_id_rejected(self):
        with pytest.raises(ValidationError):
            IssuerRead.model_validate(type("Row", (), {"name": "x"})())

    def test_unknown_attributes_ignored(self):
        row = type("Row", (), {"id": 1, "name": LATIN, "extra": 1})()
        assert "extra" not in IssuerRead.model_validate(row).model_dump()

    def test_create_output_is_valid_read_input(self):
        created = IssuerCreate(name=RUSSIAN)
        assert IssuerRead(id=1, name=created.name).name == created.name

    def test_name_is_not_validated_on_read(self):
        # the read model mirrors storage; it must not re-run create constraints
        assert IssuerRead(id=1, name="").name == ""


class TestSchemasMirrorModel:
    def test_read_columns_match_model(self):
        from app.models import Issuer

        assert set(IssuerRead.model_fields) == set(
            Issuer.__table__.columns.keys()
        )

    def test_create_columns_match_model_minus_id(self):
        from app.models import Issuer

        assert set(IssuerCreate.model_fields) == (
            set(Issuer.__table__.columns.keys()) - {"id"}
        )

    def test_model_length_matches_schema(self):
        from app.models import Issuer

        assert Issuer.__table__.c.name.type.length == MAX_NAME_LENGTH

    def test_model_name_is_not_nullable(self):
        from app.models import Issuer

        assert Issuer.__table__.c.name.nullable is False

    def test_model_name_is_unique(self):
        from app.models import Issuer

        assert Issuer.__table__.c.name.unique is True

    def test_model_name_has_no_default(self):
        from app.models import Issuer

        column = Issuer.__table__.c.name
        assert column.default is None
        assert column.server_default is None

    def test_issuer_is_not_merged_with_manufacturer(self):
        # separate table and separate concept: a manufacturer builds the product,
        # an issuer signed the document
        from app.models import Issuer, Manufacturer

        assert Issuer.__tablename__ != Manufacturer.__tablename__
        assert Issuer.__tablename__ == "issuers"

    def test_update_schema_has_no_id(self):
        assert "id" not in IssuerUpdate.model_fields

    def test_create_and_update_share_the_name_type(self):
        from typing import Annotated, Union, get_args, get_origin

        def constraints_of(schema):
            """Collect the StringConstraints a field enforces.

            Pydantic v2 normalises the two schemas differently: for Create the
            Annotated metadata is hoisted into FieldInfo.metadata, while for
            Update it stays inside the `NameField | None` annotation. Both
            placements describe the same rule, so both are inspected here.
            """
            field = schema.model_fields["name"]
            found = [
                item
                for item in field.metadata
                if type(item).__name__ == "StringConstraints"
            ]

            annotation = field.annotation
            origin = get_origin(annotation)
            if origin is Union:
                annotation = next(
                    arg
                    for arg in get_args(annotation)
                    if arg is not type(None)
                )
            if get_origin(annotation) is Annotated:
                found += [
                    item
                    for item in get_args(annotation)[1:]
                    if type(item).__name__ == "StringConstraints"
                ]

            assert len(found) == 1, f"{schema.__name__}: {found}"
            return found[0]

        create_constraints = constraints_of(IssuerCreate)
        update_constraints = constraints_of(IssuerUpdate)
        assert create_constraints == update_constraints
        assert create_constraints.max_length == MAX_NAME_LENGTH
        assert create_constraints.min_length == 1
        assert create_constraints.strip_whitespace is True