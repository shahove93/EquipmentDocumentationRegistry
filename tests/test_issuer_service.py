import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.api.issuers.schemas import IssuerCreate, IssuerUpdate
from app.models.issuer import Issuer
from app.services.issuer_service import (
    UNIQUE_CONSTRAINT,
    IssuerAlreadyExistsError,
    IssuerService,
    IssuerServiceError,
)

NAME_A = "Федеральный центр сертификации"
NAME_B = "TÜV SÜD Product Services"
NAME_C = "Росаккредитация"


@pytest.fixture
def make_issuer(db):
    def _make(name: str = NAME_A) -> Issuer:
        return IssuerService.create(db, IssuerCreate(name=name))

    return _make


class TestCreate:
    def test_creates_and_persists(self, db, make_issuer):
        issuer = make_issuer()
        assert isinstance(issuer, Issuer)
        assert issuer.id is not None
        assert issuer.name == NAME_A

    def test_row_exists_in_database(self, db, make_issuer):
        issuer = make_issuer()
        db.expire_all()
        assert db.get(Issuer, issuer.id).name == NAME_A

    def test_only_expected_column_written(self, db, make_issuer):
        issuer = make_issuer()
        row = db.execute(
            text("SELECT * FROM issuers WHERE id=:i"), {"i": issuer.id}
        ).mappings().one()
        assert set(row) == {"id", "name"}

    def test_whitespace_stripped_before_persist(self, db, make_issuer):
        issuer = make_issuer(f"  {NAME_A}  ")
        assert issuer.name == NAME_A
        db.expire_all()
        assert db.get(Issuer, issuer.id).name == NAME_A

    def test_russian_name_persisted(self, db, make_issuer):
        issuer = make_issuer(NAME_C)
        db.expire_all()
        assert db.get(Issuer, issuer.id).name == NAME_C

    def test_latin_name_persisted(self, db, make_issuer):
        issuer = make_issuer(NAME_B)
        db.expire_all()
        assert db.get(Issuer, issuer.id).name == NAME_B

    def test_max_length_persisted(self, db, make_issuer):
        name = "Я" * 255
        issuer = make_issuer(name)
        db.expire_all()
        assert db.get(Issuer, issuer.id).name == name

    def test_commit_once(self, db, make_issuer, monkeypatch):
        calls = []
        original = db.commit
        monkeypatch.setattr(
            db, "commit", lambda: (calls.append(1), original())[1]
        )
        make_issuer()
        assert len(calls) == 1

    def test_returns_refreshed_object(self, db, make_issuer):
        issuer = make_issuer()
        assert issuer._sa_instance_state.expired is False
        assert issuer._sa_instance_state.identity is not None

    def test_ids_increase(self, db, make_issuer):
        first = make_issuer(NAME_A)
        second = make_issuer(NAME_B)
        assert second.id > first.id

    def test_create_does_not_touch_manufacturers(self, db, make_issuer):
        from app.models.manufacturer import Manufacturer

        make_issuer()
        assert db.scalar(select(func.count()).select_from(Manufacturer)) == 0


class TestCreateDuplicate:
    def test_duplicate_name_rejected(self, db, make_issuer):
        make_issuer()
        with pytest.raises(IssuerAlreadyExistsError):
            make_issuer()

    def test_error_carries_conflicting_name(self, db, make_issuer):
        make_issuer()
        with pytest.raises(IssuerAlreadyExistsError) as info:
            make_issuer()
        assert info.value.name == NAME_A
        assert NAME_A in str(info.value)

    def test_error_is_service_error(self, db, make_issuer):
        make_issuer()
        with pytest.raises(IssuerServiceError):
            make_issuer()

    def test_duplicate_not_persisted(self, db, make_issuer):
        make_issuer()
        with pytest.raises(IssuerAlreadyExistsError):
            make_issuer()
        assert db.scalar(select(func.count()).select_from(Issuer)) == 1

    def test_whitespace_variant_is_the_same_key(self, db, make_issuer):
        # schema strips before persisting, so this is the same logical name
        make_issuer()
        with pytest.raises(IssuerAlreadyExistsError):
            make_issuer(f"  {NAME_A}  ")

    def test_rollback_happened_once(self, db, make_issuer, monkeypatch):
        make_issuer()
        calls = []
        monkeypatch.setattr(db, "rollback", lambda: calls.append(1))
        with pytest.raises(IssuerAlreadyExistsError):
            make_issuer()
        assert len(calls) == 1

    def test_session_usable_after_duplicate(self, db, make_issuer):
        make_issuer()
        with pytest.raises(IssuerAlreadyExistsError):
            make_issuer()
        assert not db.in_transaction()
        assert make_issuer(NAME_C).id is not None

    def test_no_pending_changes_after_duplicate(self, db, make_issuer):
        make_issuer()
        with pytest.raises(IssuerAlreadyExistsError):
            make_issuer()
        assert len(db.new) == 0
        assert len(db.dirty) == 0

    def test_distinct_names_allowed(self, db, make_issuer):
        for name in (NAME_A, NAME_B, NAME_C):
            make_issuer(name)
        assert db.scalar(select(func.count()).select_from(Issuer)) == 3


