from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.batches.schemas import BatchCreate, BatchUpdate
from app.models import Batch, Manufacturer, Product, ProductVariant
from app.services.batch_service import (
    BatchService, BatchServiceError, VariantNotFoundError, _is_variant_fk_violation,
)


@pytest.fixture
def variants(db):
    manufacturer = Manufacturer(name="Batch maker")
    products = [Product(name=f"Product {i} SDR{i}", standard="GOST", manufacturer=manufacturer) for i in (11, 17)]
    rows = [ProductVariant(product=products[0], size_text="63"), ProductVariant(product=products[0], size_text="90"), ProductVariant(product=products[1], size_text="63")]
    db.add_all(rows)
    db.commit()
    return rows


@pytest.fixture
def make_batch(db, variants):
    def make(**kwargs):
        return BatchService.create(db, BatchCreate(**{"variant_id": variants[0].id, **kwargs}))
    return make


class TestCreate:
    def test_minimal_and_full_roundtrip(self, db, variants):
        minimal = BatchService.create(db, BatchCreate(variant_id=variants[0].id))
        full = BatchService.create(db, BatchCreate(variant_id=variants[1].id, batch_number=" B ", manufacture_date="2099-02-28", quantity="5", quantity_unit=" шт "))
        ids = minimal.id, full.id
        db.expire_all()
        first, second = [db.get(Batch, key) for key in ids]
        assert first.variant_id == variants[0].id
        assert (first.batch_number, first.manufacture_date, first.quantity, first.quantity_unit) == (None, None, None, None)
        assert (second.batch_number, second.manufacture_date, second.quantity, second.quantity_unit) == ("B", date(2099, 2, 28), Decimal("5.00"), "шт")
        assert second.quantity.as_tuple().exponent == -2
        assert db.scalar(select(func.count()).select_from(Product)) == 2
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 3
        assert db.scalar(select(func.count()).select_from(Manufacturer)) == 1

    @pytest.mark.parametrize("quantity", ["0.01", "99999999.99"])
    def test_quantity_boundaries_persist(self, db, make_batch, quantity):
        key = make_batch(quantity=quantity).id
        db.expire_all()
        assert db.get(Batch, key).quantity == Decimal(quantity)

    def test_duplicates_and_nulls_are_distinct_rows(self, db, make_batch, variants):
        rows = [make_batch(batch_number="B", quantity="5") for _ in range(2)]
        rows.append(make_batch(variant_id=variants[2].id, batch_number="B", quantity="5"))
        rows.extend([make_batch(), make_batch()])
        assert len({row.id for row in rows}) == 5
        db.expire_all()
        assert db.scalar(select(func.count()).select_from(Batch)) == 5

    def test_unknown_variant(self, db):
        with pytest.raises(VariantNotFoundError) as caught:
            BatchService.create(db, BatchCreate(variant_id=999999))
        assert caught.value.variant_id == 999999
        assert isinstance(caught.value, BatchServiceError)
        assert db.scalar(select(func.count()).select_from(Batch)) == 0


class TestGetAndList:
    def test_empty_missing_and_no_delete(self, db):
        assert BatchService.list(db) == []
        assert BatchService.get_by_id(db, -1) is None
        assert not hasattr(BatchService, "delete")

    def test_global_id_order_and_sql_pagination(self, db, variants):
        rows = [Batch(variant_id=variants[i % 3].id, batch_number=f"{60 - i:03}") for i in range(55)]
        db.add_all(rows)
        db.commit()
        ids = [row.id for row in rows]
        db.expire_all()
        assert [row.id for row in BatchService.list(db)] == ids[:50]
        assert [row.id for row in BatchService.list(db, limit=2, offset=1)] == ids[1:3]
        assert len(BatchService.list(db, limit=100)) == 55
        assert BatchService.list(db, offset=55) == []
        assert BatchService.get_by_id(db, ids[0]).batch_number == "060"
        # Observe the executed SQL as well as the resulting page.
        from sqlalchemy import event
        statements = []
        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)
        event.listen(db.bind, "before_cursor_execute", capture)
        try:
            BatchService.list(db, limit=2, offset=1)
        finally:
            event.remove(db.bind, "before_cursor_execute", capture)
        sql = statements[-1].upper()
        assert "ORDER BY BATCHES.ID ASC" in sql and "LIMIT" in sql and "OFFSET" in sql
        assert "JOIN" not in sql and "WHERE" not in sql


