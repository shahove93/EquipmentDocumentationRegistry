from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String

from app.models import Base, Manufacturer, Product, ProductVariant


class TestProductVariantTable:
    def test_table_name(self):
        assert ProductVariant.__tablename__ == "product_variants"

    def test_registered_in_metadata(self):
        assert "product_variants" in Base.metadata.tables

    def test_id_column_exists(self):
        assert "id" in ProductVariant.__table__.columns

    def test_id_is_integer(self):
        assert isinstance(ProductVariant.__table__.c.id.type, Integer)

    def test_id_is_primary_key(self):
        assert ProductVariant.__table__.c.id.primary_key is True

    def test_product_id_column_exists(self):
        assert "product_id" in ProductVariant.__table__.columns

    def test_product_id_is_integer(self):
        assert isinstance(ProductVariant.__table__.c.product_id.type, Integer)

    def test_product_id_is_not_null(self):
        assert ProductVariant.__table__.c.product_id.nullable is False

    def test_product_id_foreign_key_to_products_id(self):
        fks = list(ProductVariant.__table__.c.product_id.foreign_keys)
        assert len(fks) == 1
        assert isinstance(fks[0], ForeignKey)
        assert fks[0].parent is ProductVariant.__table__.c.product_id
        assert fks[0].column.table.name == "products"
        assert fks[0].column.name == "id"

    def test_diameter_column_exists(self):
        assert "diameter" in ProductVariant.__table__.columns

    def test_diameter_is_numeric(self):
        assert isinstance(ProductVariant.__table__.c.diameter.type, Numeric)

    def test_diameter_is_nullable(self):
        assert ProductVariant.__table__.c.diameter.nullable is True

    def test_nominal_diameter_column_exists(self):
        assert "nominal_diameter" in ProductVariant.__table__.columns

    def test_nominal_diameter_is_numeric(self):
        assert isinstance(
            ProductVariant.__table__.c.nominal_diameter.type, Numeric
        )

    def test_nominal_diameter_is_nullable(self):
        assert ProductVariant.__table__.c.nominal_diameter.nullable is True

    def test_wall_thickness_column_exists(self):
        assert "wall_thickness" in ProductVariant.__table__.columns

    def test_wall_thickness_is_numeric(self):
        assert isinstance(
            ProductVariant.__table__.c.wall_thickness.type, Numeric
        )

    def test_wall_thickness_is_nullable(self):
        assert ProductVariant.__table__.c.wall_thickness.nullable is True

    def test_size_text_column_exists(self):
        assert "size_text" in ProductVariant.__table__.columns

    def test_size_text_is_string_100(self):
        assert isinstance(ProductVariant.__table__.c.size_text.type, String)
        assert ProductVariant.__table__.c.size_text.type.length == 100

    def test_size_text_is_not_null(self):
        assert ProductVariant.__table__.c.size_text.nullable is False


class TestProductVariantObject:
    def test_variant_in_memory_preserves_values(self):
        product = Product(name="Труба ПЭ 100", standard="ГОСТ 58121.2-2018")
        variant = ProductVariant(
            product=product,
            diameter=Decimal("63"),
            nominal_diameter=Decimal("50"),
            wall_thickness=Decimal("5.8"),
            size_text="Ø63 × 5.8",
        )
        assert variant.id is None
        assert variant.product_id is None
        assert variant.diameter == Decimal("63")
        assert variant.nominal_diameter == Decimal("50")
        assert variant.wall_thickness == Decimal("5.8")
        assert variant.size_text == "Ø63 × 5.8"
        assert variant.product is product

    def test_variant_with_size_text_only(self):
        product = Product(name="Цокольный ввод", standard="ТУ 22.21.29")
        variant = ProductVariant(product=product, size_text="63/57/25")
        assert variant.size_text == "63/57/25"
        assert variant.diameter is None
        assert variant.nominal_diameter is None
        assert variant.wall_thickness is None

    def test_product_variants_relationship(self):
        manufacturer = Manufacturer(name="ООО Тест")
        product = Product(
            name="Труба ПЭ 100",
            standard="ГОСТ 58121.2-2018",
            manufacturer=manufacturer,
        )
        first = ProductVariant(
            product=product, diameter=Decimal("63"), size_text="Ø63 × 5.8"
        )
        second = ProductVariant(
            product=product, nominal_diameter=Decimal("50"), size_text="Ду50"
        )

        assert product.variants == [first, second]
        assert first.product is product
        assert second.product is product