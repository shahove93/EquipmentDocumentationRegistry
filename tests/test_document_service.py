from datetime import date

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.documents.schemas import DocumentCreate, DocumentUpdate
from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.issuer import Issuer
from app.services.document_service import (
    DEFAULT_LIMIT,
    DocumentService,
    DocumentServiceError,
    DocumentTypeNotFoundError,
    InvalidValidityPeriodError,
    IssuerNotFoundError,
    _foreign_key_constraint,
)

TYPE_A = "Паспорт"
TYPE_B = "Декларация о соответствии"
ISSUER_A = "Росаккредитация"
ISSUER_B = "Федеральный центр сертификации"

VERIFIED = "verified"
REJECTED = "rejected"
PENDING = "pending"


@pytest.fixture
def document_type(db: Session) -> DocumentType:
    row = DocumentType(name=TYPE_A)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def other_document_type(db: Session) -> DocumentType:
    row = DocumentType(name=TYPE_B)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def issuer(db: Session) -> Issuer:
    row = Issuer(name=ISSUER_A)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def other_issuer(db: Session) -> Issuer:
    row = Issuer(name=ISSUER_B)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def make_document(db: Session, document_type: DocumentType):
    def _make(
        number: str = "ПС-001",
        **overrides,
    ) -> Document:
        payload = {"document_type_id": document_type.id, "number": number}
        payload.update(overrides)
        return DocumentService.create(db, DocumentCreate(**payload))

    return _make


@pytest.fixture
def set_status(db: Session):
    """Move a document to a verification verdict straight through the ORM.

    Preparing `verified` or `rejected` is not part of this stage: there is no
    verification endpoint yet and the service deliberately exposes no way to set
    the status. Test rows live in the throwaway schema, so writing the column
    directly is safe and keeps the production API narrow.
    """

    def _set(document: Document, status: str) -> Document:
        db.execute(
            text("UPDATE documents SET verification_status=:s WHERE id=:i"),
            {"s": status, "i": document.id},
        )
        db.commit()
        db.expire_all()
        return db.get(Document, document.id)

    return _set


def row_for(db: Session, document_id: int) -> dict:
    return (
        db.execute(
            text("SELECT * FROM documents WHERE id=:i"), {"i": document_id}
        )
        .mappings()
        .one()
    )


