import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.api.document_types.schemas import (
    DocumentTypeCreate,
    DocumentTypeUpdate,
)
from app.models.document_type import DocumentType
from app.services.document_type_service import (
    UNIQUE_CONSTRAINT,
    DocumentTypeAlreadyExistsError,
    DocumentTypeService,
    DocumentTypeServiceError,
)

NAME_A = "Паспорт"
NAME_B = "Свидетельство НАКС"
NAME_C = "Декларация соответствия"


@pytest.fixture
def make_document_type(db):
    def _make(name: str = NAME_A) -> DocumentType:
        return DocumentTypeService.create(db, DocumentTypeCreate(name=name))

    return _make


class TestCreate:
    def test_creates_and_persists(self, db, make_document_type):
        created = make_document_type()
        assert isinstance(created, DocumentType)
        assert created.id is not None
        assert created.name == NAME_A

    def test_row_exists_in_database(self, db, make_document_type):
        created = make_document_type()
        db.expire_all()
        assert db.get(DocumentType, created.id).name == NAME_A

    def test_only_expected_column_written(self, db, make_document_type):
        created = make_document_type()
        row = db.execute(
            text("SELECT * FROM document_types WHERE id=:i"), {"i": created.id}
        ).mappings().one()
        assert set(row) == {"id", "name"}

    def test_whitespace_stripped_before_persist(self, db, make_document_type):
        created = make_document_type(f"  {NAME_A}  ")
        assert created.name == NAME_A
        db.expire_all()
        assert db.get(DocumentType, created.id).name == NAME_A

    def test_cyrillic_persisted(self, db, make_document_type):
        created = make_document_type(NAME_C)
        db.expire_all()
        assert db.get(DocumentType, created.id).name == NAME_C

    def test_max_length_persisted(self, db, make_document_type):
        name = "Я" * 100
        created = make_document_type(name)
        db.expire_all()
        assert db.get(DocumentType, created.id).name == name

    def test_id_assigned_by_database(self, db, make_document_type):
        first = make_document_type()
        second = make_document_type(NAME_B)
        assert second.id > first.id

    def test_commit_once(self, db, make_document_type, monkeypatch):
        calls = []
        original = db.commit
        monkeypatch.setattr(
            db, "commit", lambda: (calls.append(1), original())[1]
        )
        make_document_type()
        assert len(calls) == 1

    def test_returns_refreshed_object(self, db, make_document_type):
        created = make_document_type()
        assert created._sa_instance_state.expired is False
        assert created._sa_instance_state.identity is not None

    def test_create_schema_dumps_to_model_columns(self):
        dumped = DocumentTypeCreate(name=NAME_A).model_dump()
        assert set(dumped) == {"name"}
        assert DocumentTypeService.create.__doc__ is not None


class TestCreateDuplicate:
    def test_duplicate_name_rejected(self, db, make_document_type):
        make_document_type()
        with pytest.raises(DocumentTypeAlreadyExistsError):
            make_document_type()

    def test_error_carries_conflicting_name(self, db, make_document_type):
        make_document_type()
        with pytest.raises(DocumentTypeAlreadyExistsError) as info:
            make_document_type()
        assert info.value.name == NAME_A
        assert NAME_A in str(info.value)

    def test_error_is_service_error(self, db, make_document_type):
        make_document_type()
        with pytest.raises(DocumentTypeServiceError):
            make_document_type()

    def test_duplicate_not_persisted(self, db, make_document_type):
        make_document_type()
        with pytest.raises(DocumentTypeAlreadyExistsError):
            make_document_type()
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 1

    def test_whitespace_variant_is_the_same_key(self, db, make_document_type):
        # schema strips before persisting, so this is the same logical name
        make_document_type()
        with pytest.raises(DocumentTypeAlreadyExistsError):
            make_document_type(f"  {NAME_A}  ")

    def test_rollback_happened_once(self, db, make_document_type, monkeypatch):
        make_document_type()
        calls = []
        monkeypatch.setattr(db, "rollback", lambda: calls.append(1))
        with pytest.raises(DocumentTypeAlreadyExistsError):
            make_document_type()
        assert len(calls) == 1

    def test_session_usable_after_duplicate(self, db, make_document_type):
        make_document_type()
        with pytest.raises(DocumentTypeAlreadyExistsError):
            make_document_type()
        assert not db.in_transaction()
        assert make_document_type(NAME_C).id is not None

    def test_no_pending_changes_after_duplicate(self, db, make_document_type):
        make_document_type()
        with pytest.raises(DocumentTypeAlreadyExistsError):
            make_document_type()
        assert len(db.new) == 0
        assert len(db.dirty) == 0

    def test_distinct_names_allowed(self, db, make_document_type):
        make_document_type(NAME_A)
        make_document_type(NAME_B)
        make_document_type(NAME_C)
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 3


