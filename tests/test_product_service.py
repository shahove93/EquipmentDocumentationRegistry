import pytest
from sqlalchemy import func, select

from app.api.manufacturers.schemas import ManufacturerCreate
from app.api.products.schemas import ProductCreate, ProductUpdate
from app.models.manufacturer import Manufacturer
from app.models.product import Product
from app.services.manufacturer_service import ManufacturerService
from app.services.product_service import (
    ManufacturerNotFoundError,
    ProductService,
    ProductServiceError,
)


@pytest.fixture
def manufacturer(db) -> Manufacturer:
    return ManufacturerService.create(db, ManufacturerCreate(name="ООО ИММИД"))


@pytest.fixture
def other_manufacturer(db) -> Manufacturer:
    return ManufacturerService.create(db, ManufacturerCreate(name="АИР-ГАЗ"))


@pytest.fixture
def make_product(db, manufacturer):
    def _make(
        name: str = "Труба ПЭ100 SDR11",
        standard: str = "ГОСТ 58121.2-2018",
        manufacturer_id: int | None = None,
        **extra,
    ) -> Product:
        return ProductService.create(
            db,
            ProductCreate(
                name=name,
                standard=standard,
                manufacturer_id=(
                    manufacturer.id if manufacturer_id is None else manufacturer_id
                ),
                **extra,
            ),
        )

    return _make


class TestCreate:
    def test_returns_persisted_product(self, db, manufacturer):
        product = ProductService.create(
            db,
            ProductCreate(
                name="Труба ПЭ100 SDR11",
                standard="ГОСТ 58121.2-2018",
                manufacturer_id=manufacturer.id,
            ),
        )
        assert isinstance(product, Product)
        assert product.id is not None
        assert product.name == "Труба ПЭ100 SDR11"
        assert product.standard == "ГОСТ 58121.2-2018"
        assert product.manufacturer_id == manufacturer.id

    def test_row_exists_in_database(self, db, manufacturer):
        product = ProductService.create(
            db,
            ProductCreate(
                name="Труба", standard="ГОСТ", manufacturer_id=manufacturer.id
            ),
        )
        stored = db.get(Product, product.id)
        assert stored is not None
        assert stored.name == "Труба"

    def test_optional_fields_persisted(self, db, manufacturer):
        product = ProductService.create(
            db,
            ProductCreate(
                name="Труба",
                standard="ГОСТ",
                manufacturer_id=manufacturer.id,
                designation="ТРУБА_ПЭ_110_SDR11",
                product_type="труба",
            ),
        )
        assert product.designation == "ТРУБА_ПЭ_110_SDR11"
        assert product.product_type == "труба"

    def test_optional_fields_default_to_none(self, db, manufacturer):
        product = ProductService.create(
            db,
            ProductCreate(
                name="Труба", standard="ГОСТ", manufacturer_id=manufacturer.id
            ),
        )
        assert product.designation is None
        assert product.product_type is None

    def test_sdr_lives_in_name(self, db, manufacturer):
        product = ProductService.create(
            db,
            ProductCreate(
                name="Труба ПЭ100 SDR17",
                standard="ГОСТ 58121.2-2018",
                manufacturer_id=manufacturer.id,
            ),
        )
        assert product.name == "Труба ПЭ100 SDR17"
        assert not hasattr(product, "sdr")

    def test_names_are_normalized(self, db, manufacturer):
        product = ProductService.create(
            db,
            ProductCreate(
                name="  Труба  ",
                standard="  ГОСТ  ",
                manufacturer_id=manufacturer.id,
            ),
        )
        assert product.name == "Труба"
        assert product.standard == "ГОСТ"

    def test_relationship_to_manufacturer_loaded(self, db, manufacturer, make_product):
        product = make_product()
        assert product.manufacturer is manufacturer

    def test_appears_in_manufacturer_products(self, db, manufacturer, make_product):
        product = make_product()
        db.refresh(manufacturer)
        assert product in manufacturer.products

    def test_same_name_allowed_twice(self, db, manufacturer):
        first = ProductService.create(
            db,
            ProductCreate(
                name="Труба", standard="ГОСТ", manufacturer_id=manufacturer.id
            ),
        )
        second = ProductService.create(
            db,
            ProductCreate(
                name="Труба", standard="ГОСТ", manufacturer_id=manufacturer.id
            ),
        )
        assert first.id != second.id

    def test_count_matches_created_rows(self, db, manufacturer, make_product):
        make_product(name="Первый")
        make_product(name="Второй")
        total = db.scalar(select(func.count()).select_from(Product))
        assert total == 2

    def test_ids_increase(self, db, make_product):
        first = make_product(name="Первый")
        second = make_product(name="Второй")
        assert second.id > first.id