class TestCreate:
    def test_minimal_document(self, db, document_type, make_document):
        document = make_document()
        assert isinstance(document, Document)
        assert document.id is not None
        assert document.document_type_id == document_type.id
        assert document.number == "ПС-001"

    def test_row_is_persisted(self, db, make_document):
        document = make_document()
        db.expire_all()
        stored = db.get(Document, document.id)
        assert stored is not None
        assert stored.number == "ПС-001"

    def test_document_with_all_fields(self, db, document_type, issuer, make_document):
        document = make_document(
            issue_date=date(2026, 1, 15),
            valid_from=date(2026, 2, 1),
            valid_to=date(2028, 1, 31),
            issuer_id=issuer.id,
            notes="Протокол испытаний",
        )
        db.expire_all()
        stored = db.get(Document, document.id)
        assert stored.issue_date == date(2026, 1, 15)
        assert stored.valid_from == date(2026, 2, 1)
        assert stored.valid_to == date(2028, 1, 31)
        assert stored.issuer_id == issuer.id
        assert stored.notes == "Протокол испытаний"

    def test_optional_issuer_left_null(self, db, make_document):
        document = make_document()
        assert row_for(db, document.id)["issuer_id"] is None

    def test_status_defaults_to_pending(self, db, make_document):
        document = make_document()
        assert document.verification_status == PENDING
        assert row_for(db, document.id)["verification_status"] == PENDING

    def test_status_is_not_taken_from_the_payload(self, db, make_document):
        # the schema forbids the field, so there is no way to pre-verify a document
        assert "verification_status" not in DocumentCreate.model_fields
        assert make_document().verification_status == PENDING

    def test_dates_are_stored_as_dates(self, db, make_document):
        document = make_document(valid_from=date(2026, 3, 1))
        assert row_for(db, document.id)["valid_from"] == date(2026, 3, 1)

    def test_number_is_stripped_before_persist(self, db, make_document):
        document = make_document("  ПС-002  ")
        assert document.number == "ПС-002"
        assert row_for(db, document.id)["number"] == "ПС-002"

    def test_only_expected_columns_written(self, db, make_document):
        document = make_document()
        assert set(row_for(db, document.id)) == {
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

    def test_no_file_is_attached(self, db, make_document):
        document = make_document()
        assert db.scalar(select(func.count()).select_from(text("files"))) == 0
        assert document.files == []

    def test_no_links_are_created(self, db, make_document):
        document = make_document()
        assert db.scalar(select(func.count()).select_from(text("document_products"))) == 0
        assert db.scalar(select(func.count()).select_from(text("document_variants"))) == 0
        assert db.scalar(select(func.count()).select_from(text("document_batches"))) == 0
        assert document.products == []
        assert document.variants == []
        assert document.batches == []

    def test_create_writes_no_verification_event(self, db, make_document):
        # The history table exists in the test schema since TASK-DOC-003 added
        # the ORM model, but DocumentService.create has no verification logic at
        # all: a document is born pending and nothing is recorded about that.
        #
        # Only the test schema is inspected. Asserting anything about `public`
        # would tie this test to whether the migration has been applied to the
        # working database yet, which is not a property of the service.
        in_test_schema = db.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'test_file_service' "
                "AND table_name = 'document_verification_events'"
            )
        ).scalar()
        assert in_test_schema == 1

        document = make_document()
        events = db.execute(
            text(
                "SELECT count(*) FROM document_verification_events "
                "WHERE document_id = :i"
            ),
            {"i": document.id},
        ).scalar()
        assert events == 0

    def test_repeated_documents_are_allowed(self, db, make_document):
        first = make_document("ПС-001")
        second = make_document("ПС-001")
        assert first.id != second.id
        assert db.scalar(select(func.count()).select_from(Document)) == 2


