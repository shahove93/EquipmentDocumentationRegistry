from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text

from app.models import Base, Document, DocumentType, Issuer


class TestDocumentTable:
    def test_table_name(self):
        assert Document.__tablename__ == "documents"

    def test_registered_in_metadata(self):
        assert "documents" in Base.metadata.tables

    def test_id_is_integer_and_primary_key(self):
        assert isinstance(Document.__table__.c.id.type, Integer)
        assert Document.__table__.c.id.primary_key is True

    def test_document_type_id_column(self):
        col = Document.__table__.c.document_type_id
        assert isinstance(col.type, Integer)
        assert col.nullable is False

    def test_document_type_id_foreign_key(self):
        fks = list(Document.__table__.c.document_type_id.foreign_keys)
        assert len(fks) == 1
        assert isinstance(fks[0], ForeignKey)
        assert fks[0].column.table.name == "document_types"
        assert fks[0].column.name == "id"

    def test_number_is_string_100_not_null(self):
        col = Document.__table__.c.number
        assert isinstance(col.type, String)
        assert col.type.length == 100
        assert col.nullable is False

    def test_number_is_not_unique(self):
        assert not Document.__table__.c.number.unique
        assert not [
            uc
            for uc in Document.__table__.constraints
            if type(uc).__name__ == "UniqueConstraint"
        ]

    def test_issue_date_is_date_nullable(self):
        col = Document.__table__.c.issue_date
        assert isinstance(col.type, Date)
        assert col.nullable is True

    def test_valid_from_is_date_nullable(self):
        col = Document.__table__.c.valid_from
        assert isinstance(col.type, Date)
        assert col.nullable is True

    def test_valid_to_is_date_nullable(self):
        col = Document.__table__.c.valid_to
        assert isinstance(col.type, Date)
        assert col.nullable is True

    def test_issuer_id_is_nullable_foreign_key(self):
        col = Document.__table__.c.issuer_id
        assert isinstance(col.type, Integer)
        assert col.nullable is True
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "issuers"
        assert fks[0].column.name == "id"

    def test_verification_status_is_string_30_not_null(self):
        col = Document.__table__.c.verification_status
        assert isinstance(col.type, String)
        assert col.type.length == 30
        assert col.nullable is False

    def test_verification_status_default_is_pending(self):
        assert Document.__table__.c.verification_status.default.arg == "pending"
        assert Document.__table__.c.verification_status.server_default.arg == "pending"

    def test_notes_is_text_nullable(self):
        col = Document.__table__.c.notes
        assert isinstance(col.type, Text)
        assert col.nullable is True

    def test_check_constraints_present(self):
        checks = {
            c.name: str(c.sqltext)
            for c in Document.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        assert "ck_documents_verification_status" in checks
        assert "ck_documents_valid_range" in checks
        assert (
            "verification_status IN ('pending', 'verified', 'rejected')"
            in checks["ck_documents_verification_status"]
        )

    def test_valid_range_check_allows_nulls(self):
        checks = {
            c.name: str(c.sqltext)
            for c in Document.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        expression = checks["ck_documents_valid_range"]
        assert "valid_to IS NULL" in expression
        assert "valid_from IS NULL" in expression
        assert "valid_to >= valid_from" in expression

    def test_no_extra_columns(self):
        assert set(Document.__table__.columns.keys()) == {
            "id",
            "document_type_id",
            "number",
            "issue_date",
            "valid_from",
            "valid_to",
            "issuer_id",
            "verification_status",
            "notes",
        }


class TestDocumentObject:
    def test_document_in_memory_preserves_values(self):
        document_type = DocumentType(name="Паспорт")
        issuer = Issuer(name="ГАЗСЕРТ")
        document = Document(
            document_type=document_type,
            number="ТУ 22.21.29-002-0106727451-2020",
            issue_date=date(2026, 1, 15),
            valid_from=date(2026, 1, 15),
            valid_to=date(2031, 1, 15),
            issuer=issuer,
            verification_status="verified",
            notes="Проверен вручную",
        )
        assert document.id is None
        assert document.number == "ТУ 22.21.29-002-0106727451-2020"
        assert document.issue_date == date(2026, 1, 15)
        assert document.valid_from == date(2026, 1, 15)
        assert document.valid_to == date(2031, 1, 15)
        assert document.verification_status == "verified"
        assert document.notes == "Проверен вручную"
        assert document.document_type is document_type
        assert document.issuer is issuer

    def test_document_defaults_to_pending(self):
        document_type = DocumentType(name="Декларация соответствия")
        document = Document(document_type=document_type, number="Д-1")
        # default применяется при INSERT, поэтому на несброшенном объекте
        # атрибут ещё None; проверяем настройку самого столбца
        column_default = Document.__table__.c.verification_status.default
        assert column_default is not None
        assert column_default.arg == "pending"
        assert document.issuer is None
        assert document.issue_date is None
        assert document.valid_from is None
        assert document.valid_to is None
        assert document.notes is None

    def test_document_type_documents_relationship(self):
        document_type = DocumentType(name="Свидетельство НАКС")
        first = Document(document_type=document_type, number="Н-1")
        second = Document(document_type=document_type, number="Н-2")
        assert document_type.documents == [first, second]
        assert first.document_type is document_type

    def test_issuer_documents_relationship(self):
        issuer = Issuer(name="НАКС")
        first = Document(document_type=DocumentType(name="Паспорт"), number="П-1", issuer=issuer)
        second = Document(document_type=DocumentType(name="Паспорт"), number="П-2", issuer=issuer)
        assert issuer.documents == [first, second]
        assert first.issuer is issuer
        assert second.issuer is issuer