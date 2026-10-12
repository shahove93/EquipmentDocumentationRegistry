from sqlalchemy import Integer, String

from app.models import Base, Issuer


class TestIssuerTable:
    def test_table_name(self):
        assert Issuer.__tablename__ == "issuers"

    def test_registered_in_metadata(self):
        assert "issuers" in Base.metadata.tables

    def test_id_column_exists(self):
        assert "id" in Issuer.__table__.columns

    def test_id_is_integer(self):
        assert isinstance(Issuer.__table__.c.id.type, Integer)

    def test_id_is_primary_key(self):
        assert Issuer.__table__.c.id.primary_key is True

    def test_name_column_exists(self):
        assert "name" in Issuer.__table__.columns

    def test_name_is_string_255(self):
        assert isinstance(Issuer.__table__.c.name.type, String)
        assert Issuer.__table__.c.name.type.length == 255

    def test_name_is_not_null(self):
        assert Issuer.__table__.c.name.nullable is False

    def test_name_is_unique(self):
        assert Issuer.__table__.c.name.unique is True

    def test_unique_constraint_on_name(self):
        unique_columns = [
            [col.name for col in uc.columns]
            for uc in Issuer.__table__.constraints
            if type(uc).__name__ == "UniqueConstraint"
        ]
        assert ["name"] in unique_columns

    def test_no_extra_columns(self):
        assert set(Issuer.__table__.columns.keys()) == {"id", "name"}


class TestIssuerObject:
    def test_issuer_in_memory_preserves_name(self):
        issuer = Issuer(name="ГАЗСЕРТ")
        assert issuer.id is None
        assert issuer.name == "ГАЗСЕРТ"

    def test_issuer_with_long_name(self):
        name = "Общество с ограниченной ответственностью «Норильский сертификационный центр»"
        issuer = Issuer(name=name)
        assert issuer.name == name
        assert len(name) <= 255