class TestCreateReferentialIntegrity:
    def test_missing_document_type_raises(self, db, make_document):
        with pytest.raises(DocumentTypeNotFoundError) as info:
            make_document(document_type_id=987654)
        assert info.value.document_type_id == 987654

    def test_missing_document_type_is_a_service_error(self, db, make_document):
        with pytest.raises(DocumentServiceError):
            make_document(document_type_id=987654)

    def test_missing_document_type_persists_nothing(self, db, make_document):
        with pytest.raises(DocumentTypeNotFoundError):
            make_document(document_type_id=987654)
        assert db.scalar(select(func.count()).select_from(Document)) == 0

    def test_missing_issuer_raises(self, db, make_document):
        with pytest.raises(IssuerNotFoundError) as info:
            make_document(issuer_id=987654)
        assert info.value.issuer_id == 987654

    def test_missing_issuer_persists_nothing(self, db, make_document):
        with pytest.raises(IssuerNotFoundError):
            make_document(issuer_id=987654)
        assert db.scalar(select(func.count()).select_from(Document)) == 0

    def test_session_is_usable_after_missing_type(self, db, make_document):
        with pytest.raises(DocumentTypeNotFoundError):
            make_document(document_type_id=987654)
        assert make_document("ПС-100").number == "ПС-100"

    def test_session_is_usable_after_missing_issuer(self, db, make_document):
        with pytest.raises(IssuerNotFoundError):
            make_document(issuer_id=987654)
        assert make_document("ПС-101").number == "ПС-101"

    def test_pre_check_failure_writes_nothing(self, db, make_document):
        # the reference is checked before the INSERT, so no flush is pending
        with pytest.raises(DocumentTypeNotFoundError):
            make_document(document_type_id=987654)
        assert len(DocumentService.list(db)) == 0

    def test_foreign_key_error_is_translated_at_commit_time(
        self, db, document_type, monkeypatch
    ):
        # the pre-check is bypassed so the INSERT itself hits the foreign key:
        # this is the race between the check and the commit, and the database
        # must still produce a domain error rather than a raw IntegrityError
        monkeypatch.setattr(
            DocumentService, "_require_document_type", staticmethod(lambda db, i: None)
        )
        with pytest.raises(DocumentTypeNotFoundError):
            DocumentService.create(
                db,
                DocumentCreate(document_type_id=987654, number="ПС-300"),
            )

    def test_translated_foreign_key_error_rolls_back(self, db, document_type, monkeypatch):
        monkeypatch.setattr(
            DocumentService, "_require_document_type", staticmethod(lambda db, i: None)
        )
        with pytest.raises(DocumentTypeNotFoundError):
            DocumentService.create(
                db,
                DocumentCreate(document_type_id=987654, number="ПС-301"),
            )
        assert not db.in_transaction()
        assert db.scalar(select(func.count()).select_from(Document)) == 0

    def test_session_usable_after_translated_foreign_key_error(
        self, db, document_type, monkeypatch
    ):
        monkeypatch.setattr(
            DocumentService, "_require_document_type", staticmethod(lambda db, i: None)
        )
        with pytest.raises(DocumentTypeNotFoundError):
            DocumentService.create(
                db,
                DocumentCreate(document_type_id=987654, number="ПС-302"),
            )
        assert DocumentService.create(
            db,
            DocumentCreate(document_type_id=document_type.id, number="ПС-303"),
        ).number == "ПС-303"

    def test_other_integrity_errors_are_not_masked(self, db, document_type):
        # a CHECK violation must not be reported as a missing reference
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO documents "
                    "(document_type_id, number, verification_status) "
                    "VALUES (:t, 'X', 'bogus')"
                ),
                {"t": document_type.id},
            )
        db.rollback()
        assert db.scalar(select(func.count()).select_from(Document)) == 0

    def test_check_violation_is_not_translated_to_a_domain_error(self, db, document_type):
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError) as info:
            db.execute(
                text(
                    "INSERT INTO documents "
                    "(document_type_id, number, verification_status) "
                    "VALUES (:t, 'Y', 'bogus')"
                ),
                {"t": document_type.id},
            )
        db.rollback()
        assert info.value.orig.diag.constraint_name == "ck_documents_verification_status"
        assert _foreign_key_constraint(info.value) is None

    def test_foreign_key_helper_ignores_other_constraints(self):
        from sqlalchemy.exc import IntegrityError

        class _Orig:
            sqlstate = "23514"  # check_violation

        error = IntegrityError("stmt", {}, Exception(_Orig()))
        assert _foreign_key_constraint(error) is None

    def test_foreign_key_helper_ignores_unique_violation(self):
        from sqlalchemy.exc import IntegrityError

        class _Orig:
            sqlstate = "23505"  # unique_violation

        error = IntegrityError("stmt", {}, Exception(_Orig()))
        assert _foreign_key_constraint(error) is None


class TestGet:
    def test_returns_existing(self, db, make_document):
        document = make_document()
        found = DocumentService.get(db, document.id)
        assert found is not None
        assert found.id == document.id
        assert found.number == "ПС-001"

    def test_returns_none_for_unknown_id(self, db):
        assert DocumentService.get(db, 999999) is None

    def test_returns_none_for_zero(self, db):
        assert DocumentService.get(db, 0) is None

    def test_does_not_modify_the_row(self, db, make_document):
        document = make_document(notes="исходное")
        before = row_for(db, document.id)
        DocumentService.get(db, document.id)
        db.expire_all()
        assert row_for(db, document.id) == before

    def test_does_not_commit(self, db, make_document, monkeypatch):
        make_document()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentService.get(db, 1)
        DocumentService.list(db)
        assert calls == []