class TestCreateCaseSensitivity:
    """Documented current behaviour: C.UTF-8 compares case-sensitively."""

    def test_different_case_allowed(self, db, make_issuer):
        make_issuer("Росаккредитация")
        make_issuer("РОСАККРЕДИТАЦИЯ")
        assert db.scalar(select(func.count()).select_from(Issuer)) == 2

    def test_same_name_same_case_rejected(self, db, make_issuer):
        make_issuer("Росаккредитация")
        with pytest.raises(IssuerAlreadyExistsError):
            make_issuer("Росаккредитация")

    def test_case_is_preserved(self, db, make_issuer):
        issuer = make_issuer("РОСАККРЕДИТАЦИЯ")
        db.expire_all()
        assert db.get(Issuer, issuer.id).name == "РОСАККРЕДИТАЦИЯ"

    def test_latin_case_treated_the_same_way(self, db, make_issuer):
        make_issuer("Manual")
        assert make_issuer("manual").name == "manual"
        with pytest.raises(IssuerAlreadyExistsError):
            make_issuer("manual")

    def test_database_collation_is_case_sensitive(self, db):
        assert db.scalar(text("SELECT 'a' = 'A'")) is False
        assert db.scalar(text("SELECT 'Паспорт' = 'ПАСПОРТ'")) is False


class TestGetById:
    def test_returns_existing(self, db, make_issuer):
        created = make_issuer()
        found = IssuerService.get_by_id(db, created.id)
        assert found is not None
        assert found.id == created.id
        assert found.name == NAME_A

    def test_returns_none_when_missing(self, db):
        assert IssuerService.get_by_id(db, 999_999) is None

    def test_returns_none_after_rollback_of_uncommitted_row(self, db):
        pending = Issuer(name=NAME_A)
        db.add(pending)
        db.flush()
        row_id = pending.id
        db.rollback()
        assert IssuerService.get_by_id(db, row_id) is None

    def test_does_not_commit(self, db, make_issuer, monkeypatch):
        created = make_issuer()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        IssuerService.get_by_id(db, created.id)
        assert calls == []


class TestList:
    def test_empty_when_no_rows(self, db):
        assert IssuerService.list(db) == []

    def test_returns_all_rows(self, db, make_issuer):
        for name in (NAME_A, NAME_B, NAME_C):
            make_issuer(name)
        assert len(IssuerService.list(db)) == 3

    def test_ordered_by_ascending_id(self, db, make_issuer):
        for name in (NAME_C, NAME_A, NAME_B):
            make_issuer(name)
        listed = IssuerService.list(db)
        assert [i.name for i in listed] == [NAME_C, NAME_A, NAME_B]
        assert [i.id for i in listed] == sorted(i.id for i in listed)

    def test_order_independent_of_name(self, db, make_issuer):
        make_issuer(NAME_A)
        make_issuer(NAME_B)
        assert [i.name for i in IssuerService.list(db)] == [NAME_A, NAME_B]

    def test_limit(self, db, make_issuer):
        for name in (NAME_A, NAME_B, NAME_C):
            make_issuer(name)
        assert len(IssuerService.list(db, limit=2)) == 2

    def test_offset(self, db, make_issuer):
        for name in (NAME_A, NAME_B, NAME_C):
            make_issuer(name)
        assert [i.name for i in IssuerService.list(db, offset=2)] == [NAME_C]

    def test_limit_and_offset(self, db, make_issuer):
        for name in (NAME_A, NAME_B, NAME_C):
            make_issuer(name)
        page = IssuerService.list(db, limit=1, offset=1)
        assert [i.name for i in page] == [NAME_B]

    def test_offset_beyond_end(self, db, make_issuer):
        make_issuer()
        assert IssuerService.list(db, offset=100) == []

    def test_pagination_covers_every_row_exactly_once(self, db, make_issuer):
        for index in range(5):
            make_issuer(f"Организация {index}")
        seen = [
            i.id
            for offset in (0, 2, 4)
            for i in IssuerService.list(db, limit=2, offset=offset)
        ]
        assert len(seen) == len(set(seen)) == 5
        assert seen == sorted(seen)

    def test_defaults_are_fifty_and_zero(self):
        # `__defaults__` is read directly: on Python 3.14 annotations are
        # evaluated lazily inside the class body, where the `list` method
        # shadows the builtin in the `-> list[Issuer]` annotation.
        assert IssuerService.list.__defaults__ == (50, 0)

    def test_does_not_commit(self, db, make_issuer, monkeypatch):
        make_issuer()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        IssuerService.list(db)
        assert calls == []


