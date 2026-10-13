from datetime import date

import pytest
from pydantic import ValidationError

from app.api.documents.schemas import (
    MAX_NUMBER_LENGTH,
    DocumentCreate,
    DocumentListOut,
    DocumentOut,
    DocumentUpdate,
)

MINIMAL = {"document_type_id": 1, "number": "ПС-001"}


def create(**overrides):
    return DocumentCreate(**{**MINIMAL, **overrides})


class TestCreateValid:
    def test_minimal_request(self):
        document = create()
        assert document.document_type_id == 1
        assert document.number == "ПС-001"

    def test_full_request(self):
        document = create(
            issue_date=date(2026, 1, 15),
            valid_from=date(2026, 2, 1),
            valid_to=date(2028, 1, 31),
            issuer_id=3,
            notes="Протокол испытаний, лаборатория 17",
        )
        assert document.issue_date == date(2026, 1, 15)
        assert document.valid_from == date(2026, 2, 1)
        assert document.valid_to == date(2028, 1, 31)
        assert document.issuer_id == 3
        assert document.notes == "Протокол испытаний, лаборатория 17"

    def test_dates_parsed_from_iso_strings(self):
        document = create(issue_date="2026-01-15", valid_from="2026-02-01")
        assert document.issue_date == date(2026, 1, 15)
        assert document.valid_from == date(2026, 2, 1)

    def test_optional_fields_default_to_none(self):
        document = create()
        assert document.issue_date is None
        assert document.valid_from is None
        assert document.valid_to is None
        assert document.issuer_id is None
        assert document.notes is None

    def test_only_expected_fields(self):
        assert set(DocumentCreate.model_fields) == {
            "document_type_id",
            "number",
            "issue_date",
            "valid_from",
            "valid_to",
            "issuer_id",
            "notes",
        }

    def test_has_no_id_field(self):
        assert "id" not in DocumentCreate.model_fields

    def test_has_no_verification_status_field(self):
        # the column is NOT NULL with server_default 'pending'
        assert "verification_status" not in DocumentCreate.model_fields

    def test_has_no_link_fields(self):
        assert "product_ids" not in DocumentCreate.model_fields
        assert "variant_ids" not in DocumentCreate.model_fields
        assert "batch_ids" not in DocumentCreate.model_fields

    def test_existence_not_checked(self):
        # a service/DB concern, not a schema concern
        assert create(document_type_id=987654).document_type_id == 987654
        assert create(issuer_id=987654).issuer_id == 987654

    def test_notes_accepts_long_text(self):
        # documents.notes is a TEXT column: no length limit is imposed
        notes = "а" * 10_000
        assert create(notes=notes).notes == notes


class TestCreateRequiredFields:
    def test_missing_document_type_id_rejected(self):
        with pytest.raises(ValidationError):
            DocumentCreate(number="ПС-001")

    def test_missing_number_rejected(self):
        with pytest.raises(ValidationError):
            DocumentCreate(document_type_id=1)

    def test_empty_payload_rejected(self):
        with pytest.raises(ValidationError):
            DocumentCreate()

    def test_required_fields_are_required(self):
        assert DocumentCreate.model_fields["document_type_id"].is_required()
        assert DocumentCreate.model_fields["number"].is_required()

    def test_explicit_null_document_type_id_rejected(self):
        with pytest.raises(ValidationError):
            DocumentCreate(document_type_id=None, number="ПС-001")

    def test_explicit_null_number_rejected(self):
        with pytest.raises(ValidationError):
            DocumentCreate(document_type_id=1, number=None)

    def test_missing_field_names_are_reported(self):
        with pytest.raises(ValidationError) as info:
            DocumentCreate()
        missing = {error["loc"] for error in info.value.errors()}
        assert ("document_type_id",) in missing
        assert ("number",) in missing


