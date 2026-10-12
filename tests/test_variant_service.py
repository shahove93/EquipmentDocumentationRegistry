from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.api.manufacturers.schemas import ManufacturerCreate
from app.api.products.schemas import ProductCreate
from app.api.variants.schemas import (
    ProductVariantCreate,
    ProductVariantUpdate,
)
from app.models.manufacturer import Manufacturer
from app.models.product import Product
from app.models.variant import ProductVariant
from app.services.manufacturer_service import ManufacturerService
from app.services.product_service import ProductService
from app.services.variant_service import (
    ProductNotFoundError,
    ProductVariantService,
    VariantAlreadyExistsError,
    VariantServiceError,
)

SIZE_A = "Ø63 × 5.8"
SIZE_B = "Ду50"
SIZE_C = "Ø110 × 10.0"


@pytest.fixture
def manufacturer(db) -> Manufacturer:
    return ManufacturerService.create(db, ManufacturerCreate(name="ООО ИММИД"))


@pytest.fixture
def product(db, manufacturer) -> Product:
    return ProductService.create(
        db,
        ProductCreate(
            name="Труба ПЭ100 SDR11",
            standard="ГОСТ 58121.2-2018",
            manufacturer_id=manufacturer.id,
        ),
    )


@pytest.fixture
def other_product(db, manufacturer) -> Product:
    return ProductService.create(
        db,
        ProductCreate(
            name="Труба ПЭ100 SDR17",
            standard="ГОСТ 58121.2-2018",
            manufacturer_id=manufacturer.id,
        ),
    )


@pytest.fixture
def make_variant(db, product):
    def _make(
        size_text: str = SIZE_A,
        product_id: int | None = None,
        **extra,
    ) -> ProductVariant:
        return ProductVariantService.create(
            db,
            ProductVariantCreate(
                product_id=product.id if product_id is None else product_id,
                size_text=size_text,
                **extra,
            ),
        )

    return _make


class TestCreate:
    def test_creates_and_persists(self, db, product):
        variant = ProductVariantService.create(
            db, ProductVariantCreate(product_id=product.id, size_text=SIZE_A)
        )
        assert isinstance(variant, ProductVariant)
        assert variant.id is not None
        assert variant.product_id == product.id
        assert variant.size_text == SIZE_A

    def test_row_exists_in_database(self, db, product):
        variant = ProductVariantService.create(
            db, ProductVariantCreate(product_id=product.id, size_text=SIZE_A)
        )
        stored = db.get(ProductVariant, variant.id)
        assert stored is not None
        assert stored.size_text == SIZE_A

    def test_required_fields_only(self, db, product):
        variant = ProductVariantService.create(
            db, ProductVariantCreate(product_id=product.id, size_text=SIZE_A)
        )
        assert variant.diameter is None
        assert variant.nominal_diameter is None
        assert variant.wall_thickness is None

    def test_numeric_fields_persisted(self, db, product):
        variant = ProductVariantService.create(
            db,
            ProductVariantCreate(
                product_id=product.id,
                size_text=SIZE_A,
                diameter="63",
                nominal_diameter="50",
                wall_thickness="5.80",
            ),
        )
        stored = db.get(ProductVariant, variant.id)
        assert stored.diameter == Decimal("63")
        assert stored.nominal_diameter == Decimal("50")
        assert stored.wall_thickness == Decimal("5.80")

    def test_decimal_scale_not_rounded(self, db, product):
        variant = ProductVariantService.create(
            db,
            ProductVariantCreate(
                product_id=product.id, size_text=SIZE_A, diameter="63.25"
            ),
        )
        stored = db.get(ProductVariant, variant.id)
        assert stored.diameter == Decimal("63.25")
        assert stored.diameter.as_tuple().exponent == -2

    def test_decimal_stored_as_numeric_type(self, db, product):
        variant = ProductVariantService.create(
            db,
            ProductVariantCreate(
                product_id=product.id, size_text=SIZE_A, diameter="0.01"
            ),
        )
        stored = db.get(ProductVariant, variant.id)
        assert isinstance(stored.diameter, Decimal)
        assert not isinstance(stored.diameter, float)

    def test_size_text_whitespace_stripped(self, db, product):
        variant = ProductVariantService.create(
            db, ProductVariantCreate(product_id=product.id, size_text=f"  {SIZE_A}  ")
        )
        assert variant.size_text == SIZE_A

    def test_relationship_to_product_loaded(self, db, product):
        variant = ProductVariantService.create(
            db, ProductVariantCreate(product_id=product.id, size_text=SIZE_A)
        )
        assert variant.product is product

    def test_appears_in_product_variants(self, db, product):
        variant = ProductVariantService.create(
            db, ProductVariantCreate(product_id=product.id, size_text=SIZE_A)
        )
        db.refresh(product)
        assert variant in product.variants

    def test_commit_once(self, db, product, monkeypatch):
        calls = []
        original = db.commit
        monkeypatch.setattr(
            db, "commit", lambda: (calls.append(1), original())[1]
        )
        ProductVariantService.create(
            db, ProductVariantCreate(product_id=product.id, size_text=SIZE_A)
        )
        assert len(calls) == 1