class TestUpdate:
    def test_updates_name(self, db, make_issuer):
        created = make_issuer()
        updated = IssuerService.update(
            db, created.id, IssuerUpdate(name=NAME_B)
        )
        assert updated.name == NAME_B

    def test_change_is_persisted(self, db, make_issuer):
        created = make_issuer()
        IssuerService.update(db, created.id, IssuerUpdate(name=NAME_B))
        db.expire_all()
        assert db.get(Issuer, created.id).name == NAME_B

    def test_whitespace_stripped_on_update(self, db, make_issuer):
        created = make_issuer()
        updated = IssuerService.update(
            db, created.id, IssuerUpdate(name=f"  {NAME_B}  ")
        )
        assert updated.name == NAME_B

    def test_id_never_changes(self, db, make_issuer):
        created = make_issuer()
        updated = IssuerService.update(
            db, created.id, IssuerUpdate(name=NAME_B)
        )
        assert updated.id == created.id

    def test_changes_commit_once(self, db, make_issuer, monkeypatch):
        created = make_issuer()
        calls = []
        original = db.commit
        monkeypatch.setattr(
            db, "commit", lambda: (calls.append(1), original())[1]
        )
        IssuerService.update(db, created.id, IssuerUpdate(name=NAME_B))
        assert len(calls) == 1

    def test_rename_to_own_name_allowed(self, db, make_issuer):
        created = make_issuer()
        updated = IssuerService.update(
            db, created.id, IssuerUpdate(name=NAME_A)
        )
        assert updated.name == NAME_A

    def test_rename_frees_the_previous_name(self, db, make_issuer):
        created = make_issuer(NAME_A)
        IssuerService.update(db, created.id, IssuerUpdate(name=NAME_B))
        assert IssuerService.create(db, IssuerCreate(name=NAME_A)).id is not None

    def test_missing_returns_none(self, db):
        assert IssuerService.update(db, 999_999, IssuerUpdate(name=NAME_B)) is None

    def test_missing_with_empty_patch_returns_none(self, db):
        assert IssuerService.update(db, 999_999, IssuerUpdate()) is None

    def test_missing_does_not_commit(self, db, monkeypatch):
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        IssuerService.update(db, 999_999, IssuerUpdate(name=NAME_B))
        assert calls == []

    def test_empty_patch_returns_unchanged(self, db, make_issuer):
        created = make_issuer()
        updated = IssuerService.update(db, created.id, IssuerUpdate())
        assert updated is not None
        assert updated.name == NAME_A

    def test_empty_patch_does_not_commit(self, db, make_issuer, monkeypatch):
        created = make_issuer()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        IssuerService.update(db, created.id, IssuerUpdate())
        assert calls == []

    def test_empty_patch_leaves_row_dirty_free(self, db, make_issuer):
        created = make_issuer()
        db.expire_all()
        IssuerService.update(db, created.id, IssuerUpdate())
        assert len(db.dirty) == 0

    def test_other_rows_untouched(self, db, make_issuer):
        first = make_issuer(NAME_A)
        second = make_issuer(NAME_B)
        IssuerService.update(db, first.id, IssuerUpdate(name=NAME_C))
        assert db.get(Issuer, second.id).name == NAME_B

    def test_row_count_unchanged(self, db, make_issuer):
        make_issuer(NAME_A)
        make_issuer(NAME_B)
        IssuerService.update(db, 1, IssuerUpdate(name=NAME_C))
        assert db.scalar(select(func.count()).select_from(Issuer)) == 2

    def test_update_schema_has_only_name(self):
        assert set(IssuerUpdate.model_fields) == {"name"}