class TestCreateForeignKeyIds:
    @pytest.mark.parametrize("value", [1, 2, 999999])
    def test_positive_document_type_id_accepted(self, value):
        assert create(document_type_id=value).document_type_id == value

    @pytest.mark.parametrize("value", [0, -1, -999])
    def test_non_positive_document_type_id_rejected(self, value):
        with pytest.raises(ValidationError):
            create(document_type_id=value)

    @pytest.mark.parametrize("value", [1, 2, 999999])
    def test_positive_issuer_id_accepted(self, value):
        assert create(issuer_id=value).issuer_id == value

    @pytest.mark.parametrize("value", [0, -1, -999])
    def test_non_positive_issuer_id_rejected(self, value):
        with pytest.raises(ValidationError):
            create(issuer_id=value)

    @pytest.mark.parametrize("value", [True, False])
    def test_boolean_ids_rejected(self, value):
        # bool is a subclass of int; without the guard True would store as id=1
        with pytest.raises(ValidationError):
            create(document_type_id=value)
        with pytest.raises(ValidationError):
            create(issuer_id=value)

    @pytest.mark.parametrize("value", [1.5, 2.9])
    def test_fractional_ids_rejected(self, value):
        with pytest.raises(ValidationError):
            create(document_type_id=value)
        with pytest.raises(ValidationError):
            create(issuer_id=value)

    @pytest.mark.parametrize("value", [None, 1.5])
    def test_non_integer_ids_rejected(self, value):
        with pytest.raises(ValidationError):
            create(document_type_id=value)

    def test_whole_float_id_coerced(self):
        # lax coercion is kept on purpose: JSON clients legitimately send 1.0
        assert create(document_type_id=1.0).document_type_id == 1

    def test_numeric_string_id_coerced(self):
        assert create(document_type_id="1").document_type_id == 1

    def test_issuer_id_is_optional(self):
        assert create().issuer_id is None


class TestCreateNumber:
    def test_surrounding_whitespace_stripped(self):
        assert create(number="  ПС-001  ").number == "ПС-001"

    def test_inner_whitespace_preserved(self):
        assert create(number="  ПС  001  ").number == "ПС  001"

    def test_case_is_not_changed(self):
        assert create(number="пс-001").number == "пс-001"

    def test_latin_number_accepted(self):
        assert create(number="CERT-2026/0142").number == "CERT-2026/0142"

    def test_empty_number_rejected(self):
        with pytest.raises(ValidationError):
            create(number="")

    @pytest.mark.parametrize("value", ["   ", "\t", "\n", " \t\n "])
    def test_blank_number_rejected(self, value):
        with pytest.raises(ValidationError):
            create(number=value)

    def test_max_length_accepted(self):
        number = "Я" * MAX_NUMBER_LENGTH
        assert create(number=number).number == number

    def test_over_max_length_rejected(self):
        with pytest.raises(ValidationError):
            create(number="Я" * (MAX_NUMBER_LENGTH + 1))

    def test_length_is_measured_after_strip(self):
        padded = f"  {'Я' * MAX_NUMBER_LENGTH}  "
        assert create(number=padded).number == "Я" * MAX_NUMBER_LENGTH

    def test_padded_over_max_length_rejected(self):
        padded = f"  {'Я' * (MAX_NUMBER_LENGTH + 1)}  "
        with pytest.raises(ValidationError):
            create(number=padded)

    def test_max_length_mirrors_the_column(self):
        # documents.number is VARCHAR(100) NOT NULL
        assert MAX_NUMBER_LENGTH == 100


class TestCreatePeriod:
    def test_valid_period_accepted(self):
        document = create(valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31))
        assert document.valid_from == date(2026, 1, 1)
        assert document.valid_to == date(2026, 12, 31)

    def test_equal_dates_accepted(self):
        # valid_to >= valid_from, so a single-day window is legal
        day = date(2026, 5, 5)
        assert create(valid_from=day, valid_to=day).valid_from == day

    def test_inverted_period_rejected(self):
        with pytest.raises(ValidationError):
            create(valid_from=date(2026, 12, 31), valid_to=date(2026, 1, 1))

    def test_inverted_by_one_day_rejected(self):
        with pytest.raises(ValidationError):
            create(valid_from=date(2026, 1, 2), valid_to=date(2026, 1, 1))

    def test_only_valid_from_accepted(self):
        assert create(valid_from=date(2026, 1, 1)).valid_to is None

    def test_only_valid_to_accepted(self):
        assert create(valid_to=date(2026, 1, 1)).valid_from is None

    def test_only_issue_date_accepted(self):
        assert create(issue_date=date(2026, 1, 1)).valid_from is None

    def test_no_dates_at_all_accepted(self):
        document = create()
        assert document.valid_from is None and document.valid_to is None

    def test_issue_date_is_outside_the_period_check(self):
        # an issue date after the window is a data question, not a schema error
        document = create(
            issue_date=date(2027, 1, 1),
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
        )
        assert document.issue_date == date(2027, 1, 1)

    def test_period_checked_from_iso_strings(self):
        with pytest.raises(ValidationError):
            create(valid_from="2026-12-31", valid_to="2026-01-01")


