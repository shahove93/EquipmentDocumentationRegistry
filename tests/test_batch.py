from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String

from app.models import Base, Batch, Product, ProductVariant


class TestBatchTable:
    def test_table_name(self):
        assert Batch.__tablename__ == "batches"

    def test_registered_in_metadata(self):
        assert "batches" in Base.metadata.tables

    def test_id_column_exists(self):
        assert "id" in Batch.__table__.columns

    def test_id_is_integer(self):
        assert isinstance(Batch.__table__.c.id.type, Integer)

    def test_id_is_primary_key(self):
        assert Batch.__table__.c.id.primary_key is True

    def test_variant_id_column_exists(self):
        assert "variant_id" in Batch.__table__.columns

    def test_variant_id_is_integer(self):
        assert isinstance(Batch.__table__.c.variant_id.type, Integer)

    def test_variant_id_is_not_null(self):
        assert Batch.__table__.c.variant_id.nullable is False

    def test_variant_id_foreign_key_to_product_variants_id(self):
        fks = list(Batch.__table__.c.variant_id.foreign_keys)
        assert len(fks) == 1
        assert isinstance(fks[0], ForeignKey)
        assert fks[0].parent is Batch.__table__.c.variant_id
        assert fks[0].column.table.name == "product_variants"
        assert fks[0].column.name == "id"

    def test_batch_number_column_exists(self):
        assert "batch_number" in Batch.__table__.columns

    def test_batch_number_is_string_100(self):
        assert isinstance(Batch.__table__.c.batch_number.type, String)
        assert Batch.__table__.c.batch_number.type.length == 100

    def test_batch_number_is_nullable(self):
        assert Batch.__table__.c.batch_number.nullable is True

    def test_batch_number_is_not_unique(self):
        assert not [
            uc
            for uc in Batch.__table__.constraints
            if type(uc).__name__ == "UniqueConstraint"
        ]
        assert not Batch.__table__.c.batch_number.unique

    def test_manufacture_date_column_exists(self):
        assert "manufacture_date" in Batch.__table__.columns

    def test_manufacture_date_is_date(self):
        assert isinstance(Batch.__table__.c.manufacture_date.type, Date)

    def test_manufacture_date_is_nullable(self):
        assert Batch.__table__.c.manufacture_date.nullable is True

    def test_quantity_column_exists(self):
        assert "quantity" in Batch.__table__.columns

    def test_quantity_is_numeric(self):
        assert isinstance(Batch.__table__.c.quantity.type, Numeric)

    def test_quantity_python_type_is_decimal(self):
        assert Batch.__table__.c.quantity.type.python_type is Decimal

    def test_quantity_is_nullable(self):
        assert Batch.__table__.c.quantity.nullable is True

    def test_quantity_unit_column_exists(self):
        assert "quantity_unit" in Batch.__table__.columns

    def test_quantity_unit_is_string_30(self):
        assert isinstance(Batch.__table__.c.quantity_unit.type, String)
        assert Batch.__table__.c.quantity_unit.type.length == 30

    def test_quantity_unit_is_nullable(self):
        assert Batch.__table__.c.quantity_unit.nullable is True


class TestBatchObject:
    def test_batch_in_memory_preserves_values(self):
        variant = ProductVariant(size_text="Ø63 × 5.8")
        batch = Batch(
            variant=variant,
            batch_number="Б-2026-014",
            manufacture_date=date(2026, 3, 14),
            quantity=Decimal("288"),
            quantity_unit="шт",
        )
        assert batch.id is None
        assert batch.variant_id is None
        assert batch.batch_number == "Б-2026-014"
        assert batch.manufacture_date == date(2026, 3, 14)
        assert batch.quantity == Decimal("288")
        assert batch.quantity_unit == "шт"
        assert batch.variant is variant

    def test_batch_with_only_required_fields(self):
        variant = ProductVariant(size_text="Ду50")
        batch = Batch(variant=variant)
        assert batch.batch_number is None
        assert batch.manufacture_date is None
        assert batch.quantity is None
        assert batch.quantity_unit is None

    def test_product_variant_batches_relationship(self):
        product = Product(name="Труба ПЭ 100", standard="ГОСТ 58121.2-2018")
        variant = ProductVariant(product=product, size_text="Ø63 × 5.8")
        first = Batch(variant=variant, batch_number="Б-1", quantity=Decimal("100"))
        second = Batch(
            variant=variant,
            batch_number="Б-2",
            quantity=Decimal("50"),
            quantity_unit="шт",
        )

        assert variant.batches == [first, second]
        assert first.variant is variant
        assert second.variant is variant