class TestCreateWithUnknownProduct:
    def test_raises_product_not_found(self, db):
        with pytest.raises(ProductNotFoundError):
            ProductVariantService.create(
                db, ProductVariantCreate(product_id=999_999, size_text=SIZE_A)
            )

    def test_error_carries_id(self, db):
        with pytest.raises(ProductNotFoundError) as info:
            ProductVariantService.create(
                db, ProductVariantCreate(product_id=4242, size_text=SIZE_A)
            )
        assert info.value.product_id == 4242
        assert "4242" in str(info.value)

    def test_error_is_variant_service_error(self, db):
        with pytest.raises(VariantServiceError):
            ProductVariantService.create(
                db, ProductVariantCreate(product_id=999_999, size_text=SIZE_A)
            )

    def test_nothing_persisted(self, db):
        with pytest.raises(ProductNotFoundError):
            ProductVariantService.create(
                db, ProductVariantCreate(product_id=999_999, size_text=SIZE_A)
            )
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 0

    def test_no_pending_objects(self, db):
        with pytest.raises(ProductNotFoundError):
            ProductVariantService.create(
                db, ProductVariantCreate(product_id=999_999, size_text=SIZE_A)
            )
        assert len(db.new) == 0

    def test_no_commit(self, db, monkeypatch):
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        with pytest.raises(ProductNotFoundError):
            ProductVariantService.create(
                db, ProductVariantCreate(product_id=999_999, size_text=SIZE_A)
            )
        assert calls == []


class TestAdr006Uniqueness:
    def test_duplicate_size_text_in_same_product_rejected(self, db, product, make_variant):
        make_variant(SIZE_A)
        with pytest.raises(VariantAlreadyExistsError):
            make_variant(SIZE_A)

    def test_error_carries_product_id_and_size(self, db, product, make_variant):
        make_variant(SIZE_A)
        with pytest.raises(VariantAlreadyExistsError) as info:
            make_variant(SIZE_A)
        assert info.value.product_id == product.id
        assert info.value.size_text == SIZE_A
        assert SIZE_A in str(info.value)

    def test_error_is_variant_service_error(self, db, product, make_variant):
        make_variant(SIZE_A)
        with pytest.raises(VariantServiceError):
            make_variant(SIZE_A)

    def test_different_sizes_allowed(self, db, make_variant):
        make_variant(SIZE_A)
        make_variant(SIZE_B)
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 2

    def test_same_size_in_different_products_allowed(
        self, db, product, other_product, make_variant
    ):
        make_variant(SIZE_A, product_id=product.id)
        make_variant(SIZE_A, product_id=other_product.id)
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 2

    def test_whitespace_variant_is_a_distinct_key(self, db, product, make_variant):
        # schema strips before persisting, so this is the same logical key
        make_variant(SIZE_A)
        with pytest.raises(VariantAlreadyExistsError):
            make_variant(f"  {SIZE_A}  ")

    def test_duplicate_not_persisted(self, db, product, make_variant):
        make_variant(SIZE_A)
        with pytest.raises(VariantAlreadyExistsError):
            make_variant(SIZE_A)
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 1

    def test_session_usable_after_unique_violation(self, db, product, make_variant):
        make_variant(SIZE_A)
        with pytest.raises(VariantAlreadyExistsError):
            make_variant(SIZE_A)
        assert not db.in_transaction()
        third = make_variant(SIZE_C)
        assert third.id is not None

    def test_no_pending_changes_after_violation(self, db, product, make_variant):
        make_variant(SIZE_A)
        with pytest.raises(VariantAlreadyExistsError):
            make_variant(SIZE_A)
        assert len(db.new) == 0
        assert len(db.dirty) == 0

    def test_rollback_happened_once(self, db, product, make_variant, monkeypatch):
        make_variant(SIZE_A)
        calls = []
        monkeypatch.setattr(db, "rollback", lambda: calls.append(1))
        with pytest.raises(VariantAlreadyExistsError):
            make_variant(SIZE_A)
        assert len(calls) == 1

    def test_other_integrity_errors_not_masked(self, db, product, make_variant):
        """A violation of another constraint must not become VariantAlreadyExists."""
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        make_variant(SIZE_A)
        # document_types has its own unique constraint (same SQLSTATE 23505)
        db.execute(text("INSERT INTO document_types (name) VALUES ('DT')"))
        db.commit()
        with pytest.raises(IntegrityError) as info:
            db.execute(text("INSERT INTO document_types (name) VALUES ('DT')"))
            db.commit()
        assert not isinstance(info.value, VariantAlreadyExistsError)
        db.rollback()

    def test_foreign_key_violation_not_masked(self, db, product):
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError) as info:
            db.execute(
                text(
                    "INSERT INTO product_variants (product_id, size_text) "
                    "VALUES (999999, 'X')"
                )
            )
            db.commit()
        assert not isinstance(info.value, VariantAlreadyExistsError)
        db.rollback()


