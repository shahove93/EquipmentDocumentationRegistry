import pytest
from pydantic import ValidationError

from app.api.document_types.schemas import (
    MAX_NAME_LENGTH,
    DocumentTypeCreate,
    DocumentTypeRead,
    DocumentTypeUpdate,
)

CYRILLIC = "Свидетельство НАКС"


class TestCreateValid:
    def test_plain_name(self):
        assert DocumentTypeCreate(name="Паспорт").name == "Паспорт"

    def test_cyrillic_name(self):
        assert DocumentTypeCreate(name=CYRILLIC).name == CYRILLIC

    def test_name_with_digits_and_symbols(self):
        name = "Декларация соответствия ТР ТС 032/2013"
        assert DocumentTypeCreate(name=name).name == name

    def test_only_expected_field(self):
        assert set(DocumentTypeCreate.model_fields) == {"name"}

    def test_surrounding_whitespace_stripped(self):
        assert DocumentTypeCreate(name="  Паспорт  ").name == "Паспорт"

    def test_inner_whitespace_preserved(self):
        assert DocumentTypeCreate(name="  Паспорт  качества  ").name == (
            "Паспорт  качества"
        )

    def test_case_is_not_changed(self):
        # ADR-007: the reference list is user-editable, no case normalisation
        assert DocumentTypeCreate(name="ПАСПОРТ").name == "ПАСПОРТ"
        assert DocumentTypeCreate(name="паспорт").name == "паспорт"

    def test_dump_contains_name(self):
        assert DocumentTypeCreate(name="Паспорт").model_dump() == {
            "name": "Паспорт"
        }

    def test_no_id_field(self):
        assert "id" not in DocumentTypeCreate.model_fields


class TestCreateMissingName:
    def test_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeCreate()

    def test_empty_payload_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeCreate(**{})

    def test_explicit_null_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeCreate(name=None)

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeCreate(name=42)


class TestCreateBlankName:
    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeCreate(name="")

    def test_spaces_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeCreate(name="   ")

    def test_tabs_and_newlines_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeCreate(name="\t\n ")

    def test_non_breaking_space_rejected(self):
        # NBSP (U+00A0) is Unicode whitespace: str.isspace() is True for it, so
        # strip_whitespace reduces the value to "" and min_length=1 rejects it.
        nbsp = chr(0x00A0)
        assert nbsp.isspace() is True
        assert nbsp.strip() == ""
        with pytest.raises(ValidationError):
            DocumentTypeCreate(name=nbsp)

    def test_other_unicode_spaces_rejected(self):
        # U+2009 THIN SPACE and U+3000 IDEOGRAPHIC SPACE behave the same way
        for codepoint in (0x2009, 0x3000):
            char = chr(codepoint)
            assert char.strip() == ""
            with pytest.raises(ValidationError):
                DocumentTypeCreate(name=char)

    def test_zero_width_characters_are_accepted(self):
        # Documented gap, not a defect: zero-width and BOM characters are format
        # characters (Cf), so str.isspace() is False and strip() leaves them.
        # A name consisting only of them therefore survives validation.
        for codepoint in (0x200B, 0x2060, 0xFEFF):
            char = chr(codepoint)
            assert char.isspace() is False
            assert DocumentTypeCreate(name=char).name == char

    def test_whitespace_only_after_strip_rejected(self):
        # strip() happens first, so " x " would pass but "  " must not
        with pytest.raises(ValidationError):
            DocumentTypeCreate(name="  \t  ")


class TestCreateNameLength:
    def test_length_100_accepted(self):
        name = "Я" * MAX_NAME_LENGTH
        assert len(name) == 100
        assert DocumentTypeCreate(name=name).name == name

    def test_length_1_accepted(self):
        assert DocumentTypeCreate(name="Я").name == "Я"

    def test_length_101_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeCreate(name="Я" * 101)

    def test_cyrillic_length_100_accepted(self):
        name = "Д" * MAX_NAME_LENGTH
        assert DocumentTypeCreate(name=name).name == name

    def test_length_measured_after_strip(self):
        padded = "  " + "Я" * MAX_NAME_LENGTH + "  "
        assert len(DocumentTypeCreate(name=padded).name) == MAX_NAME_LENGTH

    def test_padded_over_limit_rejected(self):
        padded = "  " + "Я" * (MAX_NAME_LENGTH + 1) + "  "
        with pytest.raises(ValidationError):
            DocumentTypeCreate(name=padded)

    def test_max_length_constant(self):
        assert MAX_NAME_LENGTH == 100


