from sqlalchemy import ForeignKey, Integer, String

from app.models import Base, Manufacturer, Product


class TestProductTable:
    def test_table_name(self):
        assert Product.__tablename__ == "products"

    def test_table_registered_in_metadata(self):
        assert "products" in Base.metadata.tables

    def test_id_column_exists(self):
        assert "id" in Product.__table__.columns

    def test_id_is_primary_key(self):
        assert Product.__table__.c.id.primary_key is True

    def test_id_is_integer_type(self):
        assert isinstance(Product.__table__.c.id.type, Integer)

    def test_name_column_exists(self):
        assert "name" in Product.__table__.columns

    def test_name_is_varchar_255(self):
        assert isinstance(Product.__table__.c.name.type, String)
        assert Product.__table__.c.name.type.length == 255

    def test_name_is_not_null(self):
        assert Product.__table__.c.name.nullable is False

    def test_designation_column_exists(self):
        assert "designation" in Product.__table__.columns

    def test_designation_is_varchar_255(self):
        assert isinstance(Product.__table__.c.designation.type, String)
        assert Product.__table__.c.designation.type.length == 255

    def test_designation_is_nullable(self):
        assert Product.__table__.c.designation.nullable is True

    def test_product_type_column_exists(self):
        assert "product_type" in Product.__table__.columns

    def test_product_type_is_varchar_100(self):
        assert isinstance(Product.__table__.c.product_type.type, String)
        assert Product.__table__.c.product_type.type.length == 100

    def test_product_type_is_nullable(self):
        assert Product.__table__.c.product_type.nullable is True

    def test_standard_column_exists(self):
        assert "standard" in Product.__table__.columns

    def test_standard_is_varchar_255(self):
        assert isinstance(Product.__table__.c.standard.type, String)
        assert Product.__table__.c.standard.type.length == 255

    def test_standard_is_not_null(self):
        assert Product.__table__.c.standard.nullable is False

    def test_manufacturer_id_column_exists(self):
        assert "manufacturer_id" in Product.__table__.columns

    def test_manufacturer_id_is_integer(self):
        assert isinstance(Product.__table__.c.manufacturer_id.type, Integer)

    def test_manufacturer_id_is_not_null(self):
        assert Product.__table__.c.manufacturer_id.nullable is False

    def test_manufacturer_id_is_foreign_key_to_manufacturers_id(self):
        fks = list(Product.__table__.c.manufacturer_id.foreign_keys)
        assert len(fks) == 1
        assert isinstance(fks[0], ForeignKey)
        assert fks[0].parent is Product.__table__.c.manufacturer_id
        assert fks[0].column.table.name == "manufacturers"
        assert fks[0].column.name == "id"


class TestProductObject:
    def test_product_in_memory_preserves_values(self):
        manufacturer = Manufacturer(name="ООО Тест")
        product = Product(
            name="Труба ПЭ 100",
            designation="ТРУБА_ПЭ_63х5,8",
            product_type="труба",
            standard="ГОСТ 58121.2-2018",
            manufacturer=manufacturer,
        )
        assert product.id is None
        assert product.name == "Труба ПЭ 100"
        assert product.designation == "ТРУБА_ПЭ_63х5,8"
        assert product.product_type == "труба"
        assert product.standard == "ГОСТ 58121.2-2018"
        assert product.manufacturer is manufacturer

    def test_manufacturer_products_relationship(self):
        manufacturer = Manufacturer(name="ООО Тест")
        product = Product(name="Труба ПЭ 100", manufacturer=manufacturer)
        assert product.manufacturer is manufacturer
        assert manufacturer.products == [product]
        assert product.manufacturer_id is None