class TestCreateCaseSensitivity:
    """Documented current behaviour: C.UTF-8 compares case-sensitively."""

    def test_different_case_allowed(self, db, make_document_type):
        make_document_type("Паспорт")
        make_document_type("ПАСПОРТ")
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 2

    def test_same_name_same_case_rejected(self, db, make_document_type):
        make_document_type("Паспорт")
        with pytest.raises(DocumentTypeAlreadyExistsError):
            make_document_type("Паспорт")

    def test_exact_match_is_case_sensitive_only(self, db, make_document_type):
        make_document_type("паспорт")
        with pytest.raises(DocumentTypeAlreadyExistsError):
            make_document_type("паспорт")
        assert make_document_type("ПАСПОРТ").name == "ПАСПОРТ"

    def test_latin_case_treated_the_same_way(self, db, make_document_type):
        make_document_type("Manual")
        assert make_document_type("manual").name == "manual"
        with pytest.raises(DocumentTypeAlreadyExistsError):
            make_document_type("manual")

    def test_database_collation_is_case_sensitive(self, db):
        assert db.scalar(text("SELECT 'a' = 'A'")) is False
        assert db.scalar(text("SELECT 'Паспорт' = 'ПАСПОРТ'")) is False


class TestGetById:
    def test_returns_existing(self, db, make_document_type):
        created = make_document_type()
        found = DocumentTypeService.get_by_id(db, created.id)
        assert found is not None
        assert found.id == created.id
        assert found.name == NAME_A

    def test_returns_none_when_missing(self, db):
        assert DocumentTypeService.get_by_id(db, 999_999) is None

    def test_returns_none_after_rollback_of_uncommitted_row(self, db):
        # create() commits, so a rollback only discards rows that were added
        # without one; this proves the identity map was cleared too.
        pending = DocumentType(name=NAME_A)
        db.add(pending)
        db.flush()
        row_id = pending.id
        db.rollback()
        assert DocumentTypeService.get_by_id(db, row_id) is None

    def test_does_not_commit(self, db, make_document_type, monkeypatch):
        created = make_document_type()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentTypeService.get_by_id(db, created.id)
        assert calls == []