class TestUpdate:
    @pytest.mark.parametrize("target", [1, 2])
    def test_move_variant_preserve_other_tables_and_rows(self, db, variants, make_batch, target):
        batch = make_batch(batch_number="old", quantity="2", manufacture_date="2024-02-29", quantity_unit="m")
        other = make_batch(batch_number="untouched")
        key, other_key = batch.id, other.id
        before = [(v.id, v.product_id, v.size_text) for v in variants]
        BatchService.update(db, key, BatchUpdate(variant_id=variants[target].id, batch_number=" new "))
        db.expire_all()
        stored = db.get(Batch, key)
        assert stored.variant_id == variants[target].id
        assert (stored.batch_number, stored.quantity, stored.manufacture_date, stored.quantity_unit) == ("new", Decimal("2.00"), date(2024, 2, 29), "m")
        assert db.get(Batch, other_key).batch_number == "untouched"
        assert [(v.id, v.product_id, v.size_text) for v in variants] == before
        assert db.scalar(select(func.count()).select_from(Product)) == 2

    @pytest.mark.parametrize("field", ["batch_number", "manufacture_date", "quantity", "quantity_unit"])
    def test_null_clears_only_present_field(self, db, make_batch, field):
        batch = make_batch(batch_number="B", manufacture_date="2024-02-29", quantity="3", quantity_unit="m")
        before = {name: getattr(batch, name) for name in ("batch_number", "manufacture_date", "quantity", "quantity_unit")}
        key = batch.id
        BatchService.update(db, key, BatchUpdate(**{field: None}))
        db.expire_all()
        stored = db.get(Batch, key)
        assert {name: getattr(stored, name) for name in before} == {**before, field: None}

    def test_duplicate_update_and_empty(self, db, make_batch):
        first, second = make_batch(batch_number="B"), make_batch(batch_number="C")
        assert BatchService.update(db, second.id, BatchUpdate(batch_number="B")).batch_number == first.batch_number
        assert BatchService.update(db, first.id, BatchUpdate()) is first

    def test_unknown_batch_precedes_unknown_variant(self, db):
        assert BatchService.update(db, 999999, BatchUpdate(variant_id=999999)) is None

    def test_unknown_variant_changes_nothing(self, db, make_batch):
        batch = make_batch(batch_number="old", quantity="2")
        key, variant_id = batch.id, batch.variant_id
        with pytest.raises(VariantNotFoundError):
            BatchService.update(db, key, BatchUpdate(variant_id=999999, batch_number="new", quantity=None))
        assert batch not in db.dirty
        assert (batch.variant_id, batch.batch_number, batch.quantity) == (variant_id, "old", Decimal("2.00"))
        db.expire_all()
        assert db.get(Batch, key).batch_number == "old"


