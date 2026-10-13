from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.documents.schemas import DocumentCreate
from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.document_verification_event import DocumentVerificationEvent
from app.services.document_service import DocumentService

PENDING = "pending"
VERIFIED = "verified"
REJECTED = "rejected"
REOPENED = "reopened"


@pytest.fixture
def document(db: Session) -> Document:
    document_type = DocumentType(name="Паспорт")
    db.add(document_type)
    db.commit()
    db.refresh(document_type)
    return DocumentService.create(
        db,
        DocumentCreate(
            document_type_id=document_type.id, number="ПС-001"
        ),
    )


@pytest.fixture
def other_document(db: Session, document: Document) -> Document:
    row = document.document_type_id
    return DocumentService.create(
        db, DocumentCreate(document_type_id=row, number="ПС-002")
    )


@pytest.fixture
def make_event(db: Session, document: Document):
    def _make(**overrides) -> DocumentVerificationEvent:
        payload = {
            "document_id": document.id,
            "from_status": PENDING,
            "to_status": VERIFIED,
            "event_type": VERIFIED,
        }
        payload.update(overrides)
        event = DocumentVerificationEvent(**payload)
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    return _make


def rows(db: Session, document_id: int) -> list[DocumentVerificationEvent]:
    return list(
        db.scalars(
            select(DocumentVerificationEvent)
            .where(DocumentVerificationEvent.document_id == document_id)
            .order_by(
                DocumentVerificationEvent.created_at,
                DocumentVerificationEvent.id,
            )
        )
    )


def count_events(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(DocumentVerificationEvent))


def expect_rejected(db: Session, **overrides):
    """Assert the database refuses the row, then leave the session usable."""
    payload = {
        "document_id": 1,
        "from_status": PENDING,
        "to_status": VERIFIED,
        "event_type": VERIFIED,
    }
    payload.update(overrides)
    db.add(DocumentVerificationEvent(**payload))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


class TestRegistration:
    def test_table_is_registered(self):
        from app.models.base import Base

        assert "document_verification_events" in Base.metadata.tables

    def test_model_is_reexported(self):
        from app.models import DocumentVerificationEvent as Reexported

        assert Reexported is DocumentVerificationEvent
        assert "DocumentVerificationEvent" in __import__(
            "app.models", fromlist=["__all__"]
        ).__all__

    def test_table_exists_in_the_test_schema(self, db):
        found = db.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = current_schema() "
                "AND table_name = 'document_verification_events'"
            )
        ).scalar()
        assert found == 1

    def test_test_session_is_separate_from_public(self, db):
        # The migration has since been applied to the working database, so
        # `public` legitimately has this table too. What must still hold is that
        # the test session never resolves an unqualified name to `public`.
        assert db.execute(text("SELECT current_schema()")).scalar() != "public"
        found = db.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = current_schema() "
                "AND table_name = 'document_verification_events'"
            )
        ).scalar()
        assert found == 1

    def test_search_path_is_the_test_schema(self, db):
        assert db.execute(text("SELECT current_schema()")).scalar() == (
            "test_file_service"
        )