class TestGetById:
    def test_returns_existing(self, db, product, make_variant):
        created = make_variant(SIZE_A)
        found = ProductVariantService.get_by_id(db, created.id)
        assert found is not None
        assert found.id == created.id
        assert found.size_text == SIZE_A

    def test_returns_none_when_missing(self, db):
        assert ProductVariantService.get_by_id(db, 999_999) is None

    def test_does_not_commit(self, db, make_variant, monkeypatch):
        created = make_variant(SIZE_A)
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        ProductVariantService.get_by_id(db, created.id)
        assert calls == []


class TestList:
    def test_requires_known_product(self, db, product, make_variant):
        make_variant(SIZE_A)
        assert len(ProductVariantService.list(db, product.id)) == 1

    def test_empty_for_product_without_variants(self, db, product):
        assert ProductVariantService.list(db, product.id) == []

    def test_filters_by_product_id(self, db, product, other_product, make_variant):
        make_variant(SIZE_A, product_id=product.id)
        make_variant(SIZE_B, product_id=product.id)
        make_variant(SIZE_C, product_id=other_product.id)
        listed = ProductVariantService.list(db, product.id)
        assert {v.size_text for v in listed} == {SIZE_A, SIZE_B}
        assert all(v.product_id == product.id for v in listed)

    def test_ordered_by_ascending_id(self, db, product, make_variant):
        make_variant(SIZE_A)
        make_variant(SIZE_B)
        make_variant(SIZE_C)
        listed = ProductVariantService.list(db, product.id)
        assert [v.size_text for v in listed] == [SIZE_A, SIZE_B, SIZE_C]
        assert [v.id for v in listed] == sorted(v.id for v in listed)

    def test_order_independent_of_size_text(self, db, product, make_variant):
        make_variant(SIZE_C)
        make_variant(SIZE_A)
        make_variant(SIZE_B)
        listed = ProductVariantService.list(db, product.id)
        assert [v.size_text for v in listed] == [SIZE_C, SIZE_A, SIZE_B]

    def test_limit(self, db, product, make_variant):
        for size in (SIZE_A, SIZE_B, SIZE_C):
            make_variant(size)
        assert len(ProductVariantService.list(db, product.id, limit=2)) == 2

    def test_offset(self, db, product, make_variant):
        for size in (SIZE_A, SIZE_B, SIZE_C):
            make_variant(size)
        assert len(ProductVariantService.list(db, product.id, offset=2)) == 1

    def test_limit_and_offset(self, db, product, make_variant):
        for size in (SIZE_A, SIZE_B, SIZE_C):
            make_variant(size)
        page = ProductVariantService.list(db, product.id, limit=1, offset=1)
        assert [v.size_text for v in page] == [SIZE_B]

    def test_offset_beyond_end(self, db, product, make_variant):
        make_variant(SIZE_A)
        assert ProductVariantService.list(db, product.id, offset=100) == []

    def test_missing_product_raises(self, db):
        with pytest.raises(ProductNotFoundError) as info:
            ProductVariantService.list(db, 999_999)
        assert info.value.product_id == 999_999

    def test_missing_product_error_is_service_error(self, db):
        with pytest.raises(VariantServiceError):
            ProductVariantService.list(db, 999_999)

    def test_does_not_commit(self, db, product, make_variant, monkeypatch):
        make_variant(SIZE_A)
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        ProductVariantService.list(db, product.id)
        assert calls == []