class TestUpdateDuplicate:
    def test_rename_to_existing_rejected(self, db, make_issuer):
        first = make_issuer(NAME_A)
        make_issuer(NAME_B)
        with pytest.raises(IssuerAlreadyExistsError):
            IssuerService.update(db, first.id, IssuerUpdate(name=NAME_B))

    def test_error_carries_new_name(self, db, make_issuer):
        first = make_issuer(NAME_A)
        make_issuer(NAME_B)
        with pytest.raises(IssuerAlreadyExistsError) as info:
            IssuerService.update(db, first.id, IssuerUpdate(name=NAME_B))
        assert info.value.name == NAME_B
        assert NAME_B in str(info.value)

    def test_error_is_service_error(self, db, make_issuer):
        first = make_issuer(NAME_A)
        make_issuer(NAME_B)
        with pytest.raises(IssuerServiceError):
            IssuerService.update(db, first.id, IssuerUpdate(name=NAME_B))

    def test_no_partial_save(self, db, make_issuer):
        first = make_issuer(NAME_A)
        make_issuer(NAME_B)
        with pytest.raises(IssuerAlreadyExistsError):
            IssuerService.update(db, first.id, IssuerUpdate(name=NAME_B))
        db.expire_all()
        assert db.get(Issuer, first.id).name == NAME_A

    def test_no_pending_changes_after_collision(self, db, make_issuer):
        first = make_issuer(NAME_A)
        make_issuer(NAME_B)
        with pytest.raises(IssuerAlreadyExistsError):
            IssuerService.update(db, first.id, IssuerUpdate(name=NAME_B))
        assert len(db.dirty) == 0
        assert len(db.new) == 0

    def test_session_usable_after_collision(self, db, make_issuer):
        first = make_issuer(NAME_A)
        make_issuer(NAME_B)
        with pytest.raises(IssuerAlreadyExistsError):
            IssuerService.update(db, first.id, IssuerUpdate(name=NAME_B))
        assert not db.in_transaction()
        recovered = IssuerService.update(db, first.id, IssuerUpdate(name=NAME_C))
        assert recovered.name == NAME_C

    def test_rollback_after_collision(self, db, make_issuer, monkeypatch):
        first = make_issuer(NAME_A)
        make_issuer(NAME_B)
        calls = []
        monkeypatch.setattr(db, "rollback", lambda: calls.append(1))
        with pytest.raises(IssuerAlreadyExistsError):
            IssuerService.update(db, first.id, IssuerUpdate(name=NAME_B))
        assert len(calls) == 1

    def test_collision_leaves_other_row_intact(self, db, make_issuer):
        first = make_issuer(NAME_A)
        second = make_issuer(NAME_B)
        with pytest.raises(IssuerAlreadyExistsError):
            IssuerService.update(db, first.id, IssuerUpdate(name=NAME_B))
        db.expire_all()
        assert db.get(Issuer, second.id).name == NAME_B

    def test_rejected_name_stays_with_its_original_owner(self, db, make_issuer):
        # after the rollback the renamed row still holds its old name, so that
        # name remains taken and the rejected one stays owned by the other row
        first = make_issuer(NAME_A)
        second = make_issuer(NAME_B)
        with pytest.raises(IssuerAlreadyExistsError):
            IssuerService.update(db, first.id, IssuerUpdate(name=NAME_B))
        db.expire_all()
        assert db.get(Issuer, first.id).name == NAME_A
        assert db.get(Issuer, second.id).name == NAME_B
        with pytest.raises(IssuerAlreadyExistsError):
            IssuerService.create(db, IssuerCreate(name=NAME_A))
        assert IssuerService.create(db, IssuerCreate(name=NAME_C)).id is not None