class TestCreateDateParsing:
    @pytest.mark.parametrize("value", ["не дата", "2026-13-01", "2026-02-30", "01.01.2026"])
    def test_invalid_date_rejected(self, value):
        with pytest.raises(ValidationError):
            create(issue_date=value)

    def test_invalid_valid_from_rejected(self):
        with pytest.raises(ValidationError):
            create(valid_from="вчера")

    def test_explicit_null_dates_accepted(self):
        document = create(issue_date=None, valid_from=None, valid_to=None)
        assert document.issue_date is None
        assert document.valid_from is None
        assert document.valid_to is None


class TestCreateForbiddenInput:
    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError):
            create(unknown_field="x")

    def test_verification_status_rejected(self):
        with pytest.raises(ValidationError):
            create(verification_status="verified")

    def test_id_rejected(self):
        # the identifier is assigned by the database
        with pytest.raises(ValidationError):
            create(id=1)

    def test_forbids_extra_configured(self):
        assert DocumentCreate.model_config["extra"] == "forbid"

    def test_verification_status_error_is_extra_forbidden(self):
        with pytest.raises(ValidationError) as info:
            create(verification_status="pending")
        assert info.value.errors()[0]["type"] == "extra_forbidden"

    def test_dump_contains_only_known_fields(self):
        assert set(create().model_dump()) == set(DocumentCreate.model_fields)


class TestUpdateShape:
    def test_empty_patch_accepted(self):
        assert DocumentUpdate().model_dump(exclude_unset=True) == {}

    def test_no_field_is_required(self):
        assert not any(
            field.is_required() for field in DocumentUpdate.model_fields.values()
        )

    def test_only_expected_fields(self):
        assert set(DocumentUpdate.model_fields) == {
            "document_type_id",
            "number",
            "issue_date",
            "valid_from",
            "valid_to",
            "issuer_id",
            "notes",
        }

    def test_has_no_verification_status_field(self):
        assert "verification_status" not in DocumentUpdate.model_fields

    def test_single_field_change(self):
        assert DocumentUpdate(number="ПС-002").model_dump(
            exclude_unset=True
        ) == {"number": "ПС-002"}

    def test_multiple_field_change(self):
        payload = {
            "document_type_id": 7,
            "number": "ПС-003",
            "issuer_id": 2,
            "notes": "уточнено",
        }
        assert DocumentUpdate(**payload).model_dump(exclude_unset=True) == payload

    def test_changed_fields_appear_in_model_fields_set(self):
        update = DocumentUpdate(number="ПС-004", notes=None)
        assert update.model_fields_set == {"number", "notes"}

    def test_absent_field_is_not_in_model_fields_set(self):
        assert DocumentUpdate(number="ПС-005").model_fields_set == {"number"}

    def test_absent_and_explicit_null_are_different(self):
        absent = DocumentUpdate(number="ПС-006")
        cleared = DocumentUpdate(notes=None)
        assert absent.model_dump(exclude_unset=True) != cleared.model_dump(
            exclude_unset=True
        )
        assert "notes" not in absent.model_dump(exclude_unset=True)
        assert cleared.model_dump(exclude_unset=True) == {"notes": None}


class TestUpdateNotNullFields:
    @pytest.mark.parametrize("field", ["document_type_id", "number"])
    def test_explicit_null_rejected(self, field):
        with pytest.raises(ValidationError):
            DocumentUpdate(**{field: None})

    def test_number_still_validated_when_supplied(self):
        with pytest.raises(ValidationError):
            DocumentUpdate(number="   ")

    def test_number_whitespace_stripped_when_supplied(self):
        assert DocumentUpdate(number="  ПС-007  ").number == "ПС-007"

    def test_number_max_length_enforced_when_supplied(self):
        assert DocumentUpdate(number="Я" * MAX_NUMBER_LENGTH).number
        with pytest.raises(ValidationError):
            DocumentUpdate(number="Я" * (MAX_NUMBER_LENGTH + 1))

    @pytest.mark.parametrize("value", [0, -1])
    def test_non_positive_document_type_id_rejected(self, value):
        with pytest.raises(ValidationError):
            DocumentUpdate(document_type_id=value)

    @pytest.mark.parametrize("value", [0, -1])
    def test_non_positive_issuer_id_rejected(self, value):
        with pytest.raises(ValidationError):
            DocumentUpdate(issuer_id=value)

    @pytest.mark.parametrize("value", [True, False])
    def test_boolean_ids_rejected(self, value):
        with pytest.raises(ValidationError):
            DocumentUpdate(document_type_id=value)
        with pytest.raises(ValidationError):
            DocumentUpdate(issuer_id=value)

    def test_positive_ids_accepted(self):
        assert DocumentUpdate(document_type_id=5, issuer_id=6).document_type_id == 5
        assert DocumentUpdate(document_type_id=5, issuer_id=6).issuer_id == 6

    def test_dates_are_still_parsed(self):
        assert DocumentUpdate(valid_from="2026-03-01").valid_from == date(2026, 3, 1)