class TestList:
    def test_empty_when_no_rows(self, db):
        assert DocumentTypeService.list(db) == []

    def test_returns_all_rows(self, db, make_document_type):
        for name in (NAME_A, NAME_B, NAME_C):
            make_document_type(name)
        assert len(DocumentTypeService.list(db)) == 3

    def test_ordered_by_ascending_id(self, db, make_document_type):
        for name in (NAME_C, NAME_A, NAME_B):
            make_document_type(name)
        listed = DocumentTypeService.list(db)
        assert [d.name for d in listed] == [NAME_C, NAME_A, NAME_B]
        assert [d.id for d in listed] == sorted(d.id for d in listed)

    def test_order_independent_of_name(self, db, make_document_type):
        # alphabetical order would differ from insertion order here
        make_document_type(NAME_A)
        make_document_type(NAME_B)
        listed = DocumentTypeService.list(db)
        assert [d.name for d in listed] == [NAME_A, NAME_B]

    def test_limit(self, db, make_document_type):
        for name in (NAME_A, NAME_B, NAME_C):
            make_document_type(name)
        assert len(DocumentTypeService.list(db, limit=2)) == 2

    def test_offset(self, db, make_document_type):
        for name in (NAME_A, NAME_B, NAME_C):
            make_document_type(name)
        page = DocumentTypeService.list(db, offset=2)
        assert [d.name for d in page] == [NAME_C]

    def test_limit_and_offset(self, db, make_document_type):
        for name in (NAME_A, NAME_B, NAME_C):
            make_document_type(name)
        page = DocumentTypeService.list(db, limit=1, offset=1)
        assert [d.name for d in page] == [NAME_B]

    def test_offset_beyond_end(self, db, make_document_type):
        make_document_type()
        assert DocumentTypeService.list(db, offset=100) == []

    def test_pagination_covers_every_row_exactly_once(self, db, make_document_type):
        for index in range(5):
            make_document_type(f"Тип {index}")
        seen = [
            d.id
            for offset in (0, 2, 4)
            for d in DocumentTypeService.list(db, limit=2, offset=offset)
        ]
        assert len(seen) == len(set(seen)) == 5
        assert seen == sorted(seen)

    def test_default_limit(self):
        # `__defaults__` is read directly: on Python 3.14 annotations are
        # evaluated lazily (PEP 649) inside the class body, where the `list`
        # method shadows the builtin in the `-> list[DocumentType]` annotation.
        # That is a pre-existing project-wide quirk, not something to assert on.
        assert DocumentTypeService.list.__defaults__ == (50, 0)

    def test_does_not_commit(self, db, make_document_type, monkeypatch):
        make_document_type()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentTypeService.list(db)
        assert calls == []


class TestUpdate:
    def test_updates_name(self, db, make_document_type):
        created = make_document_type()
        updated = DocumentTypeService.update(
            db, created.id, DocumentTypeUpdate(name=NAME_B)
        )
        assert updated.name == NAME_B

    def test_change_is_persisted(self, db, make_document_type):
        created = make_document_type()
        DocumentTypeService.update(
            db, created.id, DocumentTypeUpdate(name=NAME_B)
        )
        db.expire_all()
        assert db.get(DocumentType, created.id).name == NAME_B

    def test_whitespace_stripped_on_update(self, db, make_document_type):
        created = make_document_type()
        updated = DocumentTypeService.update(
            db, created.id, DocumentTypeUpdate(name=f"  {NAME_B}  ")
        )
        assert updated.name == NAME_B

    def test_id_never_changes(self, db, make_document_type):
        created = make_document_type()
        updated = DocumentTypeService.update(
            db, created.id, DocumentTypeUpdate(name=NAME_B)
        )
        assert updated.id == created.id

    def test_changes_commit_once(self, db, make_document_type, monkeypatch):
        created = make_document_type()
        calls = []
        original = db.commit
        monkeypatch.setattr(
            db, "commit", lambda: (calls.append(1), original())[1]
        )
        DocumentTypeService.update(
            db, created.id, DocumentTypeUpdate(name=NAME_B)
        )
        assert len(calls) == 1

    def test_empty_patch_returns_unchanged(self, db, make_document_type):
        created = make_document_type()
        updated = DocumentTypeService.update(db, created.id, DocumentTypeUpdate())
        assert updated is not None
        assert updated.name == NAME_A

    def test_empty_patch_does_not_commit(self, db, make_document_type, monkeypatch):
        created = make_document_type()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentTypeService.update(db, created.id, DocumentTypeUpdate())
        assert calls == []

    def test_empty_patch_leaves_row_dirty_free(self, db, make_document_type):
        created = make_document_type()
        db.expire_all()
        DocumentTypeService.update(db, created.id, DocumentTypeUpdate())
        assert len(db.dirty) == 0

    def test_missing_returns_none(self, db):
        assert (
            DocumentTypeService.update(
                db, 999_999, DocumentTypeUpdate(name=NAME_B)
            )
            is None
        )

    def test_missing_with_empty_patch_returns_none(self, db):
        assert DocumentTypeService.update(db, 999_999, DocumentTypeUpdate()) is None

    def test_missing_does_not_commit(self, db, monkeypatch):
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentTypeService.update(db, 999_999, DocumentTypeUpdate(name=NAME_B))
        assert calls == []

    def test_rename_to_own_name_allowed(self, db, make_document_type):
        created = make_document_type()
        updated = DocumentTypeService.update(
            db, created.id, DocumentTypeUpdate(name=NAME_A)
        )
        assert updated.name == NAME_A

    def test_update_schema_has_only_name(self):
        assert set(DocumentTypeUpdate.model_fields) == {"name"}

    def test_other_rows_untouched(self, db, make_document_type):
        first = make_document_type(NAME_A)
        second = make_document_type(NAME_B)
        DocumentTypeService.update(
            db, first.id, DocumentTypeUpdate(name=NAME_C)
        )
        assert db.get(DocumentType, second.id).name == NAME_B

    def test_row_count_unchanged_by_update(self, db, make_document_type):
        make_document_type(NAME_A)
        make_document_type(NAME_B)
        DocumentTypeService.update(
            db, 1, DocumentTypeUpdate(name=NAME_C)
        )
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 2