class TestCreateWithUnknownManufacturer:
    def test_raises_manufacturer_not_found(self, db):
        with pytest.raises(ManufacturerNotFoundError):
            ProductService.create(
                db,
                ProductCreate(
                    name="Труба", standard="ГОСТ", manufacturer_id=999_999
                ),
            )

    def test_error_carries_missing_id(self, db):
        with pytest.raises(ManufacturerNotFoundError) as info:
            ProductService.create(
                db,
                ProductCreate(name="Труба", standard="ГОСТ", manufacturer_id=4242),
            )
        assert info.value.manufacturer_id == 4242
        assert "4242" in str(info.value)

    def test_error_is_product_service_error(self, db):
        with pytest.raises(ProductServiceError):
            ProductService.create(
                db,
                ProductCreate(name="Труба", standard="ГОСТ", manufacturer_id=1),
            )

    def test_nothing_persisted(self, db):
        with pytest.raises(ManufacturerNotFoundError):
            ProductService.create(
                db,
                ProductCreate(name="Труба", standard="ГОСТ", manufacturer_id=999_999),
            )
        assert db.scalar(select(func.count()).select_from(Product)) == 0

    def test_no_pending_object_left_in_session(self, db, manufacturer):
        with pytest.raises(ManufacturerNotFoundError):
            ProductService.create(
                db,
                ProductCreate(
                    name="Труба", standard="ГОСТ", manufacturer_id=999_999
                ),
            )
        assert len(db.new) == 0

    def test_zero_manufacturer_id_rejected_by_schema(self, db):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProductCreate(name="Труба", standard="ГОСТ", manufacturer_id=0)


class TestGetById:
    def test_returns_existing(self, db, make_product):
        created = make_product(name="Труба ПЭ100 SDR11")
        found = ProductService.get_by_id(db, created.id)
        assert found is not None
        assert found.id == created.id
        assert found.name == "Труба ПЭ100 SDR11"

    def test_returns_none_when_missing(self, db):
        assert ProductService.get_by_id(db, 999_999) is None

    def test_returns_none_for_unrelated_id(self, db, make_product):
        created = make_product()
        assert ProductService.get_by_id(db, created.id + 10_000) is None

    def test_does_not_commit(self, db, make_product, monkeypatch):
        created = make_product()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        ProductService.get_by_id(db, created.id)
        assert calls == []


class TestList:
    def test_empty_database(self, db):
        assert ProductService.list(db) == []

    def test_returns_all_by_default(self, db, make_product):
        for name in ("Первый", "Второй", "Третий"):
            make_product(name=name)
        assert len(ProductService.list(db)) == 3

    def test_ordered_by_ascending_id(self, db, make_product):
        for name in ("Первый", "Второй", "Третий"):
            make_product(name=name)
        listed = ProductService.list(db)
        assert [p.id for p in listed] == sorted(p.id for p in listed)
        assert [p.name for p in listed] == ["Первый", "Второй", "Третий"]

    def test_order_independent_of_name(self, db, make_product):
        for name in ("ЯМАЛ", "ALIAXIS", "ИММИД"):
            make_product(name=name)
        listed = ProductService.list(db)
        assert [p.name for p in listed] == ["ЯМАЛ", "ALIAXIS", "ИММИД"]

    def test_limit(self, db, make_product):
        for index in range(5):
            make_product(name=f"П{index}")
        assert len(ProductService.list(db, limit=2)) == 2

    def test_offset(self, db, make_product):
        for index in range(5):
            make_product(name=f"П{index}")
        assert len(ProductService.list(db, offset=3)) == 2

    def test_limit_and_offset(self, db, make_product):
        for index in range(5):
            make_product(name=f"П{index}")
        first = ProductService.list(db, limit=2, offset=0)
        second = ProductService.list(db, limit=2, offset=2)
        assert [p.name for p in first] == ["П0", "П1"]
        assert [p.name for p in second] == ["П2", "П3"]

    def test_offset_beyond_end(self, db, make_product):
        make_product()
        assert ProductService.list(db, offset=100) == []

    def test_default_limit_is_50(self, db, make_product):
        for index in range(55):
            make_product(name=f"П{index:03d}")
        assert len(ProductService.list(db)) == 50

    def test_does_not_commit(self, db, make_product, monkeypatch):
        make_product()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        ProductService.list(db)
        assert calls == []


