import pytest
from sqlalchemy import func, select

from app.api.manufacturers.schemas import ManufacturerCreate, ManufacturerUpdate
from app.models.manufacturer import Manufacturer
from app.services.manufacturer_service import ManufacturerService


@pytest.fixture
def make_manufacturer(db):
    def _make(name: str) -> Manufacturer:
        return ManufacturerService.create(db, ManufacturerCreate(name=name))

    return _make


class TestCreate:
    def test_returns_persisted_object(self, db, make_manufacturer):
        manufacturer = make_manufacturer("ООО ИММИД")
        assert isinstance(manufacturer, Manufacturer)
        assert manufacturer.id is not None
        assert manufacturer.name == "ООО ИММИД"

    def test_row_exists_in_database(self, db, make_manufacturer):
        manufacturer = make_manufacturer("ООО ИММИД")
        stored = db.get(Manufacturer, manufacturer.id)
        assert stored is not None
        assert stored.name == "ООО ИММИД"

    def test_name_is_normalized_before_storage(self, db):
        manufacturer = ManufacturerService.create(
            db, ManufacturerCreate(name="  ООО ИММИД  ")
        )
        assert manufacturer.name == "ООО ИММИД"

    def test_ids_are_assigned_by_database(self, db, make_manufacturer):
        first = make_manufacturer("Первый")
        second = make_manufacturer("Второй")
        assert first.id != second.id
        assert second.id > first.id

    def test_count_matches_created_rows(self, db):
        ManufacturerService.create(db, ManufacturerCreate(name="Один"))
        ManufacturerService.create(db, ManufacturerCreate(name="Два"))
        total = db.scalar(select(func.count()).select_from(Manufacturer))
        assert total == 2

    def test_duplicate_names_allowed(self, db):
        first = ManufacturerService.create(db, ManufacturerCreate(name="ALIAXIS"))
        second = ManufacturerService.create(db, ManufacturerCreate(name="ALIAXIS"))
        assert first.id != second.id
        assert first.name == second.name == "ALIAXIS"