class TestUpdate:
    def test_name_optional(self):
        assert DocumentTypeUpdate().name is None

    def test_new_name_accepted(self):
        assert DocumentTypeUpdate(name="Паспорт качества").name == (
            "Паспорт качества"
        )

    def test_whitespace_stripped(self):
        assert DocumentTypeUpdate(name="  Паспорт  ").name == "Паспорт"

    def test_empty_patch_dumps_to_empty_dict(self):
        assert DocumentTypeUpdate().model_dump(exclude_unset=True) == {}

    def test_exclude_unset_omits_absent_field(self):
        assert "name" not in DocumentTypeUpdate().model_dump(exclude_unset=True)

    def test_exclude_unset_contains_provided_name(self):
        assert DocumentTypeUpdate(name="Паспорт").model_dump(
            exclude_unset=True
        ) == {"name": "Паспорт"}

    def test_stripped_value_is_what_gets_dumped(self):
        assert DocumentTypeUpdate(name="  Паспорт  ").model_dump(
            exclude_unset=True
        ) == {"name": "Паспорт"}

    def test_fields_set_tracks_provided_name(self):
        assert DocumentTypeUpdate().model_fields_set == set()
        assert DocumentTypeUpdate(name="Паспорт").model_fields_set == {"name"}

    def test_explicit_null_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeUpdate(name=None)

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeUpdate(name="")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeUpdate(name="   ")

    def test_length_101_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeUpdate(name="Я" * 101)

    def test_length_100_accepted(self):
        assert len(DocumentTypeUpdate(name="Я" * 100).name) == 100

    def test_absent_and_null_are_distinguishable(self):
        # absent -> not dumped; explicit null -> rejected, never silently ignored
        assert DocumentTypeUpdate().model_dump(exclude_unset=True) == {}
        with pytest.raises(ValidationError):
            DocumentTypeUpdate(name=None)

    def test_only_expected_field(self):
        assert set(DocumentTypeUpdate.model_fields) == {"name"}


class TestRead:
    def test_from_attributes_config(self):
        assert DocumentTypeRead.model_config.get("from_attributes") is True

    def test_from_orm_object(self):
        from app.models import DocumentType

        schema = DocumentTypeRead.model_validate(DocumentType(id=3, name=CYRILLIC))
        assert schema.id == 3
        assert schema.name == CYRILLIC

    def test_from_plain_object(self):
        row = type("Row", (), {"id": 7, "name": "Паспорт"})()
        assert DocumentTypeRead.model_validate(row).id == 7

    def test_dump_round_trip(self):
        from app.models import DocumentType

        dumped = DocumentTypeRead.model_validate(
            DocumentType(id=1, name="Паспорт")
        ).model_dump()
        assert dumped == {"id": 1, "name": "Паспорт"}

    def test_only_expected_fields(self):
        assert set(DocumentTypeRead.model_fields) == {"id", "name"}

    def test_missing_id_rejected(self):
        with pytest.raises(ValidationError):
            DocumentTypeRead.model_validate(type("Row", (), {"name": "x"})())

    def test_unknown_attributes_ignored(self):
        row = type("Row", (), {"id": 1, "name": "Паспорт", "extra": 1})()
        assert "extra" not in DocumentTypeRead.model_validate(row).model_dump()

    def test_create_output_is_valid_read_input(self):
        created = DocumentTypeCreate(name=CYRILLIC)
        read = DocumentTypeRead(id=1, name=created.name)
        assert read.name == created.name


class TestSchemasMirrorModel:
    def test_read_columns_match_model(self):
        from app.models import DocumentType

        assert set(DocumentTypeRead.model_fields) == set(
            DocumentType.__table__.columns.keys()
        )

    def test_create_columns_match_model_minus_id(self):
        from app.models import DocumentType

        assert set(DocumentTypeCreate.model_fields) == (
            set(DocumentType.__table__.columns.keys()) - {"id"}
        )

    def test_model_length_matches_schema(self):
        from app.models import DocumentType

        assert DocumentType.__table__.c.name.type.length == MAX_NAME_LENGTH

    def test_model_name_is_not_nullable(self):
        from app.models import DocumentType

        assert DocumentType.__table__.c.name.nullable is False

    def test_model_name_is_unique(self):
        from app.models import DocumentType

        assert DocumentType.__table__.c.name.unique is True

    def test_model_name_defaults_are_absent(self):
        from app.models import DocumentType

        column = DocumentType.__table__.c.name
        assert column.default is None
        assert column.server_default is None