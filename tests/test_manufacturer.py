from sqlalchemy import Integer, String

from app.models import Base, Manufacturer


class TestManufacturerTable:
    def test_table_name(self):
        assert Manufacturer.__tablename__ == "manufacturers"

    def test_table_registered_in_metadata(self):
        assert "manufacturers" in Base.metadata.tables

    def test_id_column_exists(self):
        assert "id" in Manufacturer.__table__.columns

    def test_id_is_primary_key(self):
        assert Manufacturer.__table__.c.id.primary_key is True

    def test_id_is_integer_type(self):
        assert isinstance(Manufacturer.__table__.c.id.type, Integer)

    def test_name_column_exists(self):
        assert "name" in Manufacturer.__table__.columns

    def test_name_is_varchar_255(self):
        assert isinstance(Manufacturer.__table__.c.name.type, String)
        assert Manufacturer.__table__.c.name.type.length == 255

    def test_name_is_not_null(self):
        assert Manufacturer.__table__.c.name.nullable is False


class TestManufacturerObject:
    def test_manufacturer_in_memory(self):
        manufacturer = Manufacturer(name="ООО Тест")
        assert manufacturer.name == "ООО Тест"
        assert manufacturer.id is None