class TestGetById:
    def test_returns_existing(self, db, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        found = ManufacturerService.get_by_id(db, created.id)
        assert found is not None
        assert found.id == created.id
        assert found.name == "ООО ИММИД"

    def test_returns_none_when_missing(self, db):
        assert ManufacturerService.get_by_id(db, 999_999) is None

    def test_returns_none_for_unrelated_id(self, db, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        assert ManufacturerService.get_by_id(db, created.id + 10_000) is None


class TestList:
    def test_empty_database(self, db):
        assert ManufacturerService.list(db) == []

    def test_returns_all_by_default(self, db):
        names = ["Первый", "Второй", "Третий"]
        for name in names:
            ManufacturerService.create(db, ManufacturerCreate(name=name))
        assert len(ManufacturerService.list(db)) == 3

    def test_ordered_by_ascending_id(self, db):
        for name in ["Первый", "Второй", "Третий"]:
            ManufacturerService.create(db, ManufacturerCreate(name=name))
        listed = ManufacturerService.list(db)
        assert [m.name for m in listed] == ["Первый", "Второй", "Третий"]
        assert listed == sorted(listed, key=lambda m: m.id)

    def test_order_independent_of_name(self, db):
        for name in ["ЯМАЛ", "ALIAXIS", "ИММИД"]:
            ManufacturerService.create(db, ManufacturerCreate(name=name))
        listed = ManufacturerService.list(db)
        assert [m.name for m in listed] == ["ЯМАЛ", "ALIAXIS", "ИММИД"]

    def test_limit(self, db):
        for index in range(5):
            ManufacturerService.create(db, ManufacturerCreate(name=f"П{index}"))
        assert len(ManufacturerService.list(db, limit=2)) == 2

    def test_offset(self, db):
        for index in range(5):
            ManufacturerService.create(db, ManufacturerCreate(name=f"П{index}"))
        assert len(ManufacturerService.list(db, offset=3)) == 2

    def test_limit_and_offset_paging(self, db):
        for index in range(5):
            ManufacturerService.create(db, ManufacturerCreate(name=f"П{index}"))
        first_page = ManufacturerService.list(db, limit=2, offset=0)
        second_page = ManufacturerService.list(db, limit=2, offset=2)
        third_page = ManufacturerService.list(db, limit=2, offset=4)
        assert [m.name for m in first_page] == ["П0", "П1"]
        assert [m.name for m in second_page] == ["П2", "П3"]
        assert [m.name for m in third_page] == ["П4"]

    def test_offset_beyond_end_returns_empty(self, db):
        ManufacturerService.create(db, ManufacturerCreate(name="П0"))
        assert ManufacturerService.list(db, offset=100) == []

    def test_default_limit_is_50(self, db):
        for index in range(55):
            ManufacturerService.create(db, ManufacturerCreate(name=f"П{index:03d}"))
        assert len(ManufacturerService.list(db)) == 50


class TestUpdate:
    def test_updates_name(self, db, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        updated = ManufacturerService.update(
            db, created.id, ManufacturerUpdate(name="ООО ИММИД (Москва)")
        )
        assert updated is not None
        assert updated.name == "ООО ИММИД (Москва)"
        assert db.get(Manufacturer, created.id).name == "ООО ИММИД (Москва)"

    def test_name_is_normalized(self, db, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        updated = ManufacturerService.update(
            db, created.id, ManufacturerUpdate(name="   Новое Имя   ")
        )
        assert updated.name == "Новое Имя"

    def test_patch_with_absent_field_changes_nothing(self, db, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        updated = ManufacturerService.update(db, created.id, ManufacturerUpdate())
        assert updated is not None
        assert updated.name == "ООО ИММИД"
        assert db.get(Manufacturer, created.id).name == "ООО ИММИД"

    def test_patch_empty_payload_keeps_other_rows(self, db, make_manufacturer):
        first = make_manufacturer("Первый")
        second = make_manufacturer("Второй")
        ManufacturerService.update(db, first.id, ManufacturerUpdate())
        assert db.get(Manufacturer, second.id).name == "Второй"

    def test_missing_manufacturer_returns_none(self, db):
        assert (
            ManufacturerService.update(
                db, 999_999, ManufacturerUpdate(name="Новое")
            )
            is None
        )

    def test_missing_manufacturer_creates_nothing(self, db):
        before = db.scalar(select(func.count()).select_from(Manufacturer))
        ManufacturerService.update(
            db, 999_999, ManufacturerUpdate(name="Новое")
        )
        after = db.scalar(select(func.count()).select_from(Manufacturer))
        assert after == before

    def test_patch_creating_duplicate_name_allowed(self, db, make_manufacturer):
        first = make_manufacturer("ALIAXIS")
        second = make_manufacturer("Другой")
        ManufacturerService.update(db, second.id, ManufacturerUpdate(name="ALIAXIS"))
        assert db.get(Manufacturer, first.id).name == "ALIAXIS"
        assert db.get(Manufacturer, second.id).name == "ALIAXIS"

    def test_updated_object_is_readable_after_commit(self, db, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        updated = ManufacturerService.update(
            db, created.id, ManufacturerUpdate(name="Новое")
        )
        assert updated.id == created.id
        assert ManufacturerService.get_by_id(db, created.id).name == "Новое"


class TestTransactionBoundaries:
    def test_create_commits_once(self, db, monkeypatch, make_manufacturer):
        calls = []
        original = db.commit
        monkeypatch.setattr(
            db, "commit", lambda: (calls.append(1), original())[1]
        )
        ManufacturerService.create(db, ManufacturerCreate(name="ООО"))
        assert len(calls) == 1

    def test_update_with_changes_commits_once(
        self, db, monkeypatch, make_manufacturer
    ):
        created = make_manufacturer("ООО ИММИД")
        calls = []
        original = db.commit
        monkeypatch.setattr(
            db, "commit", lambda: (calls.append(1), original())[1]
        )
        ManufacturerService.update(
            db, created.id, ManufacturerUpdate(name="Новое")
        )
        assert len(calls) == 1

    def test_update_without_changes_does_not_commit(
        self, db, monkeypatch, make_manufacturer
    ):
        created = make_manufacturer("ООО ИММИД")
        calls = []
        monkeypatch.setattr(
            db, "commit", lambda: calls.append(1)
        )
        ManufacturerService.update(db, created.id, ManufacturerUpdate())
        assert calls == []

    def test_read_operations_do_not_commit(self, db, monkeypatch, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        ManufacturerService.get_by_id(db, created.id)
        ManufacturerService.list(db)
        assert calls == []

    def test_rollback_discards_service_changes(self, db):
        manufacturer = ManufacturerService.create(
            db, ManufacturerCreate(name="ООО ИММИД")
        )
        db.delete(manufacturer)
        db.commit()
        assert ManufacturerService.get_by_id(db, manufacturer.id) is None