class TestValidEvents:
    def test_verified_event(self, db, document, make_event):
        event = make_event()
        assert isinstance(event, DocumentVerificationEvent)
        assert event.id is not None
        assert event.document_id == document.id
        assert event.from_status == PENDING
        assert event.to_status == VERIFIED
        assert event.event_type == VERIFIED

    def test_verified_from_rejected_is_allowed(self, db, document, make_event):
        event = make_event(from_status=REJECTED, to_status=VERIFIED, event_type=VERIFIED)
        assert event.from_status == REJECTED

    def test_rejected_event_with_reason(self, db, document, make_event):
        event = make_event(
            to_status=REJECTED, event_type=REJECTED, reason="протокол не соответствует"
        )
        assert event.to_status == REJECTED
        assert event.reason == "протокол не соответствует"

    def test_rejected_event_from_verified(self, db, document, make_event):
        event = make_event(
            from_status=VERIFIED,
            to_status=REJECTED,
            event_type=REJECTED,
            reason="ошибка измерения",
        )
        assert event.from_status == VERIFIED

    def test_reopened_from_verified(self, db, document, make_event):
        event = make_event(from_status=VERIFIED, to_status=PENDING, event_type=REOPENED)
        assert event.to_status == PENDING
        assert event.event_type == REOPENED

    def test_reopened_from_rejected(self, db, document, make_event):
        event = make_event(from_status=REJECTED, to_status=PENDING, event_type=REOPENED)
        assert event.from_status == REJECTED

    def test_reason_may_accompany_any_event(self, db, document, make_event):
        assert make_event(reason="по запросу заказчика").reason == (
            "по запросу заказчика"
        )

    def test_reason_is_optional_for_verified(self, db, document, make_event):
        assert make_event().reason is None

    def test_reason_is_optional_for_reopened(self, db, document, make_event):
        event = make_event(from_status=VERIFIED, to_status=PENDING, event_type=REOPENED)
        assert event.reason is None

    def test_row_is_persisted(self, db, document, make_event):
        event = make_event()
        db.expire_all()
        stored = db.get(DocumentVerificationEvent, event.id)
        assert stored is not None
        assert stored.to_status == VERIFIED

    def test_only_expected_columns_written(self, db, make_event):
        event = make_event()
        row = (
            db.execute(
                text("SELECT * FROM document_verification_events WHERE id=:i"),
                {"i": event.id},
            )
            .mappings()
            .one()
        )
        assert set(row) == {
            "id",
            "document_id",
            "from_status",
            "to_status",
            "event_type",
            "reason",
            "created_at",
        }


class TestRequiredFields:
    def test_missing_document_id_rejected(self, db):
        expect_rejected(db, document_id=None)

    def test_document_id_is_required_in_the_model(self):
        assert DocumentVerificationEvent.__table__.columns["document_id"].nullable is (
            False
        )

    def test_missing_from_status_rejected(self, db, document):
        expect_rejected(db, from_status=None)

    def test_missing_to_status_rejected(self, db, document):
        expect_rejected(db, to_status=None)

    def test_missing_event_type_rejected(self, db, document):
        expect_rejected(db, event_type=None)

    def test_foreign_key_to_existing_document(self, db, document, make_event):
        assert make_event().document_id == document.id

    def test_foreign_key_to_unknown_document_rejected(self, db):
        expect_rejected(db, document_id=987654)

    def test_created_at_is_not_nullable(self):
        column = DocumentVerificationEvent.__table__.columns["created_at"]
        assert column.nullable is False
        assert column.server_default is not None


class TestInvalidStatuses:
    def test_invalid_from_status_rejected(self, db, document):
        expect_rejected(db, from_status="archived")

    def test_invalid_to_status_rejected(self, db, document):
        expect_rejected(db, to_status="archived", event_type=REJECTED, reason="x")

    def test_empty_from_status_rejected(self, db, document):
        expect_rejected(db, from_status="")

    def test_invalid_event_type_rejected(self, db, document):
        expect_rejected(db, event_type="approved")

    def test_empty_event_type_rejected(self, db, document):
        expect_rejected(db, event_type="")

    def test_nothing_is_written_when_rejected(self, db, document):
        expect_rejected(db, from_status="archived")
        assert count_events(db) == 0


class TestEventTypeMustMatchTarget:
    @pytest.mark.parametrize("event_type", [VERIFIED, REJECTED, REOPENED])
    def test_verified_event_type_must_reach_verified(self, db, document, event_type):
        expect_rejected(
            db,
            event_type=event_type,
            to_status=VERIFIED,
            reason="причина",
            from_status=PENDING,
        ) if event_type != VERIFIED else expect_rejected(
            db, event_type=event_type, to_status=PENDING, from_status=VERIFIED
        )

    def test_verified_type_reaching_pending_rejected(self, db, document):
        expect_rejected(db, event_type=VERIFIED, to_status=PENDING, from_status=VERIFIED)

    def test_verified_type_reaching_rejected_rejected(self, db, document):
        expect_rejected(
            db,
            event_type=VERIFIED,
            to_status=REJECTED,
            from_status=PENDING,
            reason="x",
        )

    def test_rejected_type_reaching_verified_rejected(self, db, document):
        expect_rejected(
            db,
            event_type=REJECTED,
            to_status=VERIFIED,
            from_status=PENDING,
            reason="x",
        )

    def test_reopened_type_reaching_verified_rejected(self, db, document):
        expect_rejected(
            db, event_type=REOPENED, to_status=VERIFIED, from_status=REJECTED
        )

    def test_reopened_type_reaching_rejected_rejected(self, db, document):
        expect_rejected(
            db,
            event_type=REOPENED,
            to_status=REJECTED,
            from_status=VERIFIED,
            reason="x",
        )