class TestList:
    def test_empty_when_no_rows(self, db):
        assert DocumentService.list(db) == []

    def test_returns_all_rows_by_default(self, db, make_document):
        for index in range(3):
            make_document(f"ПС-{index}")
        assert len(DocumentService.list(db)) == 3

    def test_default_limit_is_fifty(self):
        assert DEFAULT_LIMIT == 50

    def test_ordered_by_ascending_id(self, db, make_document):
        created = [make_document(f"ПС-{index}") for index in range(5)]
        assert [d.id for d in DocumentService.list(db)] == [
            d.id for d in created
        ]

    def test_order_is_by_id_not_by_number(self, db, make_document):
        for name in ("Яблочный", "Абрикосовый", "Янтарный"):
            make_document(f"Док-{name}")
        listed = DocumentService.list(db)
        assert [d.id for d in listed] == sorted(d.id for d in listed)
        assert [d.number for d in listed] == [
            "Док-Яблочный",
            "Док-Абрикосовый",
            "Док-Янтарный",
        ]

    def test_limit(self, db, make_document):
        for index in range(5):
            make_document(f"ПС-{index}")
        assert len(DocumentService.list(db, limit=2)) == 2

    def test_limit_larger_than_table(self, db, make_document):
        make_document()
        assert len(DocumentService.list(db, limit=100)) == 1

    def test_offset(self, db, make_document):
        for index in range(5):
            make_document(f"ПС-{index}")
        page = DocumentService.list(db, limit=2, offset=2)
        assert [d.number for d in page] == ["ПС-2", "ПС-3"]

    def test_offset_beyond_end(self, db, make_document):
        make_document()
        assert DocumentService.list(db, offset=100) == []

    def test_pagination_covers_every_row_exactly_once(self, db, make_document):
        for index in range(5):
            make_document(f"ПС-{index}")
        seen = [
            document.id
            for offset in (0, 2, 4)
            for document in DocumentService.list(db, limit=2, offset=offset)
        ]
        assert len(seen) == len(set(seen)) == 5
        assert seen == sorted(seen)

    def test_does_not_modify_rows(self, db, make_document):
        document = make_document()
        before = row_for(db, document.id)
        DocumentService.list(db)
        db.expire_all()
        assert row_for(db, document.id) == before

    def test_returns_orm_objects(self, db, make_document):
        make_document()
        assert isinstance(DocumentService.list(db)[0], Document)


class TestUpdateNoOp:
    def test_empty_patch_returns_document(self, db, make_document):
        document = make_document()
        updated = DocumentService.update(db, document.id, DocumentUpdate())
        assert updated is not None
        assert updated.id == document.id

    def test_empty_patch_does_not_commit(self, db, make_document, monkeypatch):
        document = make_document()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentService.update(db, document.id, DocumentUpdate())
        assert calls == []

    def test_empty_patch_leaves_row_untouched(self, db, make_document):
        document = make_document()
        before = row_for(db, document.id)
        DocumentService.update(db, document.id, DocumentUpdate())
        db.expire_all()
        assert row_for(db, document.id) == before

    def test_repeating_the_same_value_does_not_commit(
        self, db, make_document, set_status, monkeypatch
    ):
        document = set_status(make_document(), VERIFIED)
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentService.update(db, document.id, DocumentUpdate(number="ПС-001"))
        assert calls == []

    def test_repeating_the_same_value_keeps_the_status(
        self, db, make_document, set_status
    ):
        document = set_status(make_document(), VERIFIED)
        updated = DocumentService.update(db, document.id, DocumentUpdate(number="ПС-001"))
        assert updated.verification_status == VERIFIED

    def test_unknown_document_returns_none(self, db):
        assert DocumentService.update(db, 999999, DocumentUpdate()) is None

    def test_unknown_document_does_not_commit(self, db, monkeypatch):
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentService.update(db, 999999, DocumentUpdate(number="ПС-999"))
        assert calls == []