class TestUpdate:
    def test_updates_size_text(self, db, product, make_variant):
        created = make_variant(SIZE_A)
        updated = ProductVariantService.update(
            db, created.id, ProductVariantUpdate(size_text=SIZE_B)
        )
        assert updated.size_text == SIZE_B
        assert db.get(ProductVariant, created.id).size_text == SIZE_B

    def test_updates_numeric_fields(self, db, product, make_variant):
        created = make_variant(SIZE_A)
        updated = ProductVariantService.update(
            db,
            created.id,
            ProductVariantUpdate(diameter="63", nominal_diameter="50", wall_thickness="5.80"),
        )
        assert updated.diameter == Decimal("63")
        assert updated.nominal_diameter == Decimal("50")
        assert updated.wall_thickness == Decimal("5.80")

    def test_numeric_fields_persisted(self, db, product, make_variant):
        created = make_variant(SIZE_A)
        ProductVariantService.update(
            db, created.id, ProductVariantUpdate(diameter="63")
        )
        db.expire_all()
        assert db.get(ProductVariant, created.id).diameter == Decimal("63")

    def test_clears_numeric_field_with_null(self, db, product, make_variant):
        created = make_variant(SIZE_A, diameter="63", wall_thickness="5.8")
        updated = ProductVariantService.update(
            db, created.id, ProductVariantUpdate(diameter=None)
        )
        assert updated.diameter is None
        assert updated.wall_thickness == Decimal("5.8")
        db.expire_all()
        assert db.get(ProductVariant, created.id).diameter is None

    def test_absent_fields_untouched(self, db, product, make_variant):
        created = make_variant(SIZE_A, diameter="63")
        updated = ProductVariantService.update(
            db, created.id, ProductVariantUpdate(size_text=SIZE_B)
        )
        assert updated.size_text == SIZE_B
        assert updated.diameter == Decimal("63")

    def test_empty_patch_returns_unchanged(self, db, product, make_variant):
        created = make_variant(SIZE_A)
        updated = ProductVariantService.update(db, created.id, ProductVariantUpdate())
        assert updated is not None
        assert updated.size_text == SIZE_A

    def test_empty_patch_does_not_commit(self, db, product, make_variant, monkeypatch):
        created = make_variant(SIZE_A)
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        ProductVariantService.update(db, created.id, ProductVariantUpdate())
        assert calls == []

    def test_changes_commit_once(self, db, product, make_variant, monkeypatch):
        created = make_variant(SIZE_A)
        calls = []
        original = db.commit
        monkeypatch.setattr(
            db, "commit", lambda: (calls.append(1), original())[1]
        )
        ProductVariantService.update(
            db, created.id, ProductVariantUpdate(size_text=SIZE_B)
        )
        assert len(calls) == 1

    def test_missing_variant_returns_none(self, db):
        assert (
            ProductVariantService.update(db, 999_999, ProductVariantUpdate(size_text=SIZE_B))
            is None
        )

    def test_missing_variant_empty_patch_returns_none(self, db):
        assert ProductVariantService.update(db, 999_999, ProductVariantUpdate()) is None

    def test_product_id_never_changes(self, db, product, make_variant):
        created = make_variant(SIZE_A)
        updated = ProductVariantService.update(
            db, created.id, ProductVariantUpdate(size_text=SIZE_B, diameter="63")
        )
        assert updated.product_id == product.id
        db.expire_all()
        assert db.get(ProductVariant, created.id).product_id == product.id

    def test_update_schema_has_no_product_id(self):
        assert "product_id" not in ProductVariantUpdate.model_fields

    def test_other_rows_untouched(self, db, product, make_variant):
        first = make_variant(SIZE_A)
        second = make_variant(SIZE_B)
        ProductVariantService.update(
            db, first.id, ProductVariantUpdate(size_text=SIZE_C)
        )
        assert db.get(ProductVariant, second.id).size_text == SIZE_B


