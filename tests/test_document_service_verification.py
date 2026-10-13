"""Verification lifecycle of DocumentService: status changes and their history.

Every status change must land together with the event that explains it, so
each test checks both the stored `verification_status` and the row in
`document_verification_events` — a status without a history row is exactly the
bug this stage exists to prevent.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.documents.schemas import DocumentCreate, DocumentUpdate
from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.file import File
from app.services.document_service import (
    PENDING,
    REJECTED,
    VERIFIED,
    DocumentHasNoFilesError,
    DocumentService,
    RejectionReasonRequiredError,
)

REASON = "не соответствует ГОСТ 58121.2-2018"


@pytest.fixture
def document_type(db: Session) -> DocumentType:
    row = DocumentType(name="Паспорт")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def make_document(db: Session, document_type: DocumentType):
    counter = {"n": 0}

    def _make(number: str | None = None) -> Document:
        counter["n"] += 1
        return DocumentService.create(
            db,
            DocumentCreate(
                document_type_id=document_type.id,
                number=number or f"ПС-{counter['n']:03d}",
            ),
        )

    return _make


@pytest.fixture
def attach_file(db: Session):
    """Register a file row the way FileService would, without touching storage."""

    def _attach(document: Document, filename: str = "passport.pdf") -> File:
        row = File(
            document_id=document.id,
            original_filename=filename,
            storage_key=f"documents/{document.id}/{filename}",
            mime_type="application/pdf",
            size_bytes=1024,
            sha256="0" * 64,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _attach


@pytest.fixture
def make_verified(db: Session, make_document, attach_file):
    def _make(number: str | None = None) -> Document:
        document = attach_file(make_document(number))
        return DocumentService.verify(db, document.id, reason="проверен")

    return _make


def events_of(db: Session, document_id: int) -> list[dict]:
    rows = db.execute(
        text(
            "SELECT id, from_status, to_status, event_type, reason "
            "FROM document_verification_events WHERE document_id = :i "
            "ORDER BY created_at, id"
        ),
        {"i": document_id},
    ).fetchall()
    return [
        {
            "id": r[0],
            "from_status": r[1],
            "to_status": r[2],
            "event_type": r[3],
            "reason": r[4],
        }
        for r in rows
    ]


def stored_status(db: Session, document_id: int) -> str:
    db.expire_all()
    return db.get(Document, document_id).verification_status


class TestVerify:
    def test_pending_to_verified_with_file(self, db, make_document, attach_file):
        document = attach_file(make_document())
        assert DocumentService.verify(db, document.id).verification_status == VERIFIED
        assert stored_status(db, document.id) == VERIFIED
        assert events_of(db, document.id) == [
            {
                "id": events_of(db, document.id)[0]["id"],
                "from_status": PENDING,
                "to_status": VERIFIED,
                "event_type": "verified",
                "reason": None,
            }
        ]

    def test_verified_without_file_is_refused(self, db, make_document):
        document = make_document()
        with pytest.raises(DocumentHasNoFilesError) as info:
            DocumentService.verify(db, document.id)
        assert info.value.document_id == document.id
        assert stored_status(db, document.id) == PENDING
        assert events_of(db, document.id) == []

    def test_refusal_writes_nothing(self, db, make_document):
        document = make_document()
        with pytest.raises(DocumentHasNoFilesError):
            DocumentService.verify(db, document.id)
        assert db.execute(text("SELECT count(*) FROM document_verification_events")).scalar() == 0

    def test_rejected_to_verified_directly(self, db, make_document, attach_file):
        document = attach_file(make_document())
        DocumentService.reject(db, document.id, reason=REASON)
        verified = DocumentService.verify(db, document.id)
        assert verified.verification_status == VERIFIED
        assert [(e["from_status"], e["to_status"], e["event_type"]) for e in events_of(db, document.id)] == [
            (PENDING, REJECTED, "rejected"),
            (REJECTED, VERIFIED, "verified"),
        ]

    def test_reason_is_stored_when_given(self, db, make_document, attach_file):
        document = attach_file(make_document())
        DocumentService.verify(db, document.id, reason="по протоколу 17")
        assert events_of(db, document.id)[0]["reason"] == "по протоколу 17"

    def test_one_event_only(self, db, make_document, attach_file):
        document = attach_file(make_document())
        DocumentService.verify(db, document.id)
        assert len(events_of(db, document.id)) == 1

    def test_repeated_verify_creates_no_event(self, db, make_verified):
        document = make_verified()
        again = DocumentService.verify(db, document.id, reason="повторно")
        assert again.verification_status == VERIFIED
        assert len(events_of(db, document.id)) == 1

    def test_repeated_verify_does_not_commit(self, db, make_verified, monkeypatch):
        document = make_verified()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentService.verify(db, document.id)
        assert calls == []

    def test_unknown_document_returns_none(self, db):
        assert DocumentService.verify(db, 999999) is None

    def test_file_of_another_document_does_not_count(
        self, db, make_document, attach_file
    ):
        first = attach_file(make_document())
        second = make_document()
        with pytest.raises(DocumentHasNoFilesError):
            DocumentService.verify(db, second.id)
        assert stored_status(db, first.id) == PENDING


class TestReject:
    def test_pending_to_rejected_with_reason(self, db, make_document):
        document = make_document()
        assert DocumentService.reject(db, document.id, REASON).verification_status == (
            REJECTED
        )
        assert stored_status(db, document.id) == REJECTED
        assert events_of(db, document.id) == [
            {
                "id": events_of(db, document.id)[0]["id"],
                "from_status": PENDING,
                "to_status": REJECTED,
                "event_type": "rejected",
                "reason": REASON,
            }
        ]

    def test_rejected_without_reason_is_refused(self, db, make_document):
        document = make_document()
        with pytest.raises(RejectionReasonRequiredError):
            DocumentService.reject(db, document.id, "")
        assert stored_status(db, document.id) == PENDING
        assert events_of(db, document.id) == []

    @pytest.mark.parametrize("reason", [None, "   ", "\t", "\n", " \t\n "])
    def test_blank_reason_is_refused(self, db, make_document, reason):
        document = make_document()
        with pytest.raises(RejectionReasonRequiredError):
            DocumentService.reject(db, document.id, reason)
        assert events_of(db, document.id) == []

    def test_verified_to_rejected_directly(self, db, make_verified):
        document = make_verified()
        DocumentService.reject(db, document.id, reason=REASON)
        assert stored_status(db, document.id) == REJECTED
        assert [(e["from_status"], e["to_status"], e["event_type"]) for e in events_of(db, document.id)] == [
            (PENDING, VERIFIED, "verified"),
            (VERIFIED, REJECTED, "rejected"),
        ]

    def test_reason_is_kept_verbatim(self, db, make_document):
        document = make_document()
        DocumentService.reject(db, document.id, reason=f"  {REASON}  ")
        assert events_of(db, document.id)[0]["reason"] == f"  {REASON}  "

    def test_repeated_reject_creates_no_event(self, db, make_document):
        document = make_document()
        DocumentService.reject(db, document.id, reason=REASON)
        again = DocumentService.reject(db, document.id, reason=REASON)
        assert again.verification_status == REJECTED
        assert len(events_of(db, document.id)) == 1

    def test_repeated_reject_with_other_reason_leaves_history(
        self, db, make_document
    ):
        document = make_document()
        DocumentService.reject(db, document.id, reason=REASON)
        DocumentService.reject(db, document.id, reason="другое объяснение")
        history = events_of(db, document.id)
        assert len(history) == 1
        assert history[0]["reason"] == REASON

    def test_repeated_reject_does_not_commit(self, db, make_document, monkeypatch):
        document = make_document()
        DocumentService.reject(db, document.id, reason=REASON)
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentService.reject(db, document.id, reason=REASON)
        assert calls == []

    def test_unknown_document_returns_none(self, db):
        assert DocumentService.reject(db, 999999, REASON) is None


class TestReopeningOnUpdate:
    def test_verified_to_pending_records_reopened(self, db, make_verified):
        document = make_verified()
        DocumentService.update(db, document.id, DocumentUpdate(number="ПС-900"))
        assert stored_status(db, document.id) == PENDING
        reopened = events_of(db, document.id)[-1]
        assert reopened["from_status"] == VERIFIED
        assert reopened["to_status"] == PENDING
        assert reopened["event_type"] == "reopened"
        assert reopened["reason"] is None

    def test_rejected_to_pending_records_reopened(self, db, make_document):
        document = make_document()
        DocumentService.reject(db, document.id, reason=REASON)
        DocumentService.update(db, document.id, DocumentUpdate(number="ПС-901"))
        assert stored_status(db, document.id) == PENDING
        reopened = events_of(db, document.id)[-1]
        assert reopened["from_status"] == REJECTED
        assert reopened["event_type"] == "reopened"

    @pytest.mark.parametrize(
        "change",
        [
            {"number": "ПС-910"},
            {"issue_date": "2026-05-05"},
            {"valid_from": "2026-05-05"},
            {"valid_to": "2030-05-05"},
        ],
    )
    def test_every_significant_requisite_reopens(self, db, make_verified, change):
        document = make_verified()
        DocumentService.update(db, document.id, DocumentUpdate(**change))
        assert events_of(db, document.id)[-1]["event_type"] == "reopened"

    def test_notes_only_change_keeps_the_status(self, db, make_verified):
        document = make_verified()
        updated = DocumentService.update(db, document.id, DocumentUpdate(notes="правка"))
        assert updated.verification_status == VERIFIED
        assert stored_status(db, document.id) == VERIFIED
        assert len(events_of(db, document.id)) == 1

    def test_notes_only_change_on_rejected(self, db, make_document):
        document = make_document()
        DocumentService.reject(db, document.id, reason=REASON)
        DocumentService.update(db, document.id, DocumentUpdate(notes="правка"))
        assert stored_status(db, document.id) == REJECTED
        assert len(events_of(db, document.id)) == 1

    def test_identical_values_create_no_event(self, db, make_verified):
        document = make_verified()
        current = db.get(Document, document.id).number
        DocumentService.update(db, document.id, DocumentUpdate(number=current))
        assert stored_status(db, document.id) == VERIFIED
        assert len(events_of(db, document.id)) == 1

    def test_identical_values_do_not_commit(self, db, make_verified, monkeypatch):
        document = make_verified()
        current = db.get(Document, document.id).number
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentService.update(db, document.id, DocumentUpdate(number=current))
        assert calls == []

    def test_pending_document_gets_no_reopened_event(self, db, make_document):
        document = make_document()
        DocumentService.update(db, document.id, DocumentUpdate(number="ПС-920"))
        assert stored_status(db, document.id) == PENDING
        assert events_of(db, document.id) == []

    def test_empty_patch_creates_no_event(self, db, make_verified):
        document = make_verified()
        DocumentService.update(db, document.id, DocumentUpdate())
        assert len(events_of(db, document.id)) == 1

    def test_one_event_per_reopening(self, db, make_verified):
        document = make_verified()
        DocumentService.update(db, document.id, DocumentUpdate(number="ПС-930"))
        DocumentService.update(db, document.id, DocumentUpdate(number="ПС-931"))
        reopened = [e for e in events_of(db, document.id) if e["event_type"] == "reopened"]
        assert len(reopened) == 1


class TestCreationWritesNoHistory:
    def test_new_document_has_no_events(self, db, make_document):
        document = make_document()
        assert events_of(db, document.id) == []

    def test_new_document_is_pending(self, db, make_document):
        assert stored_status(db, make_document().id) == PENDING

    def test_document_with_file_is_still_pending(self, db, make_document, attach_file):
        document = attach_file(make_document())
        assert stored_status(db, document.id) == PENDING
        assert events_of(db, document.id) == []


class TestAtomicity:
    @staticmethod
    def poison(monkeypatch, session):
        """Make the event row itself violate its CHECK at flush time.

        Failing inside `db.add` would never reach `_commit`, so the service's
        rollback would not run and the test would prove nothing. Poisoning the
        value instead makes the real commit flush the document UPDATE, hit the
        CHECK violation, and roll both back through the production path.
        """
        from app.models.document_verification_event import (
            DocumentVerificationEvent,
        )

        real_add = session.add

        def poisoned(instance, *args, **kwargs):
            if isinstance(instance, DocumentVerificationEvent):
                instance.event_type = "approved"  # not in the closed set
            return real_add(instance, *args, **kwargs)

        monkeypatch.setattr(session, "add", poisoned)

    def test_reopening_failure_rolls_back_status_and_number(
        self, db, make_verified, monkeypatch
    ):
        from sqlalchemy.exc import IntegrityError

        document = make_verified()
        self.poison(monkeypatch, db)

        with pytest.raises(IntegrityError):
            DocumentService.update(db, document.id, DocumentUpdate(number="ПС-999"))
        monkeypatch.undo()

        db.expire_all()
        stored = db.get(Document, document.id)
        assert stored.number == "ПС-001"
        assert stored.verification_status == VERIFIED
        assert len(events_of(db, document.id)) == 1

    def test_verify_failure_rolls_back_the_status(
        self, db, make_document, attach_file, monkeypatch
    ):
        from sqlalchemy.exc import IntegrityError

        document = attach_file(make_document())
        self.poison(monkeypatch, db)

        with pytest.raises(IntegrityError):
            DocumentService.verify(db, document.id)
        monkeypatch.undo()

        assert stored_status(db, document.id) == PENDING
        assert events_of(db, document.id) == []

    def test_reject_failure_rolls_back_the_status(self, db, make_document, monkeypatch):
        from sqlalchemy.exc import IntegrityError

        document = make_document()
        self.poison(monkeypatch, db)

        with pytest.raises(IntegrityError):
            DocumentService.reject(db, document.id, reason=REASON)
        monkeypatch.undo()

        assert stored_status(db, document.id) == PENDING
        assert events_of(db, document.id) == []

    def test_session_is_usable_after_a_rollback(self, db, make_document, monkeypatch):
        from sqlalchemy.exc import IntegrityError

        document = make_document()
        self.poison(monkeypatch, db)

        with pytest.raises(IntegrityError):
            DocumentService.reject(db, document.id, reason=REASON)
        monkeypatch.undo()

        assert not db.in_transaction()
        again = DocumentService.reject(db, document.id, reason=REASON)
        assert again.verification_status == REJECTED
        assert len(events_of(db, document.id)) == 1

    def test_verify_commits_exactly_once(self, db, make_document, attach_file, monkeypatch):
        document = attach_file(make_document())
        calls = []
        original = db.commit
        monkeypatch.setattr(db, "commit", lambda: (calls.append(1), original()))
        DocumentService.verify(db, document.id)
        assert len(calls) == 1

    def test_reject_commits_exactly_once(self, db, make_document, monkeypatch):
        document = make_document()
        calls = []
        original = db.commit
        monkeypatch.setattr(db, "commit", lambda: (calls.append(1), original()))
        DocumentService.reject(db, document.id, reason=REASON)
        assert len(calls) == 1

    def test_update_with_reopening_commits_exactly_once(
        self, db, make_verified, monkeypatch
    ):
        document = make_verified()
        calls = []
        original = db.commit
        monkeypatch.setattr(db, "commit", lambda: (calls.append(1), original()))
        DocumentService.update(db, document.id, DocumentUpdate(number="ПС-940"))
        assert len(calls) == 1


class TestHistoryPersistence:
    def test_history_survives_later_edits(self, db, make_verified):
        document = make_verified()
        DocumentService.update(db, document.id, DocumentUpdate(number="ПС-950"))
        DocumentService.verify(db, document.id)
        DocumentService.update(db, document.id, DocumentUpdate(notes="правка"))

        history = events_of(db, document.id)
        assert [(e["from_status"], e["to_status"], e["event_type"]) for e in history] == [
            (PENDING, VERIFIED, "verified"),
            (VERIFIED, PENDING, "reopened"),
            (PENDING, VERIFIED, "verified"),
        ]

    def test_events_are_linked_to_the_document(self, db, make_verified):
        document = make_verified()
        other = make_verified()
        history = events_of(db, document.id)
        assert all(e["id"] for e in history)
        assert len(events_of(db, other.id)) == 1
        assert history[0]["id"] != events_of(db, other.id)[0]["id"]

    def test_history_is_ordered_by_time(self, db, make_verified):
        document = make_verified()
        DocumentService.update(db, document.id, DocumentUpdate(number="ПС-951"))
        DocumentService.verify(db, document.id)
        ids = [e["id"] for e in events_of(db, document.id)]
        assert ids == sorted(ids)

    def test_deleting_the_document_removes_its_history(self, db, make_document):
        # a document without attachments, so the ORM has no child row to null
        # out and the database-level ON DELETE CASCADE is what is exercised
        document = make_document()
        DocumentService.reject(db, document.id, reason=REASON)
        document_id = document.id
        assert len(events_of(db, document_id)) == 1

        db.execute(text("DELETE FROM documents WHERE id = :i"), {"i": document_id})
        db.commit()
        assert events_of(db, document_id) == []

    def test_created_at_is_filled_by_the_database(self, db, make_verified):
        document = make_verified()
        stamps = db.execute(
            text(
                "SELECT created_at FROM document_verification_events "
                "WHERE document_id = :i"
            ),
            {"i": document.id},
        ).fetchall()
        assert len(stamps) == 1
        assert stamps[0][0] is not None


class TestServiceContract:
    def test_read_methods_never_commit(self, db, make_document, monkeypatch):
        make_document()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        DocumentService.list(db)
        DocumentService.get(db, 1)
        assert calls == []

    def test_public_surface(self):
        assert {
            "create",
            "get",
            "list",
            "update",
            "verify",
            "reject",
        } <= set(vars(DocumentService))

    def test_new_errors_share_the_base(self):
        assert issubclass(DocumentHasNoFilesError, Exception)
        assert issubclass(RejectionReasonRequiredError, Exception)

    def test_status_still_absent_from_update_schema(self):
        assert "verification_status" not in DocumentUpdate.model_fields