class TestUpdateRequisites:
    def test_single_requisite_is_persisted(self, db, make_document):
        document = make_document()
        updated = DocumentService.update(db, document.id, DocumentUpdate(number="ПС-777"))
        assert updated.number == "ПС-777"
        db.expire_all()
        assert row_for(db, document.id)["number"] == "ПС-777"

    def test_several_fields_are_persisted(self, db, make_document):
        document = make_document()
        updated = DocumentService.update(
            db,
            document.id,
            DocumentUpdate(
                number="ПС-888",
                issue_date=date(2026, 1, 15),
                notes="уточнено",
            ),
        )
        assert updated.number == "ПС-888"
        assert updated.issue_date == date(2026, 1, 15)
        assert updated.notes == "уточнено"
        db.expire_all()
        row = row_for(db, document.id)
        assert row["number"] == "ПС-888"
        assert row["notes"] == "уточнено"

    def test_document_type_is_replaceable(self, db, make_document, other_document_type):
        document = make_document()
        updated = DocumentService.update(
            db, document.id, DocumentUpdate(document_type_id=other_document_type.id)
        )
        assert updated.document_type_id == other_document_type.id

    def test_issuer_is_replaceable(self, db, make_document, other_issuer):
        document = make_document()
        updated = DocumentService.update(
            db, document.id, DocumentUpdate(issuer_id=other_issuer.id)
        )
        assert updated.issuer_id == other_issuer.id

    def test_id_never_changes(self, db, make_document):
        document = make_document()
        updated = DocumentService.update(
            db,
            document.id,
            DocumentUpdate(number="ПС-999", issuer_id=None, valid_to=date(2026, 1, 1)),
        )
        assert updated.id == document.id

    def test_number_is_stripped_before_persist(self, db, make_document):
        document = make_document()
        DocumentService.update(db, document.id, DocumentUpdate(number="  ПС-555  "))
        db.expire_all()
        assert row_for(db, document.id)["number"] == "ПС-555"

    def test_absent_field_is_not_touched(self, db, make_document):
        document = make_document(issue_date=date(2026, 1, 15), notes="исходное")
        updated = DocumentService.update(db, document.id, DocumentUpdate(number="ПС-556"))
        assert updated.issue_date == date(2026, 1, 15)
        assert updated.notes == "исходное"

    def test_explicit_null_clears_a_nullable_column(self, db, make_document):
        document = make_document(issue_date=date(2026, 1, 15), notes="исходное")
        updated = DocumentService.update(
            db, document.id, DocumentUpdate(issue_date=None, notes=None)
        )
        assert updated.issue_date is None
        assert updated.notes is None
        db.expire_all()
        row = row_for(db, document.id)
        assert row["issue_date"] is None
        assert row["notes"] is None

    def test_absent_and_explicit_null_differ(self, db, make_document):
        document = make_document(notes="исходное")
        DocumentService.update(db, document.id, DocumentUpdate(number="ПС-557"))
        db.expire_all()
        assert db.get(Document, document.id).notes == "исходное"

        DocumentService.update(db, document.id, DocumentUpdate(notes=None))
        db.expire_all()
        assert db.get(Document, document.id).notes is None

    def test_issuer_can_be_cleared(self, db, make_document, issuer):
        document = make_document(issuer_id=issuer.id)
        updated = DocumentService.update(db, document.id, DocumentUpdate(issuer_id=None))
        assert updated.issuer_id is None