class TestUpdateDuplicate:
    def test_rename_to_existing_rejected(self, db, make_document_type):
        first = make_document_type(NAME_A)
        make_document_type(NAME_B)
        with pytest.raises(DocumentTypeAlreadyExistsError):
            DocumentTypeService.update(
                db, first.id, DocumentTypeUpdate(name=NAME_B)
            )

    def test_error_carries_new_name(self, db, make_document_type):
        first = make_document_type(NAME_A)
        make_document_type(NAME_B)
        with pytest.raises(DocumentTypeAlreadyExistsError) as info:
            DocumentTypeService.update(
                db, first.id, DocumentTypeUpdate(name=NAME_B)
            )
        assert info.value.name == NAME_B
        assert NAME_B in str(info.value)

    def test_error_is_service_error(self, db, make_document_type):
        first = make_document_type(NAME_A)
        make_document_type(NAME_B)
        with pytest.raises(DocumentTypeServiceError):
            DocumentTypeService.update(
                db, first.id, DocumentTypeUpdate(name=NAME_B)
            )

    def test_no_partial_save(self, db, make_document_type):
        first = make_document_type(NAME_A)
        make_document_type(NAME_B)
        with pytest.raises(DocumentTypeAlreadyExistsError):
            DocumentTypeService.update(
                db, first.id, DocumentTypeUpdate(name=NAME_B)
            )
        db.expire_all()
        assert db.get(DocumentType, first.id).name == NAME_A

    def test_session_usable_after_collision(self, db, make_document_type):
        first = make_document_type(NAME_A)
        make_document_type(NAME_B)
        with pytest.raises(DocumentTypeAlreadyExistsError):
            DocumentTypeService.update(
                db, first.id, DocumentTypeUpdate(name=NAME_B)
            )
        assert not db.in_transaction()
        recovered = DocumentTypeService.update(
            db, first.id, DocumentTypeUpdate(name=NAME_C)
        )
        assert recovered.name == NAME_C

    def test_rollback_after_collision(self, db, make_document_type, monkeypatch):
        first = make_document_type(NAME_A)
        make_document_type(NAME_B)
        calls = []
        monkeypatch.setattr(db, "rollback", lambda: calls.append(1))
        with pytest.raises(DocumentTypeAlreadyExistsError):
            DocumentTypeService.update(
                db, first.id, DocumentTypeUpdate(name=NAME_B)
            )
        assert len(calls) == 1

    def test_no_pending_changes_after_collision(self, db, make_document_type):
        first = make_document_type(NAME_A)
        make_document_type(NAME_B)
        with pytest.raises(DocumentTypeAlreadyExistsError):
            DocumentTypeService.update(
                db, first.id, DocumentTypeUpdate(name=NAME_B)
            )
        assert len(db.dirty) == 0
        assert len(db.new) == 0

    def test_collision_leaves_other_row_intact(self, db, make_document_type):
        first = make_document_type(NAME_A)
        second = make_document_type(NAME_B)
        with pytest.raises(DocumentTypeAlreadyExistsError):
            DocumentTypeService.update(
                db, first.id, DocumentTypeUpdate(name=NAME_B)
            )
        db.expire_all()
        assert db.get(DocumentType, second.id).name == NAME_B