class TestTransactionsAndErrors:
    def test_commit_counts_real_commit(self, db, variants, monkeypatch):
        commit = Mock(wraps=db.commit)
        monkeypatch.setattr(db, "commit", commit)
        batch = BatchService.create(db, BatchCreate(variant_id=variants[0].id))
        assert commit.call_count == 1
        commit.reset_mock()
        BatchService.update(db, batch.id, BatchUpdate(quantity="5"))
        assert commit.call_count == 1
        commit.reset_mock()
        BatchService.update(db, batch.id, BatchUpdate(quantity="5"))
        assert commit.call_count == 1
        commit.reset_mock()
        BatchService.get_by_id(db, batch.id)
        BatchService.list(db)
        BatchService.update(db, batch.id, BatchUpdate())
        BatchService.update(db, 999999, BatchUpdate(variant_id=999999))
        for operation in [
            lambda: BatchService.create(db, BatchCreate(variant_id=999999)),
            lambda: BatchService.update(db, batch.id, BatchUpdate(variant_id=999999, quantity=None)),
        ]:
            with pytest.raises(VariantNotFoundError):
                operation()
        assert commit.call_count == 0

    @pytest.mark.parametrize("operation", ["create", "update"])
    def test_real_fk_race_rolls_back_and_session_reusable(self, db, make_batch, monkeypatch, operation):
        original = make_batch(batch_number="old", quantity="5")
        key, old_variant = original.id, original.variant_id
        commit = Mock(wraps=db.commit)
        rollback = Mock(wraps=db.rollback)
        monkeypatch.setattr(db, "commit", commit)
        monkeypatch.setattr(db, "rollback", rollback)
        monkeypatch.setattr(BatchService, "_require_variant", staticmethod(lambda *_: None))
        with pytest.raises(VariantNotFoundError) as caught:
            if operation == "create":
                BatchService.create(db, BatchCreate(variant_id=999999, batch_number="new"))
            else:
                BatchService.update(db, key, BatchUpdate(variant_id=999999, batch_number="new", quantity=None))
        assert caught.value.variant_id == 999999
        assert isinstance(caught.value.__cause__, IntegrityError)
        assert _is_variant_fk_violation(caught.value.__cause__)
        assert commit.call_count == rollback.call_count == 1
        db.expire_all()
        stored = db.get(Batch, key)
        assert (stored.variant_id, stored.batch_number, stored.quantity) == (old_variant, "old", Decimal("5.00"))
        assert db.scalar(select(func.count()).select_from(Batch)) == 1
        BatchService.update(db, key, BatchUpdate(batch_number="recovered"))
        db.expire_all()
        assert db.get(Batch, key).batch_number == "recovered"

    @pytest.mark.parametrize("sql,expected", [
        ("INSERT INTO batches (variant_id) VALUES (999999)", True),
        ("INSERT INTO product_variants (product_id, size_text) VALUES (999999, 'x')", False),
        ("INSERT INTO batches (variant_id) VALUES (NULL)", False),
        ("INSERT INTO product_variants (product_id, size_text) SELECT product_id, size_text FROM product_variants LIMIT 1", False),
        ("INSERT INTO batches (id, variant_id) SELECT id, variant_id FROM batches LIMIT 1", False),
    ])
    def test_classifier_with_real_postgres_errors(self, db, make_batch, sql, expected):
        make_batch()
        with pytest.raises(IntegrityError) as caught:
            db.execute(text(sql))
        db.rollback()
        assert _is_variant_fk_violation(caught.value) is expected
        assert db.scalar(text("SELECT 1")) == 1

    @pytest.mark.parametrize("kind", ["unique", "not_null", "check", "other_fk", "generic"])
    def test_other_commit_errors_rollback_and_reraise_without_retry(self, db, make_batch, monkeypatch, kind):
        batch = make_batch(batch_number="old")
        key = batch.id
        if kind == "generic":
            error = SQLAlchemyError("unexpected")
        else:
            # Generate real diagnostics in the scratch schema; no model/migration changes.
            if kind == "check":
                db.execute(text("CREATE TEMP TABLE batch_error_probe (n int CHECK (n > 0))"))
            sql = {
                "unique": "INSERT INTO batches (id, variant_id) SELECT id, variant_id FROM batches LIMIT 1",
                "not_null": "INSERT INTO batches (variant_id) VALUES (NULL)",
                "other_fk": "INSERT INTO product_variants (product_id, size_text) VALUES (999999, 'x')",
                "check": "INSERT INTO batch_error_probe VALUES (-1)",
            }[kind]
            with pytest.raises(IntegrityError) as caught:
                db.execute(text(sql))
            db.rollback()
            error = caught.value
        assert not _is_variant_fk_violation(error)
        commit = Mock(side_effect=error)
        rollback = Mock(wraps=db.rollback)
        monkeypatch.setattr(db, "commit", commit)
        monkeypatch.setattr(db, "rollback", rollback)
        with pytest.raises(SQLAlchemyError) as caught:
            BatchService.update(db, key, BatchUpdate(batch_number="new"))
        assert caught.value is error
        assert commit.call_count == rollback.call_count == 1
        db.expire_all()
        assert db.get(Batch, key).batch_number == "old"