class TestRejectedRequiresReason:
    def test_rejected_without_reason_rejected(self, db, document):
        expect_rejected(db, event_type=REJECTED, to_status=REJECTED, reason=None)

    def test_rejected_with_empty_reason_rejected(self, db, document):
        expect_rejected(db, event_type=REJECTED, to_status=REJECTED, reason="")

    @pytest.mark.parametrize("reason", ["   ", "\t", "\n", " \t\n "])
    def test_rejected_with_whitespace_reason_rejected(self, db, document, reason):
        expect_rejected(db, event_type=REJECTED, to_status=REJECTED, reason=reason)

    def test_rejected_with_meaningful_reason_accepted(self, db, document, make_event):
        event = make_event(
            event_type=REJECTED, to_status=REJECTED, reason="не соответствует ГОСТ"
        )
        assert event.reason == "не соответствует ГОСТ"

    def test_whitespace_is_not_stripped_by_the_database(self, db, document, make_event):
        # btrim is only used to decide whether a reason was given; the stored
        # text is kept verbatim
        event = make_event(
            event_type=REJECTED, to_status=REJECTED, reason="  причина  "
        )
        assert event.reason == "  причина  "

    def test_verified_without_reason_is_fine(self, db, document, make_event):
        assert make_event().reason is None

    def test_reopened_without_reason_is_fine(self, db, document, make_event):
        assert (
            make_event(
                from_status=VERIFIED, to_status=PENDING, event_type=REOPENED
            ).reason
            is None
        )


class TestReopenedOrigin:
    def test_reopened_from_pending_rejected(self, db, document):
        expect_rejected(
            db, event_type=REOPENED, to_status=PENDING, from_status=PENDING
        )

    def test_reopened_from_verified_accepted(self, db, document, make_event):
        assert make_event(
            event_type=REOPENED, to_status=PENDING, from_status=VERIFIED
        ).from_status == VERIFIED

    def test_reopened_from_rejected_accepted(self, db, document, make_event):
        assert make_event(
            event_type=REOPENED, to_status=PENDING, from_status=REJECTED
        ).from_status == REJECTED


class TestNoSelfTransition:
    def test_same_status_rejected(self, db, document):
        expect_rejected(
            db, event_type=VERIFIED, to_status=VERIFIED, from_status=VERIFIED
        )

    def test_pending_to_pending_rejected(self, db, document):
        expect_rejected(
            db, event_type=REOPENED, to_status=PENDING, from_status=PENDING
        )

    def test_rejected_to_rejected_rejected(self, db, document):
        expect_rejected(
            db,
            event_type=REJECTED,
            to_status=REJECTED,
            from_status=REJECTED,
            reason="x",
        )

    def test_constraint_name_reported(self, db, document):
        db.add(
            DocumentVerificationEvent(
                document_id=document.id,
                from_status=VERIFIED,
                to_status=VERIFIED,
                event_type=VERIFIED,
            )
        )
        with pytest.raises(IntegrityError) as info:
            db.commit()
        db.rollback()
        assert info.value.orig.diag.constraint_name == (
            "ck_document_verification_events_status_changed"
        )