class TestErrorTranslationIsNarrow:
    """Only document_types' own unique constraint becomes the service error."""

    def test_other_unique_constraint_not_masked(self, db, make_document_type):
        # issuers.name carries its own UNIQUE constraint, so it reports the
        # same SQLSTATE 23505 under a different constraint name
        insert = text("INSERT INTO issuers (name) VALUES ('НЦС')")
        db.execute(insert)
        db.commit()
        with pytest.raises(IntegrityError) as info:
            db.execute(insert)
            db.commit()
        assert not isinstance(info.value, DocumentTypeAlreadyExistsError)
        db.rollback()

    def test_not_null_violation_not_masked(self, db, make_document_type):
        make_document_type()
        with pytest.raises(IntegrityError) as info:
            db.execute(text("INSERT INTO document_types (name) VALUES (NULL)"))
            db.commit()
        assert not isinstance(info.value, DocumentTypeAlreadyExistsError)
        db.rollback()

    def test_foreign_key_violation_not_masked(self, db, make_document_type):
        created = make_document_type()
        with pytest.raises(IntegrityError) as info:
            db.execute(
                text(
                    "INSERT INTO documents (number, document_type_id, issuer_id) "
                    "VALUES ('DOC-1', :t, 999999)"
                ),
                {"t": created.id},
            )
            db.commit()
        assert not isinstance(info.value, DocumentTypeAlreadyExistsError)
        db.rollback()

    def test_repeated_name_is_the_translated_case(self, db, make_document_type):
        make_document_type()
        with pytest.raises(DocumentTypeAlreadyExistsError):
            make_document_type()

    def test_constraint_name_constant_matches_database(self, db):
        row = db.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'document_types'::regclass AND contype = 'u'"
            )
        ).scalar_one()
        assert row == UNIQUE_CONSTRAINT

    def test_detected_error_reports_expected_sqlstate(self, db, make_document_type):
        make_document_type()
        with pytest.raises(DocumentTypeAlreadyExistsError) as info:
            make_document_type()
        cause = info.value.__cause__
        assert cause.orig.sqlstate == "23505"
        assert cause.orig.diag.constraint_name == UNIQUE_CONSTRAINT

    def test_no_fastapi_dependency_in_service_module(self):
        import app.services.document_type_service as module

        source = module.__file__
        with open(source, encoding="utf-8") as handle:
            text_body = handle.read()
        assert "fastapi" not in text_body.lower()


class TestServiceContract:
    def test_public_methods_present(self):
        for name in ("create", "get_by_id", "list", "update"):
            assert callable(getattr(DocumentTypeService, name))

    def test_no_delete_method(self):
        assert not hasattr(DocumentTypeService, "delete")

    def test_exception_hierarchy(self):
        assert issubclass(DocumentTypeAlreadyExistsError, DocumentTypeServiceError)
        assert issubclass(DocumentTypeServiceError, Exception)