class TestUpdate:
    def test_updates_name(self, db, make_product):
        created = make_product(name="Труба ПЭ100 SDR11")
        updated = ProductService.update(
            db, created.id, ProductUpdate(name="Труба ПЭ100 SDR17")
        )
        assert updated.name == "Труба ПЭ100 SDR17"
        assert db.get(Product, created.id).name == "Труба ПЭ100 SDR17"

    def test_updates_standard(self, db, make_product):
        created = make_product(standard="ГОСТ 58121.2-2018")
        updated = ProductService.update(
            db, created.id, ProductUpdate(standard="ТУ 22.21.29-002-0106727451-2020")
        )
        assert updated.standard == "ТУ 22.21.29-002-0106727451-2020"

    def test_updates_optional_field(self, db, make_product):
        created = make_product()
        updated = ProductService.update(
            db, created.id, ProductUpdate(designation="АРТ-1")
        )
        assert updated.designation == "АРТ-1"

    def test_clears_optional_field_with_null(self, db, make_product):
        created = make_product(designation="АРТ-1")
        updated = ProductService.update(
            db, created.id, ProductUpdate(designation=None)
        )
        assert updated.designation is None
        assert db.get(Product, created.id).designation is None

    def test_updates_several_fields(self, db, make_product):
        created = make_product()
        updated = ProductService.update(
            db,
            created.id,
            ProductUpdate(name="Новое", standard="ТУ", product_type="труба"),
        )
        assert updated.name == "Новое"
        assert updated.standard == "ТУ"
        assert updated.product_type == "труба"

    def test_absent_fields_untouched(self, db, make_product):
        created = make_product(name="Труба", standard="ГОСТ", designation="АРТ-1")
        updated = ProductService.update(
            db, created.id, ProductUpdate(name="Новое Имя")
        )
        assert updated.name == "Новое Имя"
        assert updated.standard == "ГОСТ"
        assert updated.designation == "АРТ-1"

    def test_empty_patch_returns_unchanged(self, db, make_product):
        created = make_product(name="Труба")
        updated = ProductService.update(db, created.id, ProductUpdate())
        assert updated is not None
        assert updated.name == "Труба"

    def test_empty_patch_does_not_commit(self, db, make_product, monkeypatch):
        created = make_product()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        ProductService.update(db, created.id, ProductUpdate())
        assert calls == []

    def test_changes_commit_once(self, db, make_product, monkeypatch):
        created = make_product()
        calls = []
        original = db.commit
        monkeypatch.setattr(
            db, "commit", lambda: (calls.append(1), original())[1]
        )
        ProductService.update(db, created.id, ProductUpdate(name="Новое"))
        assert len(calls) == 1

    def test_create_commits_once(self, db, manufacturer, monkeypatch):
        calls = []
        original = db.commit
        monkeypatch.setattr(
            db, "commit", lambda: (calls.append(1), original())[1]
        )
        ProductService.create(
            db,
            ProductCreate(
                name="Труба", standard="ГОСТ", manufacturer_id=manufacturer.id
            ),
        )
        assert len(calls) == 1

    def test_missing_product_returns_none(self, db):
        assert ProductService.update(db, 999_999, ProductUpdate(name="X")) is None

    def test_missing_product_with_empty_patch_returns_none(self, db):
        assert ProductService.update(db, 999_999, ProductUpdate()) is None

    def test_other_rows_untouched(self, db, make_product):
        first = make_product(name="Первый")
        second = make_product(name="Второй")
        ProductService.update(db, first.id, ProductUpdate(name="Изменён"))
        assert db.get(Product, second.id).name == "Второй"

    def test_manufacturer_relationship_survives_update(self, db, manufacturer, make_product):
        created = make_product()
        updated = ProductService.update(db, created.id, ProductUpdate(name="Новое"))
        assert updated.manufacturer is manufacturer
        assert updated.manufacturer_id == manufacturer.id