class TestUpdateUniqueness:
    def test_rename_to_existing_size_rejected(self, db, product, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        with pytest.raises(VariantAlreadyExistsError):
            ProductVariantService.update(
                db, first.id, ProductVariantUpdate(size_text=SIZE_B)
            )

    def test_error_carries_product_and_size(self, db, product, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        with pytest.raises(VariantAlreadyExistsError) as info:
            ProductVariantService.update(
                db, first.id, ProductVariantUpdate(size_text=SIZE_B)
            )
        assert info.value.product_id == product.id
        assert info.value.size_text == SIZE_B

    def test_no_partial_save(self, db, product, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        with pytest.raises(VariantAlreadyExistsError):
            ProductVariantService.update(
                db, first.id, ProductVariantUpdate(size_text=SIZE_B)
            )
        db.expire_all()
        stored = db.get(ProductVariant, first.id)
        assert stored.size_text == SIZE_A

    def test_other_change_not_persisted_on_collision(self, db, product, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        with pytest.raises(VariantAlreadyExistsError):
            ProductVariantService.update(
                db,
                first.id,
                ProductVariantUpdate(size_text=SIZE_B, diameter="63"),
            )
        db.expire_all()
        assert db.get(ProductVariant, first.id).diameter is None

    def test_session_usable_after_collision(self, db, product, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        with pytest.raises(VariantAlreadyExistsError):
            ProductVariantService.update(
                db, first.id, ProductVariantUpdate(size_text=SIZE_B)
            )
        assert not db.in_transaction()
        assert ProductVariantService.update(
            db, first.id, ProductVariantUpdate(size_text=SIZE_C)
        ).size_text == SIZE_C

    def test_rollback_after_collision(self, db, product, make_variant, monkeypatch):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        calls = []
        monkeypatch.setattr(db, "rollback", lambda: calls.append(1))
        with pytest.raises(VariantAlreadyExistsError):
            ProductVariantService.update(
                db, first.id, ProductVariantUpdate(size_text=SIZE_B)
            )
        assert len(calls) == 1

    def test_no_pending_changes_after_collision(self, db, product, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        with pytest.raises(VariantAlreadyExistsError):
            ProductVariantService.update(
                db, first.id, ProductVariantUpdate(size_text=SIZE_B)
            )
        assert len(db.dirty) == 0
        assert len(db.new) == 0

    def test_same_size_on_another_product_allowed(
        self, db, product, other_product, make_variant
    ):
        first = make_variant(SIZE_A, product_id=product.id)
        other = make_variant(SIZE_B, product_id=other_product.id)
        updated = ProductVariantService.update(
            db, other.id, ProductVariantUpdate(size_text=SIZE_A)
        )
        assert updated.size_text == SIZE_A
        assert updated.product_id == other_product.id
        assert db.get(ProductVariant, first.id).size_text == SIZE_A

    def test_renaming_to_own_size_allowed(self, db, product, make_variant):
        created = make_variant(SIZE_A)
        updated = ProductVariantService.update(
            db, created.id, ProductVariantUpdate(size_text=SIZE_A)
        )
        assert updated.size_text == SIZE_A


class TestDataIntegrity:
    def test_product_variants_count(self, db, product, make_variant):
        make_variant(SIZE_A)
        make_variant(SIZE_B)
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 2

    def test_product_relationship_intact_after_updates(
        self, db, product, make_variant
    ):
        created = make_variant(SIZE_A)
        updated = ProductVariantService.update(
            db, created.id, ProductVariantUpdate(size_text=SIZE_B)
        )
        assert updated.product is product
        assert updated.product_id == product.id

    def test_no_sdr_column_written(self, db, product, make_variant):
        from sqlalchemy import text

        variant = make_variant("Труба ПЭ100 SDR11 / Ø63")
        row = db.execute(
            text("SELECT * FROM product_variants WHERE id=:i"), {"i": variant.id}
        ).mappings().one()
        assert "sdr" not in row
        assert row["size_text"] == "Труба ПЭ100 SDR11 / Ø63"