class TestErrorTranslationIsNarrow:
    """Only issuers' own unique constraint becomes the service error."""

    def test_other_unique_constraint_not_masked(self, db, make_issuer):
        # document_types.name carries its own UNIQUE constraint, so it reports
        # the same SQLSTATE 23505 under a different constraint name
        insert = text("INSERT INTO document_types (name) VALUES ('ПС')")
        db.execute(insert)
        db.commit()
        with pytest.raises(IntegrityError) as info:
            db.execute(insert)
            db.commit()
        assert not isinstance(info.value, IssuerAlreadyExistsError)
        db.rollback()

    def test_foreign_key_violation_not_masked(self, db, make_issuer):
        created = make_issuer()
        with pytest.raises(IntegrityError) as info:
            db.execute(
                text(
                    "INSERT INTO documents (number, document_type_id, issuer_id) "
                    "VALUES ('DOC-1', 999999, :i)"
                ),
                {"i": created.id},
            )
            db.commit()
        assert not isinstance(info.value, IssuerAlreadyExistsError)
        db.rollback()

    def test_foreign_key_violation_on_unknown_issuer_not_masked(self, db):
        db.execute(text("INSERT INTO document_types (name) VALUES ('ПС')"))
        db.commit()
        with pytest.raises(IntegrityError) as info:
            db.execute(
                text(
                    "INSERT INTO documents (number, document_type_id, issuer_id) "
                    "VALUES ('DOC-2', 1, 999999)"
                )
            )
            db.commit()
        assert not isinstance(info.value, IssuerAlreadyExistsError)
        db.rollback()

    def test_not_null_violation_not_masked(self, db, make_issuer):
        with pytest.raises(IntegrityError) as info:
            db.execute(text("INSERT INTO issuers (name) VALUES (NULL)"))
            db.commit()
        assert not isinstance(info.value, IssuerAlreadyExistsError)
        db.rollback()

    def test_check_constraint_violation_not_masked(self, db, make_issuer):
        # documents.verification_status is constrained but not unique
        db.execute(text("INSERT INTO document_types (name) VALUES ('ПС')"))
        db.commit()
        with pytest.raises(IntegrityError) as info:
            db.execute(
                text(
                    "INSERT INTO documents (number, document_type_id, "
                    "verification_status) VALUES ('DOC-3', 1, 'nonsense')"
                )
            )
            db.commit()
        assert not isinstance(info.value, IssuerAlreadyExistsError)
        db.rollback()

    def test_duplicate_name_is_the_translated_case(self, db, make_issuer):
        make_issuer()
        with pytest.raises(IssuerAlreadyExistsError):
            make_issuer()

    def test_detected_error_reports_expected_sqlstate(self, db, make_issuer):
        make_issuer()
        with pytest.raises(IssuerAlreadyExistsError) as info:
            make_issuer()
        cause = info.value.__cause__
        assert cause.orig.sqlstate == "23505"
        assert cause.orig.diag.constraint_name == UNIQUE_CONSTRAINT


class TestConstraintNameMatchesDatabase:
    def test_constant_matches_catalog(self, db):
        actual = db.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'issuers'::regclass AND contype = 'u'"
            )
        ).scalar_one()
        assert actual == UNIQUE_CONSTRAINT

    def test_constraint_is_on_name(self, db):
        definition = db.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = 'issuers'::regclass AND contype = 'u'"
            )
        ).scalar_one()
        assert definition == "UNIQUE (name)"

    def test_lookup_is_read_only(self, db, make_issuer):
        make_issuer()
        before = db.scalar(text("SELECT count(*) FROM issuers"))
        db.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'issuers'::regclass AND contype = 'u'"
            )
        ).scalar_one()
        assert db.scalar(text("SELECT count(*) FROM issuers")) == before == 1