class TestUpdateManufacturer:
    def test_changes_to_existing_manufacturer(
        self, db, manufacturer, other_manufacturer, make_product
    ):
        created = make_product()
        updated = ProductService.update(
            db, created.id, ProductUpdate(manufacturer_id=other_manufacturer.id)
        )
        assert updated.manufacturer_id == other_manufacturer.id
        assert updated.manufacturer is other_manufacturer

    def test_persisted_manufacturer_change(self, db, other_manufacturer, make_product):
        created = make_product()
        ProductService.update(
            db, created.id, ProductUpdate(manufacturer_id=other_manufacturer.id)
        )
        db.expire_all()
        assert db.get(Product, created.id).manufacturer_id == other_manufacturer.id

    def test_same_manufacturer_allowed(self, db, manufacturer, make_product):
        created = make_product()
        updated = ProductService.update(
            db, created.id, ProductUpdate(manufacturer_id=manufacturer.id)
        )
        assert updated.manufacturer_id == manufacturer.id

    def test_unknown_manufacturer_raises(self, db, make_product):
        created = make_product()
        with pytest.raises(ManufacturerNotFoundError):
            ProductService.update(
                db, created.id, ProductUpdate(manufacturer_id=999_999)
            )

    def test_error_carries_missing_id(self, db, make_product):
        created = make_product()
        with pytest.raises(ManufacturerNotFoundError) as info:
            ProductService.update(
                db, created.id, ProductUpdate(manufacturer_id=4242)
            )
        assert info.value.manufacturer_id == 4242
        assert "4242" in str(info.value)

    def test_no_partial_save_on_unknown_manufacturer(self, db, make_product):
        created = make_product(name="Труба", standard="ГОСТ")
        with pytest.raises(ManufacturerNotFoundError):
            ProductService.update(
                db,
                created.id,
                ProductUpdate(name="Новое Имя", manufacturer_id=999_999),
            )
        db.expire_all()
        stored = db.get(Product, created.id)
        assert stored.name == "Труба"

    def test_standard_not_saved_on_rejected_request(self, db, make_product):
        created = make_product(standard="ГОСТ")
        with pytest.raises(ManufacturerNotFoundError):
            ProductService.update(
                db,
                created.id,
                ProductUpdate(standard="ТУ", manufacturer_id=999_999),
            )
        db.expire_all()
        assert db.get(Product, created.id).standard == "ГОСТ"

    def test_manufacturer_not_changed_after_rejection(self, db, manufacturer, make_product):
        created = make_product()
        with pytest.raises(ManufacturerNotFoundError):
            ProductService.update(
                db, created.id, ProductUpdate(manufacturer_id=999_999)
            )
        db.expire_all()
        assert db.get(Product, created.id).manufacturer_id == manufacturer.id

    def test_no_pending_changes_after_rejection(self, db, make_product):
        created = make_product()
        with pytest.raises(ManufacturerNotFoundError):
            ProductService.update(
                db, created.id, ProductUpdate(name="Новое", manufacturer_id=999_999)
            )
        assert len(db.dirty) == 0

    def test_no_commit_after_rejection(self, db, make_product, monkeypatch):
        created = make_product()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        with pytest.raises(ManufacturerNotFoundError):
            ProductService.update(
                db, created.id, ProductUpdate(manufacturer_id=999_999)
            )
        assert calls == []

    def test_product_still_readable_after_rejection(self, db, make_product):
        created = make_product()
        with pytest.raises(ManufacturerNotFoundError):
            ProductService.update(
                db, created.id, ProductUpdate(manufacturer_id=999_999)
            )
        assert ProductService.get_by_id(db, created.id) is not None