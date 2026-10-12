from sqlalchemy import Integer, String

from app.models import Base, DocumentType


class TestDocumentTypeTable:
    def test_table_name(self):
        assert DocumentType.__tablename__ == "document_types"

    def test_registered_in_metadata(self):
        assert "document_types" in Base.metadata.tables

    def test_id_column_exists(self):
        assert "id" in DocumentType.__table__.columns

    def test_id_is_integer(self):
        assert isinstance(DocumentType.__table__.c.id.type, Integer)

    def test_id_is_primary_key(self):
        assert DocumentType.__table__.c.id.primary_key is True

    def test_name_column_exists(self):
        assert "name" in DocumentType.__table__.columns

    def test_name_is_string_100(self):
        assert isinstance(DocumentType.__table__.c.name.type, String)
        assert DocumentType.__table__.c.name.type.length == 100

    def test_name_is_not_null(self):
        assert DocumentType.__table__.c.name.nullable is False

    def test_name_is_unique(self):
        assert DocumentType.__table__.c.name.unique is True

    def test_unique_constraint_on_name(self):
        unique_columns = [
            [col.name for col in uc.columns]
            for uc in DocumentType.__table__.constraints
            if type(uc).__name__ == "UniqueConstraint"
        ]
        assert ["name"] in unique_columns

    def test_no_extra_columns(self):
        assert set(DocumentType.__table__.columns.keys()) == {"id", "name"}


class TestDocumentTypeObject:
    def test_document_type_in_memory_preserves_name(self):
        document_type = DocumentType(name="Сертификат соответствия")
        assert document_type.id is None
        assert document_type.name == "Сертификат соответствия"

    def test_document_type_with_plain_name(self):
        document_type = DocumentType(name="Паспорт")
        assert document_type.name == "Паспорт"

    def test_known_document_type_names_fit_100_chars(self):
        for name in (
            "Паспорт",
            "Паспорт качества",
            "Сертификат качества",
            "Сертификат соответствия",
            "Декларация соответствия",
            "Свидетельство",
            "Свидетельство НАКС",
            "Другой документ",
        ):
            assert len(name) <= 100
            assert DocumentType(name=name).name == name