class TestCreatedAt:
    def test_created_at_is_filled_by_the_database(self, db, make_event):
        event = make_event()
        assert isinstance(event.created_at, datetime)

    def test_created_at_is_timezone_aware(self, db, make_event):
        # psycopg returns timestamptz in the session time zone, not necessarily
        # UTC; what matters is that the value carries an offset
        created = make_event().created_at
        assert created.tzinfo is not None
        assert created.utcoffset() is not None

    def test_created_at_is_close_to_now(self, db, make_event):
        # now() is the transaction timestamp, which may predate this line, so
        # the window is deliberately generous
        created = make_event().created_at
        delta = abs((datetime.now(timezone.utc) - created).total_seconds())
        assert delta < 3600

    def test_created_at_can_be_set_explicitly(self, db, make_event):
        moment = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        assert make_event(created_at=moment).created_at == moment

    def test_storage_round_trips_the_timestamp(self, db, make_event):
        moment = datetime(2026, 3, 1, 12, 30, tzinfo=timezone.utc)
        event = make_event(created_at=moment)
        db.expire_all()
        stored = db.get(DocumentVerificationEvent, event.id).created_at
        # aware datetimes compare by instant, so this asserts the same point in
        # time even though psycopg returns it in the session time zone
        assert stored == moment
        assert stored.tzinfo is not None


class TestHistoryOrdering:
    def test_events_are_returned_in_chronological_order(
        self, db, document, make_event
    ):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        make_event(created_at=base + timedelta(hours=3))
        make_event(
            from_status=VERIFIED,
            to_status=REJECTED,
            event_type=REJECTED,
            reason="причина",
            created_at=base,
        )
        make_event(
            from_status=REJECTED,
            to_status=PENDING,
            event_type=REOPENED,
            created_at=base + timedelta(hours=1),
        )
        listed = rows(db, document.id)
        assert [e.created_at for e in listed] == [
            base,
            base + timedelta(hours=1),
            base + timedelta(hours=3),
        ]

    def test_identical_timestamps_are_broken_by_id(self, db, document, make_event):
        moment = datetime(2026, 5, 5, tzinfo=timezone.utc)
        for index in range(5):
            make_event(created_at=moment, reason=f"шаг {index}")
        listed = rows(db, document.id)
        assert [e.id for e in listed] == sorted(e.id for e in listed)

    def test_history_is_scoped_to_one_document(
        self, db, document, other_document, make_event
    ):
        make_event()
        db.add(
            DocumentVerificationEvent(
                document_id=other_document.id,
                from_status=PENDING,
                to_status=VERIFIED,
                event_type=VERIFIED,
            )
        )
        db.commit()
        assert len(rows(db, document.id)) == 1
        assert len(rows(db, other_document.id)) == 1
        assert count_events(db) == 2

    def test_document_without_events_returns_nothing(
        self, db, document, other_document
    ):
        assert rows(db, other_document.id) == []

    def test_index_exists_in_the_test_schema(self, db):
        found = db.execute(
            text(
                "SELECT count(*) FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND indexname = "
                "'ix_document_verification_events_document_id_created_at_id'"
            )
        ).scalar()
        assert found == 1


class TestCascadeDelete:
    def test_deleting_a_document_removes_its_events(self, db, document, make_event):
        make_event()
        assert count_events(db) == 1
        db.delete(db.get(Document, document.id))
        db.commit()
        assert count_events(db) == 0

    def test_cascade_removes_the_whole_history(self, db, document, make_event):
        make_event()
        make_event(
            from_status=VERIFIED, to_status=REJECTED, event_type=REJECTED, reason="x"
        )
        make_event(
            from_status=REJECTED, to_status=PENDING, event_type=REOPENED
        )
        assert count_events(db) == 3
        db.delete(db.get(Document, document.id))
        db.commit()
        assert count_events(db) == 0

    def test_other_documents_keep_their_history(
        self, db, document, other_document, make_event
    ):
        make_event()
        db.add(
            DocumentVerificationEvent(
                document_id=other_document.id,
                from_status=PENDING,
                to_status=VERIFIED,
                event_type=VERIFIED,
            )
        )
        db.commit()
        db.delete(db.get(Document, document.id))
        db.commit()
        assert count_events(db) == 1
        assert len(rows(db, other_document.id)) == 1

    def test_foreign_key_is_declared_as_cascade(self):
        column = DocumentVerificationEvent.__table__.columns["document_id"]
        assert column.foreign_keys.pop().ondelete == "CASCADE"