class TestUpdateNullableFields:
    @pytest.mark.parametrize(
        "field", ["issue_date", "valid_from", "valid_to", "issuer_id", "notes"]
    )
    def test_explicit_null_accepted(self, field):
        update = DocumentUpdate(**{field: None})
        assert update.model_dump(exclude_unset=True) == {field: None}

    def test_explicit_null_clears_several_columns(self):
        payload = {"issue_date": None, "issuer_id": None, "notes": None}
        assert DocumentUpdate(**payload).model_dump(exclude_unset=True) == payload

    def test_value_is_still_accepted(self):
        assert DocumentUpdate(notes="примечание").notes == "примечание"
        assert DocumentUpdate(issuer_id=4).issuer_id == 4


class TestUpdatePeriod:
    def test_both_dates_valid_period_accepted(self):
        update = DocumentUpdate(valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31))
        assert update.valid_to == date(2026, 12, 31)

    def test_both_dates_equal_accepted(self):
        day = date(2026, 5, 5)
        assert DocumentUpdate(valid_from=day, valid_to=day).valid_from == day

    def test_both_dates_inverted_rejected(self):
        with pytest.raises(ValidationError):
            DocumentUpdate(valid_from=date(2026, 12, 31), valid_to=date(2026, 1, 1))

    def test_only_valid_from_accepted(self):
        # the merged window depends on the stored value: the service decides
        update = DocumentUpdate(valid_from=date(2026, 12, 31))
        assert update.model_dump(exclude_unset=True) == {
            "valid_from": date(2026, 12, 31)
        }

    def test_only_valid_to_accepted(self):
        update = DocumentUpdate(valid_to=date(2020, 1, 1))
        assert update.model_dump(exclude_unset=True) == {"valid_to": date(2020, 1, 1)}

    def test_only_issue_date_accepted(self):
        assert DocumentUpdate(issue_date=date(2026, 1, 1)).valid_from is None

    def test_one_bound_cleared_is_not_checked(self):
        # clearing a bound leaves an open-ended window by definition
        update = DocumentUpdate(valid_from=None, valid_to=date(1999, 1, 1))
        assert update.model_dump(exclude_unset=True) == {
            "valid_from": None,
            "valid_to": date(1999, 1, 1),
        }

    def test_clearing_both_bounds_accepted(self):
        update = DocumentUpdate(valid_from=None, valid_to=None)
        assert update.model_dump(exclude_unset=True) == {
            "valid_from": None,
            "valid_to": None,
        }


class TestUpdateForbiddenInput:
    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError):
            DocumentUpdate(unknown_field="x")

    def test_verification_status_rejected(self):
        with pytest.raises(ValidationError):
            DocumentUpdate(verification_status="rejected")

    def test_id_rejected(self):
        with pytest.raises(ValidationError):
            DocumentUpdate(id=1)

    def test_link_fields_rejected(self):
        for field in ("product_ids", "variant_ids", "batch_ids"):
            with pytest.raises(ValidationError):
                DocumentUpdate(**{field: [1]})

    def test_file_upload_rejected(self):
        with pytest.raises(ValidationError):
            DocumentUpdate(file="passport.pdf")

    def test_forbids_extra_configured(self):
        assert DocumentUpdate.model_config["extra"] == "forbid"


class _DocumentRow:
    """Stand-in for the ORM object, carrying only the declared attributes."""

    def __init__(self, **values):
        defaults = {
            "id": 1,
            "document_type_id": 2,
            "number": "ПС-001",
            "issue_date": None,
            "valid_from": None,
            "valid_to": None,
            "issuer_id": None,
            "verification_status": "pending",
            "notes": None,
        }
        defaults.update(values)
        for key, value in defaults.items():
            setattr(self, key, value)