class TestUpdatePeriodMerging:
    def test_valid_from_alone_is_merged_with_stored_valid_to(self, db, make_document):
        document = make_document(valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31))
        updated = DocumentService.update(
            db, document.id, DocumentUpdate(valid_from=date(2026, 2, 1))
        )
        assert updated.valid_from == date(2026, 2, 1)
        assert updated.valid_to == date(2026, 12, 31)

    def test_valid_to_alone_is_merged_with_stored_valid_from(self, db, make_document):
        document = make_document(valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31))
        updated = DocumentService.update(
            db, document.id, DocumentUpdate(valid_to=date(2026, 11, 30))
        )
        assert updated.valid_from == date(2026, 1, 1)
        assert updated.valid_to == date(2026, 11, 30)

    def test_inverted_result_is_rejected(self, db, make_document):
        document = make_document(valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31))
        with pytest.raises(InvalidValidityPeriodError):
            DocumentService.update(db, document.id, DocumentUpdate(valid_to=date(2025, 1, 1)))

    def test_inverted_result_saves_nothing(self, db, make_document):
        document = make_document(valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31))
        before = row_for(db, document.id)
        with pytest.raises(InvalidValidityPeriodError):
            DocumentService.update(
                db,
                document.id,
                DocumentUpdate(number="ПС-600", valid_to=date(2025, 1, 1)),
            )
        db.expire_all()
        assert row_for(db, document.id) == before

    def test_rejection_does_not_commit(self, db, make_document, monkeypatch):
        document = make_document(valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31))
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        with pytest.raises(InvalidValidityPeriodError):
            DocumentService.update(db, document.id, DocumentUpdate(valid_to=date(2025, 1, 1)))
        assert calls == []

    def test_rejection_leaves_the_session_usable(self, db, make_document):
        document = make_document(valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31))
        with pytest.raises(InvalidValidityPeriodError):
            DocumentService.update(db, document.id, DocumentUpdate(valid_to=date(2025, 1, 1)))
        updated = DocumentService.update(db, document.id, DocumentUpdate(notes="ок"))
        assert updated.notes == "ок"

    def test_equal_bounds_are_accepted(self, db, make_document):
        document = make_document(valid_from=date(2026, 1, 1))
        updated = DocumentService.update(db, document.id, DocumentUpdate(valid_to=date(2026, 1, 1)))
        assert updated.valid_from == updated.valid_to == date(2026, 1, 1)

    def test_clearing_one_bound_is_always_allowed(self, db, make_document):
        document = make_document(valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31))
        updated = DocumentService.update(db, document.id, DocumentUpdate(valid_from=None))
        assert updated.valid_from is None
        assert updated.valid_to == date(2026, 12, 31)

    def test_open_ended_window_is_allowed(self, db, make_document):
        document = make_document(valid_from=date(1999, 1, 1))
        updated = DocumentService.update(db, document.id, DocumentUpdate(valid_to=date(2026, 1, 1)))
        assert updated.valid_to == date(2026, 1, 1)

    def test_schema_rejects_inverted_pair_sent_together(self, db, make_document):
        # the schema catches this before the service is reached
        with pytest.raises(Exception):
            DocumentUpdate(valid_from=date(2026, 12, 31), valid_to=date(2026, 1, 1))