class TestModelDeclaration:
    def test_expected_columns(self):
        assert set(DocumentVerificationEvent.__table__.columns.keys()) == {
            "id",
            "document_id",
            "from_status",
            "to_status",
            "event_type",
            "reason",
            "created_at",
        }

    def test_column_lengths(self):
        table = DocumentVerificationEvent.__table__
        assert table.columns["from_status"].type.length == 20
        assert table.columns["to_status"].type.length == 20
        assert table.columns["event_type"].type.length == 30

    def test_check_constraint_names(self):
        names = {
            constraint.name
            for constraint in DocumentVerificationEvent.__table__.constraints
            if constraint.__class__.__name__ == "CheckConstraint"
        }
        assert names == {
            "ck_document_verification_events_from_status",
            "ck_document_verification_events_to_status",
            "ck_document_verification_events_event_type",
            "ck_document_verification_events_status_changed",
            "ck_document_verification_events_type_matches_target",
            "ck_document_verification_events_rejected_reason",
            "ck_document_verification_events_reopened_origin",
        }

    def test_index_columns(self):
        index = DocumentVerificationEvent.__table__.indexes.pop()
        assert index.name == (
            "ix_document_verification_events_document_id_created_at_id"
        )
        assert [column.name for column in index.columns] == [
            "document_id",
            "created_at",
            "id",
        ]

    def test_no_relationship_declared_on_document(self):
        # reading the history is always by document_id; a lazy collection would
        # slow every document query for no gain
        assert "verification_events" not in Document.__mapper__.relationships.keys()

    def test_service_writes_the_history(self):
        # TASK-DOC-004 wired the history into DocumentService in the same
        # transaction as the status change, so the service must now reference the
        # event model and the old "gap" warning must be gone.
        import inspect

        from app.services import document_service

        source = inspect.getsource(document_service)
        assert "DocumentVerificationEvent" in source
        assert "_apply_status_transition" in source
        assert "TECHNICAL GAP" not in source


class TestMigrationScript:
    """Static checks only: the revision is never applied to the working database."""

    def _read(self):
        import pathlib

        path = pathlib.Path("alembic/versions/a3f1c72d5b90_create_document_verification_events.py")
        assert path.exists()
        return path.read_text(encoding="utf-8")

    def test_down_revision_chains_to_the_previous_head(self):
        assert "down_revision: Union[str, Sequence[str], None] = '9e6a954d41be'" in (
            self._read()
        )

    def test_creates_only_the_event_table(self):
        source = self._read()
        assert "op.create_table('document_verification_events'" in source
        for table in (
            "documents",
            "products",
            "product_variants",
            "batches",
            "issuers",
            "document_types",
            "files",
        ):
            assert f"op.create_table('{table}'" not in source

    def test_downgrade_drops_only_the_event_table(self):
        source = self._read()
        assert "op.drop_table('document_verification_events')" in source
        assert source.count("op.drop_table") == 1

    def test_declares_every_check_constraint(self):
        source = self._read()
        for name in (
            "ck_document_verification_events_from_status",
            "ck_document_verification_events_to_status",
            "ck_document_verification_events_event_type",
            "ck_document_verification_events_status_changed",
            "ck_document_verification_events_type_matches_target",
            "ck_document_verification_events_rejected_reason",
            "ck_document_verification_events_reopened_origin",
        ):
            assert name in source

    def test_declares_the_index_and_the_cascade(self):
        source = self._read()
        assert (
            "op.create_index('ix_document_verification_events_document_id_created_at_id'"
            in source
        )
        assert "ondelete='CASCADE'" in source

    def test_created_at_uses_a_server_default(self):
        assert "server_default=sa.text('now()')" in self._read()

    def test_existing_revisions_are_untouched(self):
        import pathlib

        revisions = sorted(
            p.name
            for p in pathlib.Path("alembic/versions").glob("*.py")
        )
        assert len(revisions) == 12
        assert revisions[0] == (
            "056121f44e99_create_document_link_tables.py"
        )

    def test_head_is_the_new_revision(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config("alembic.ini")
        script = ScriptDirectory.from_config(config)
        assert script.get_heads() == ["a3f1c72d5b90"]
        assert len(list(script.walk_revisions())) == 12