class TestDocumentOut:
    def test_only_expected_fields(self):
        assert set(DocumentOut.model_fields) == {
            "id",
            "document_type_id",
            "number",
            "issue_date",
            "valid_from",
            "valid_to",
            "issuer_id",
            "verification_status",
            "notes",
        }

    def test_has_no_link_or_file_fields(self):
        assert "products" not in DocumentOut.model_fields
        assert "variants" not in DocumentOut.model_fields
        assert "batches" not in DocumentOut.model_fields
        assert "files" not in DocumentOut.model_fields

    def test_from_attributes_enabled(self):
        assert DocumentOut.model_config["from_attributes"] is True

    def test_validate_from_pydantic_payload(self):
        document = DocumentOut(
            id=1,
            document_type_id=2,
            number="ПС-001",
            verification_status="pending",
        )
        assert document.number == "ПС-001"
        assert document.verification_status == "pending"

    def test_validate_from_orm_like_object(self):
        document = DocumentOut.model_validate(_DocumentRow())
        assert document.id == 1
        assert document.document_type_id == 2
        assert document.verification_status == "pending"

    def test_nullables_default_to_none(self):
        document = DocumentOut.model_validate(_DocumentRow())
        assert document.issue_date is None
        assert document.valid_from is None
        assert document.valid_to is None
        assert document.issuer_id is None
        assert document.notes is None

    def test_dates_from_orm_object(self):
        document = DocumentOut.model_validate(
            _DocumentRow(issue_date=date(2026, 1, 15), valid_from=date(2026, 2, 1))
        )
        assert document.issue_date == date(2026, 1, 15)
        assert document.valid_from == date(2026, 2, 1)

    def test_dates_serialise_as_iso_strings(self):
        document = DocumentOut.model_validate(
            _DocumentRow(valid_from=date(2026, 2, 1))
        )
        assert document.model_dump(mode="json")["valid_from"] == "2026-02-01"

    def test_all_three_verification_states_pass_through(self):
        for status in ("pending", "verified", "rejected"):
            assert (
                DocumentOut.model_validate(
                    _DocumentRow(verification_status=status)
                ).verification_status
                == status
            )

    def test_required_fields_are_required(self):
        assert DocumentOut.model_fields["id"].is_required()
        assert DocumentOut.model_fields["number"].is_required()
        assert DocumentOut.model_fields["verification_status"].is_required()

    def test_serialised_body_has_every_field(self):
        payload = DocumentOut.model_validate(
            _DocumentRow(notes="примечание", issuer_id=9)
        ).model_dump(mode="json")
        assert set(payload) == set(DocumentOut.model_fields)
        assert payload["notes"] == "примечание"
        assert payload["issuer_id"] == 9


class TestDocumentListOut:
    def test_empty_list(self):
        assert DocumentListOut([]).model_dump() == []
        assert DocumentListOut(root=[]).root == []

    def test_root_model_type(self):
        assert DocumentListOut.model_config.get("extra") is None

    def test_several_documents(self):
        rows = [
            _DocumentRow(id=1, number="ПС-001"),
            _DocumentRow(id=2, number="ПС-002"),
            _DocumentRow(id=3, number="ПС-003"),
        ]
        documents = DocumentListOut([DocumentOut.model_validate(r) for r in rows])
        assert [d.id for d in documents.root] == [1, 2, 3]
        assert [d.number for d in documents.root] == ["ПС-001", "ПС-002", "ПС-003"]

    def test_accepts_orm_objects_directly(self):
        documents = DocumentListOut([_DocumentRow(id=1), _DocumentRow(id=2)])
        assert len(documents.root) == 2

    def test_serialises_to_a_bare_json_array(self):
        payload = DocumentListOut([DocumentOut.model_validate(_DocumentRow())]).model_dump(
            mode="json"
        )
        assert isinstance(payload, list)
        assert isinstance(payload[0], dict)
        assert set(payload[0]) == set(DocumentOut.model_fields)

    def test_carries_no_envelope_fields(self):
        payload = DocumentListOut(
            [DocumentOut.model_validate(_DocumentRow())]
        ).model_dump(mode="json")
        # no total, no items/page wrapper: every existing collection endpoint
        # returns the page directly
        assert isinstance(payload, list)

    def test_items_validate_against_document_out(self):
        with pytest.raises(ValidationError):
            DocumentListOut([{"number": "ПС-001"}])

    def test_list_length_matches_input(self):
        rows = [_DocumentRow(id=index) for index in range(5)]
        documents = DocumentListOut([DocumentOut.model_validate(r) for r in rows])
        assert len(documents.root) == 5