class TestUpdateVerificationStatus:
    def test_verified_returns_to_pending_on_requisite_change(
        self, db, make_document, set_status
    ):
        document = set_status(make_document(), VERIFIED)
        updated = DocumentService.update(db, document.id, DocumentUpdate(number="ПС-700"))
        assert updated.verification_status == PENDING
        db.expire_all()
        assert row_for(db, document.id)["verification_status"] == PENDING

    def test_rejected_returns_to_pending_on_requisite_change(
        self, db, make_document, set_status
    ):
        document = set_status(make_document(), REJECTED)
        updated = DocumentService.update(db, document.id, DocumentUpdate(number="ПС-701"))
        assert updated.verification_status == PENDING
        db.expire_all()
        assert row_for(db, document.id)["verification_status"] == PENDING

    def test_pending_stays_pending(self, db, make_document):
        document = make_document()
        updated = DocumentService.update(db, document.id, DocumentUpdate(number="ПС-702"))
        assert updated.verification_status == PENDING
        db.expire_all()
        assert row_for(db, document.id)["verification_status"] == PENDING

    def test_verified_is_kept_when_only_notes_change(
        self, db, make_document, set_status
    ):
        document = set_status(make_document(), VERIFIED)
        updated = DocumentService.update(db, document.id, DocumentUpdate(notes="уточнение"))
        assert updated.verification_status == VERIFIED
        assert updated.notes == "уточнение"
        db.expire_all()
        assert row_for(db, document.id)["verification_status"] == VERIFIED

    def test_rejected_is_kept_when_only_notes_change(
        self, db, make_document, set_status
    ):
        document = set_status(make_document(), REJECTED)
        updated = DocumentService.update(db, document.id, DocumentUpdate(notes="уточнение"))
        assert updated.verification_status == REJECTED
        db.expire_all()
        assert row_for(db, document.id)["verification_status"] == REJECTED

    def test_clearing_notes_is_also_insignificant(
        self, db, make_document, set_status
    ):
        document = set_status(make_document(notes="исходное"), VERIFIED)
        updated = DocumentService.update(db, document.id, DocumentUpdate(notes=None))
        assert updated.verification_status == VERIFIED

    @pytest.mark.parametrize(
        "change",
        [
            {"number": "ПС-710"},
            {"issue_date": date(2026, 5, 5)},
            {"valid_from": date(2026, 5, 5)},
            {"valid_to": date(2030, 5, 5)},
        ],
    )
    def test_every_significant_requisite_resets_the_status(
        self, db, make_document, set_status, change
    ):
        document = set_status(make_document(valid_to=date(2030, 1, 1)), VERIFIED)
        updated = DocumentService.update(db, document.id, DocumentUpdate(**change))
        assert updated.verification_status == PENDING
        db.expire_all()
        assert row_for(db, document.id)["verification_status"] == PENDING

    def test_notes_change_never_resets_the_status(self, db, make_document, set_status):
        document = set_status(make_document(), REJECTED)
        updated = DocumentService.update(db, document.id, DocumentUpdate(notes="правка"))
        assert updated.verification_status == REJECTED

    def test_document_type_change_resets_the_status(
        self, db, make_document, set_status, other_document_type
    ):
        document = set_status(make_document(), VERIFIED)
        updated = DocumentService.update(
            db, document.id, DocumentUpdate(document_type_id=other_document_type.id)
        )
        assert updated.verification_status == PENDING

    def test_issuer_change_resets_the_status(
        self, db, make_document, set_status, other_issuer
    ):
        document = set_status(make_document(), VERIFIED)
        updated = DocumentService.update(
            db, document.id, DocumentUpdate(issuer_id=other_issuer.id)
        )
        assert updated.verification_status == PENDING

    def test_status_cannot_be_set_directly(self, db, make_document):
        with pytest.raises(Exception):
            DocumentUpdate(verification_status=VERIFIED)
        assert "verification_status" not in DocumentUpdate.model_fields

    def test_transition_is_recorded(self, db, make_document, set_status):
        # Task 003A made this assertion temporary: the table existed but the
        # service did not write to it. Now that the history is part of the same
        # transaction as the status change, a decided document that is edited
        # must leave exactly one `reopened` event behind.
        document = set_status(make_document(), VERIFIED)

        updated = DocumentService.update(
            db, document.id, DocumentUpdate(number="ПС-720")
        )
        assert updated.verification_status == PENDING

        db.expire_all()
        assert db.get(Document, document.id).verification_status == PENDING

        events = db.execute(
            text(
                "SELECT from_status, to_status, event_type, reason "
                "FROM document_verification_events WHERE document_id = :i"
            ),
            {"i": document.id},
        ).fetchall()
        assert len(events) == 1
        assert events[0] == (VERIFIED, PENDING, "reopened", None)