class TestIssuerStaysSeparateFromManufacturer:
    def test_different_tables(self):
        from app.models.manufacturer import Manufacturer

        assert Issuer.__tablename__ == "issuers"
        assert Issuer.__tablename__ != Manufacturer.__tablename__

    def test_issuer_has_no_manufacturer_reference(self):
        assert "manufacturer_id" not in Issuer.__table__.columns

    def test_creating_an_issuer_creates_no_manufacturer(self, db, make_issuer):
        from app.models.manufacturer import Manufacturer

        make_issuer(NAME_A)
        make_issuer(NAME_B)
        assert db.scalar(select(func.count()).select_from(Manufacturer)) == 0

    def test_same_name_allowed_in_both_references(self, db, make_issuer):
        # an organisation may legitimately be both a manufacturer and an issuer
        from app.models.manufacturer import Manufacturer

        db.execute(text("INSERT INTO manufacturers (name) VALUES (:n)"), {"n": NAME_A})
        db.commit()
        make_issuer(NAME_A)
        assert db.scalar(
            select(func.count()).select_from(Manufacturer).where(
                Manufacturer.name == NAME_A
            )
        ) == 1
        assert db.scalar(
            select(func.count()).select_from(Issuer).where(Issuer.name == NAME_A)
        ) == 1


class TestErrorClassification:
    """Exercise the classifier itself with errors raised by the real database.

    The raw-SQL tests above prove the constraint exists, but they bypass the
    service, so they would still pass if `_is_name_unique_violation` ignored
    the constraint name. These tests feed it genuine IntegrityErrors and pin the
    distinction that makes the check load-bearing.
    """

    @staticmethod
    def _rejected(db, statement, params=None):
        """Run a statement that violates a constraint and return the error."""
        try:
            db.execute(text(statement), params or {})
            db.commit()
        except IntegrityError as error:
            db.rollback()
            return error
        db.rollback()
        raise AssertionError(f"statement did not violate a constraint: {statement}")

    def test_own_violation_is_recognised(self, db, make_issuer):
        from app.services.issuer_service import _is_name_unique_violation

        make_issuer()
        db.add(Issuer(name=NAME_A))
        with pytest.raises(IntegrityError) as info:
            db.commit()
        db.rollback()
        assert info.value.orig.sqlstate == "23505"
        assert info.value.orig.diag.constraint_name == UNIQUE_CONSTRAINT
        assert _is_name_unique_violation(info.value) is True

    def test_other_unique_violation_is_rejected(self, db):
        from app.services.issuer_service import _is_name_unique_violation

        statement = "INSERT INTO document_types (name) VALUES ('ПС')"
        db.execute(text(statement))
        db.commit()
        error = self._rejected(db, statement)
        assert error.orig.sqlstate == "23505"
        assert error.orig.diag.constraint_name != UNIQUE_CONSTRAINT
        assert _is_name_unique_violation(error) is False

    def test_constraint_name_check_is_load_bearing(self, db):
        # the other unique violation shares the SQLSTATE, so rejecting it is
        # only possible because the constraint name is compared as well
        from app.services.issuer_service import _is_name_unique_violation

        statement = "INSERT INTO document_types (name) VALUES ('ПС')"
        db.execute(text(statement))
        db.commit()
        error = self._rejected(db, statement)
        sqlstate_only = getattr(error.orig, "sqlstate", None) == "23505"
        assert sqlstate_only is True
        assert _is_name_unique_violation(error) is False

    def test_not_null_violation_is_rejected(self, db):
        from app.services.issuer_service import _is_name_unique_violation

        error = self._rejected(db, "INSERT INTO issuers (name) VALUES (NULL)")
        assert error.orig.sqlstate != "23505"
        assert _is_name_unique_violation(error) is False

    def test_foreign_key_violation_is_rejected(self, db):
        from app.services.issuer_service import _is_name_unique_violation

        db.execute(text("INSERT INTO document_types (name) VALUES ('ПС')"))
        db.commit()
        error = self._rejected(db, 
            "INSERT INTO documents (number, document_type_id, issuer_id) "
            "VALUES ('DOC-9', 1, 999999)"
        )
        assert _is_name_unique_violation(error) is False


class TestServiceContract:
    def test_public_methods_present(self):
        for name in ("create", "get_by_id", "list", "update"):
            assert callable(getattr(IssuerService, name))

    def test_no_delete_method(self):
        assert not hasattr(IssuerService, "delete")

    def test_exception_hierarchy(self):
        assert issubclass(IssuerAlreadyExistsError, IssuerServiceError)
        assert issubclass(IssuerServiceError, Exception)

    def test_no_fastapi_dependency_in_service_module(self):
        import app.services.issuer_service as module

        with open(module.__file__, encoding="utf-8") as handle:
            assert "fastapi" not in handle.read().lower()