class TestUpdateReferentialIntegrity:
    def test_missing_document_type_raises(self, db, make_document):
        document = make_document()
        with pytest.raises(DocumentTypeNotFoundError) as info:
            DocumentService.update(db, document.id, DocumentUpdate(document_type_id=987654))
        assert info.value.document_type_id == 987654

    def test_missing_document_type_saves_nothing(self, db, make_document):
        document = make_document()
        before = row_for(db, document.id)
        with pytest.raises(DocumentTypeNotFoundError):
            DocumentService.update(
                db, document.id, DocumentUpdate(number="ПС-800", document_type_id=987654)
            )
        db.expire_all()
        assert row_for(db, document.id) == before

    def test_missing_issuer_raises(self, db, make_document):
        document = make_document()
        with pytest.raises(IssuerNotFoundError):
            DocumentService.update(db, document.id, DocumentUpdate(issuer_id=987654))

    def test_missing_issuer_saves_nothing(self, db, make_document):
        document = make_document()
        before = row_for(db, document.id)
        with pytest.raises(IssuerNotFoundError):
            DocumentService.update(db, document.id, DocumentUpdate(issuer_id=987654))
        db.expire_all()
        assert row_for(db, document.id) == before

    def test_session_is_usable_after_rejected_update(self, db, make_document):
        document = make_document()
        with pytest.raises(DocumentTypeNotFoundError):
            DocumentService.update(db, document.id, DocumentUpdate(document_type_id=987654))
        updated = DocumentService.update(db, document.id, DocumentUpdate(notes="ок"))
        assert updated.notes == "ок"

    def test_status_not_reset_when_the_reference_is_missing(
        self, db, make_document, set_status
    ):
        # the check runs before any mutation, so a rejected update cannot reset
        # a verdict as a side effect
        document = set_status(make_document(), VERIFIED)
        with pytest.raises(DocumentTypeNotFoundError):
            DocumentService.update(db, document.id, DocumentUpdate(document_type_id=987654))
        db.expire_all()
        assert row_for(db, document.id)["verification_status"] == VERIFIED


class TestServiceContract:
    def test_read_methods_never_commit(self, db, make_document, monkeypatch):
        make_document()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        document = DocumentService.list(db)[0]
        DocumentService.get(db, document.id)
        DocumentService.get(db, 999999)
        assert calls == []

    def test_create_commits_exactly_once(self, db, document_type, monkeypatch):
        calls = []
        original = db.commit
        monkeypatch.setattr(db, "commit", lambda: (calls.append(1), original()))
        DocumentService.create(
            db, DocumentCreate(document_type_id=document_type.id, number="ПС-900")
        )
        assert len(calls) == 1

    def test_update_commits_exactly_once(self, db, make_document, monkeypatch):
        document = make_document()
        calls = []
        original = db.commit
        monkeypatch.setattr(db, "commit", lambda: (calls.append(1), original()))
        DocumentService.update(db, document.id, DocumentUpdate(number="ПС-901"))
        assert len(calls) == 1

    def test_session_is_always_supplied_by_the_caller(self):
        import inspect

        for name in ("create", "get", "list", "update"):
            parameters = list(inspect.signature(getattr(DocumentService, name)).parameters)
            assert parameters[0] == "db"

    def test_errors_share_a_common_base(self):
        for error in (
            DocumentTypeNotFoundError,
            IssuerNotFoundError,
            InvalidValidityPeriodError,
        ):
            assert issubclass(error, DocumentServiceError)

    def test_error_messages_carry_the_identifier(self):
        assert "987654" in str(DocumentTypeNotFoundError(987654))
        assert "987654" in str(IssuerNotFoundError(987654))
        assert "2026-01-01" in str(
            InvalidValidityPeriodError(date(2026, 12, 31), date(2026, 1, 1))
        )