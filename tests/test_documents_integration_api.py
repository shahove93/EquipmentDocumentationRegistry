"""End-to-end HTTP walk through a certificate's whole verification lifecycle.

The per-operation modules pin each route's own contract. This module drives the
sequence a real user performs — create a document type, create the document,
attach a scan, confirm it, correct the number, reject it, attach another scan,
confirm again, delete one scan — and checks what only the operations together
can show: the status at every step, the exact number of history rows, the reason
of each `reopened`, and that a download still returns the right bytes.

Two deliberate choices:

* **Only HTTP.** Every step is a request through `TestClient`. No service is
  imported or called to perform the scenario, because the point is precisely
  that the approved lifecycle is reachable for a user, not just from Python.
* **A fresh session per request.** The `client` fixture overrides `get_db` with
  a generator that builds and closes a session for each request, which is what
  `app.database.connection.get_db` does in production. That is what makes the
  "no false `409`" requirement meaningful: if a session were shared and left a
  read transaction open, `FileService.attach` / `detach` would refuse the next
  write. Reads are interleaved with writes throughout to prove they do not.

Everything runs against the scratch schema `test_file_service` and a temporary
storage root; the working database and `storage/` are never touched.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.connection import get_db
from app.main import app

DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"
MAX_BYTES = 64 * 1024

# Two structurally valid, visibly different PDFs: the download check at the end
# would prove nothing if both attachments held identical bytes.
PDF_ONE = (
    b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    b"trailer\n<<>>\n%%EOF\n"
)
PDF_TWO = (
    b"%PDF-1.7\n%\xc7\xec\x8f\xa2\n1 0 obj\n<< /Type /Catalog /Next >>\nendobj\n"
    b"trailer\n<<>>\n%%EOF\n"
)

_MISSING = object()


@pytest.fixture
def client(engine, tmp_path):
    """A client whose every request gets its own session, as in production."""

    def override_get_db():
        session = Session(engine, future=True)
        try:
            yield session
        finally:
            session.close()

    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        STORAGE_ROOT=str(tmp_path / "storage"),
        MAX_UPLOAD_SIZE_BYTES=MAX_BYTES,
    )
    previous_db = app.dependency_overrides.get(get_db, _MISSING)
    previous_settings = app.dependency_overrides.get(get_settings, _MISSING)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        if previous_db is _MISSING:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_db
        if previous_settings is _MISSING:
            app.dependency_overrides.pop(get_settings, None)
        else:
            app.dependency_overrides[get_settings] = previous_settings


# --------------------------------------------------------------------------- #
# HTTP helpers — no service is called anywhere in this module
# --------------------------------------------------------------------------- #


def create_document_type(client: TestClient, name: str | None = None) -> int:
    response = client.post(
        "/document-types", json={"name": name or f"Type {uuid.uuid4().hex[:12]}"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_document(
    client: TestClient, document_type_id: int, number: str
) -> dict:
    response = client.post(
        "/documents", json={"document_type_id": document_type_id, "number": number}
    )
    assert response.status_code == 201, response.text
    return response.json()


def get_document(client: TestClient, document_id: int) -> dict:
    response = client.get(f"/documents/{document_id}")
    assert response.status_code == 200, response.text
    return response.json()


def status_of(client: TestClient, document_id: int) -> str:
    return get_document(client, document_id)["verification_status"]


def list_files(client: TestClient, document_id: int) -> list[dict]:
    response = client.get(f"/documents/{document_id}/files")
    assert response.status_code == 200, response.text
    return response.json()


def upload(
    client: TestClient,
    document_id: int,
    content: bytes,
    filename: str = "scan.pdf",
) -> dict:
    response = client.post(
        f"/documents/{document_id}/files",
        files={"file": (filename, content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    assert response.headers["Location"].endswith(
        f"/documents/{document_id}/files/{response.json()['id']}"
    )
    return response.json()


def decide(
    client: TestClient, document_id: int, decision: str, reason: str | None = None
):
    body: dict[str, object] = {"decision": decision}
    if reason is not None:
        body["reason"] = reason
    return client.post(f"/documents/{document_id}/verification", json=body)


def history(client: TestClient, document_id: int) -> list[dict]:
    response = client.get(f"/documents/{document_id}/verification-history")
    assert response.status_code == 200, response.text
    return response.json()


def tuples(events: list[dict]) -> list[tuple[str, str, str, str | None]]:
    return [
        (row["from_status"], row["to_status"], row["event_type"], row["reason"])
        for row in events
    ]


# --------------------------------------------------------------------------- #
# 3. The full scenario
# --------------------------------------------------------------------------- #


class TestFullCertificateLifecycle:
    def test_end_to_end(self, client):
        # 1. A document type, created the way a user would.
        document_type_id = create_document_type(client, "Сертификат соответствия")

        # 2. Create the document. It is born `pending`, and `Location` points
        #    at its card.
        created = client.post(
            "/documents",
            json={"document_type_id": document_type_id, "number": "CERT-2026-001"},
        )
        assert created.status_code == 201, created.text
        assert created.headers["Location"].endswith("/documents/" + str(created.json()["id"]))
        document_id = created.json()["id"]
        assert created.json()["verification_status"] == "pending"
        assert history(client, document_id) == []

        # 3. Read it back.
        card = get_document(client, document_id)
        assert card["number"] == "CERT-2026-001"
        assert card["verification_status"] == "pending"

        # 4. Attach the scan.
        first = upload(client, document_id, PDF_ONE, "certificate.pdf")
        assert first["document_id"] == document_id
        assert first["original_filename"] == "certificate.pdf"
        assert first["mime_type"] == "application/pdf"
        assert first["size_bytes"] == len(PDF_ONE)
        assert len(first["sha256"]) == 64
        # Attaching to a pending document is not a verdict change.
        assert status_of(client, document_id) == "pending"
        assert history(client, document_id) == []

        # 5. The attachment shows up in the listing.
        listed = list_files(client, document_id)
        assert [row["id"] for row in listed] == [first["id"]]

        # 6. Confirm it.
        confirmed = decide(client, document_id, "verified")
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["verification_status"] == "verified"

        # 7-8. Exactly one event, and it says what happened.
        events = history(client, document_id)
        assert len(events) == 1
        assert tuples(events) == [
            ("pending", "verified", "verified", None),
        ]

        # 9. Correct the number.
        patched = client.patch(
            f"/documents/{document_id}", json={"number": "CERT-2026-002"}
        )
        assert patched.status_code == 200, patched.text

        # 10. The verdict is withdrawn, with the machine reason.
        assert patched.json()["verification_status"] == "pending"
        events = history(client, document_id)
        assert len(events) == 2
        assert tuples(events)[-1] == (
            "verified",
            "pending",
            "reopened",
            "significant_fields_changed",
        )

        # 11. Confirm again.
        assert decide(client, document_id, "verified").status_code == 200
        assert status_of(client, document_id) == "verified"
        assert len(history(client, document_id)) == 3

        # 12. Reject it, with a reason.
        rejected = decide(client, document_id, "rejected", "Скан нечитаем")
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["verification_status"] == "rejected"

        # 13. `verified -> rejected` happened directly, in one row.
        events = history(client, document_id)
        assert len(events) == 4
        assert tuples(events)[-1] == ("verified", "rejected", "rejected", "Скан нечитаем")

        # 14. A second scan on a rejected document withdraws the verdict.
        second = upload(client, document_id, PDF_TWO, "certificate-v2.pdf")
        assert second["id"] != first["id"]
        assert status_of(client, document_id) == "pending"
        events = history(client, document_id)
        assert len(events) == 5
        assert tuples(events)[-1] == ("rejected", "pending", "reopened", "file_added")
        assert [row["id"] for row in list_files(client, document_id)] == [
            first["id"],
            second["id"],
        ]

        # 15. Confirm again; two scans are now attached.
        assert decide(client, document_id, "verified").status_code == 200
        assert status_of(client, document_id) == "verified"
        assert len(history(client, document_id)) == 6

        # 16. Remove the first scan. The verdict is withdrawn again.
        deleted = client.delete(f"/documents/{document_id}/files/{first['id']}")
        assert deleted.status_code == 204, deleted.text
        assert deleted.content == b""
        assert status_of(client, document_id) == "pending"
        events = history(client, document_id)
        assert len(events) == 7
        assert tuples(events)[-1] == ("verified", "pending", "reopened", "file_deleted")
        assert [row["id"] for row in list_files(client, document_id)] == [second["id"]]

        # 17. The surviving attachment still downloads its own bytes.
        download = client.get(
            f"/documents/{document_id}/files/{second['id']}/content"
        )
        assert download.status_code == 200, download.text
        assert download.content == PDF_TWO
        assert download.headers["content-type"].startswith("application/pdf")

        # 18. The whole history, in order, with reasons and both endpoints.
        assert tuples(history(client, document_id)) == [
            ("pending", "verified", "verified", None),
            ("verified", "pending", "reopened", "significant_fields_changed"),
            ("pending", "verified", "verified", None),
            ("verified", "rejected", "rejected", "Скан нечитаем"),
            ("rejected", "pending", "reopened", "file_added"),
            ("pending", "verified", "verified", None),
            ("verified", "pending", "reopened", "file_deleted"),
        ]
        stamps = [row["created_at"] for row in history(client, document_id)]
        assert stamps == sorted(stamps)
        assert all(
            set(row)
            == {
                "id",
                "document_id",
                "from_status",
                "to_status",
                "event_type",
                "reason",
                "created_at",
            }
            for row in history(client, document_id)
        )


# --------------------------------------------------------------------------- #
# 4. Guards, isolation and failed operations
# --------------------------------------------------------------------------- #


class TestVerificationGuards:
    def test_confirming_without_a_file_is_422_and_changes_nothing(self, client):
        document_type_id = create_document_type(client)
        document_id = create_document(client, document_type_id, "CERT-1")["id"]

        response = decide(client, document_id, "verified")

        assert response.status_code == 422
        assert status_of(client, document_id) == "pending"
        assert history(client, document_id) == []
        assert list_files(client, document_id) == []

    def test_rejecting_without_a_reason_is_422(self, client):
        document_type_id = create_document_type(client)
        document_id = create_document(client, document_type_id, "CERT-1")["id"]
        assert decide(client, document_id, "verified").status_code == 422  # no file

        blank = decide(client, document_id, "rejected")
        assert blank.status_code == 422
        assert decide(client, document_id, "rejected", "   ").status_code == 422
        assert status_of(client, document_id) == "pending"
        assert history(client, document_id) == []

    def test_repeating_the_same_verdict_adds_no_event(self, client):
        document_type_id = create_document_type(client)
        document_id = create_document(client, document_type_id, "CERT-1")["id"]
        upload(client, document_id, PDF_ONE)
        assert decide(client, document_id, "verified").status_code == 200
        assert len(history(client, document_id)) == 1

        repeat = decide(client, document_id, "verified")

        assert repeat.status_code == 200
        assert repeat.json()["verification_status"] == "verified"
        assert len(history(client, document_id)) == 1

    def test_repeating_a_rejection_keeps_the_original_reason(self, client):
        document_type_id = create_document_type(client)
        document_id = create_document(client, document_type_id, "CERT-1")["id"]
        assert (
            decide(client, document_id, "rejected", "Первый повод").status_code == 200
        )

        repeat = decide(client, document_id, "rejected", "Второй повод")

        assert repeat.status_code == 200
        events = history(client, document_id)
        assert len(events) == 1
        assert events[0]["reason"] == "Первый повод"

    def test_notes_only_patch_preserves_a_verdict(self, client):
        document_type_id = create_document_type(client)
        document_id = create_document(client, document_type_id, "CERT-1")["id"]
        upload(client, document_id, PDF_ONE)
        assert decide(client, document_id, "verified").status_code == 200
        assert len(history(client, document_id)) == 1

        patched = client.patch(f"/documents/{document_id}", json={"notes": "Пометка"})

        assert patched.status_code == 200
        assert patched.json()["verification_status"] == "verified"
        assert len(history(client, document_id)) == 1

    def test_unknown_document_type_is_422_and_creates_nothing(self, client):
        before = len(client.get("/documents").json())

        response = client.post(
            "/documents", json={"document_type_id": 999_999, "number": "CERT-X"}
        )

        assert response.status_code == 422
        assert len(client.get("/documents").json()) == before


class TestIsolation:
    def test_neighbouring_documents_keep_their_own_status_and_history(self, client):
        document_type_id = create_document_type(client)
        first = create_document(client, document_type_id, "CERT-A")["id"]
        second = create_document(client, document_type_id, "CERT-B")["id"]
        upload(client, first, PDF_ONE)

        assert decide(client, first, "verified").status_code == 200

        assert status_of(client, first) == "verified"
        assert status_of(client, second) == "pending"
        assert len(history(client, first)) == 1
        assert history(client, second) == []
        assert list_files(client, second) == []

    def test_an_attachment_of_another_document_is_not_reachable(self, client):
        document_type_id = create_document_type(client)
        owner = create_document(client, document_type_id, "CERT-OWNER")["id"]
        other = create_document(client, document_type_id, "CERT-OTHER")["id"]
        file_id = upload(client, owner, PDF_ONE)["id"]

        assert list_files(client, other) == []
        assert client.get(f"/documents/{other}/files/{file_id}").status_code == 404
        assert (
            client.get(f"/documents/{other}/files/{file_id}/content").status_code == 404
        )
        assert client.delete(f"/documents/{other}/files/{file_id}").status_code == 404

        # The owner's attachment is untouched by the refused requests.
        assert [row["id"] for row in list_files(client, owner)] == [file_id]

    def test_a_failed_upload_leaves_no_attachment_behind(self, client):
        document_type_id = create_document_type(client)
        document_id = create_document(client, document_type_id, "CERT-1")["id"]

        # A zip is not an allowed type; the signature check refuses it.
        bad = client.post(
            f"/documents/{document_id}/files",
            files={"file": ("archive.pdf", b"PK\x03\x04 not a pdf", "application/pdf")},
        )

        assert bad.status_code == 422
        assert list_files(client, document_id) == []
        assert status_of(client, document_id) == "pending"
        assert history(client, document_id) == []

    def test_uploading_to_a_missing_document_is_404(self, client):
        response = client.post(
            "/documents/9999999/files",
            files={"file": ("scan.pdf", PDF_ONE, "application/pdf")},
        )
        assert response.status_code == 404


class TestSessionLifecycle:
    def test_reads_between_writes_do_not_cause_false_conflicts(self, client):
        # Each request gets its own session in this fixture. If a read left a
        # transaction open on a shared session, the write below would be refused
        # with `409` (`TransactionAlreadyOpenError`) instead of succeeding.
        document_type_id = create_document_type(client)
        document_id = create_document(client, document_type_id, "CERT-1")["id"]

        assert client.get(f"/documents/{document_id}").status_code == 200
        assert client.get(f"/documents/{document_id}/files").status_code == 200

        file_id = upload(client, document_id, PDF_ONE)["id"]

        assert client.get(f"/documents/{document_id}/files").status_code == 200
        assert history(client, document_id) == []

        assert client.delete(f"/documents/{document_id}/files/{file_id}").status_code == 204
        assert list_files(client, document_id) == []

    def test_two_consecutive_writes_both_succeed(self, client):
        document_type_id = create_document_type(client)
        document_id = create_document(client, document_type_id, "CERT-1")["id"]

        first = upload(client, document_id, PDF_ONE)
        second = upload(client, document_id, PDF_TWO)

        assert first["id"] != second["id"]
        assert len(list_files(client, document_id)) == 2

    def test_error_responses_reveal_no_internals(self, client):
        document_type_id = create_document_type(client)
        document_id = create_document(client, document_type_id, "CERT-1")["id"]

        for response in (
            decide(client, document_id, "verified"),
            client.get(f"/documents/{document_id}/files/9999999/content"),
            client.get("/documents/9999999/verification-history"),
        ):
            lowered = response.text.lower()
            for needle in ("select", "traceback", "psycopg", "storage_key", "password"):
                assert needle not in lowered, (needle, response.text)


# --------------------------------------------------------------------------- #
# 5. Contracts
# --------------------------------------------------------------------------- #

DOCUMENT_PATHS = {
    "/documents": {"get", "post"},
    "/documents/{document_id}": {"get", "patch"},
    "/documents/{document_id}/verification": {"post"},
    "/documents/{document_id}/verification-history": {"get"},
}

FILE_PATHS = {
    "/documents/{document_id}/files": {"get", "post"},
    "/documents/{document_id}/files/{file_id}": {"get", "delete"},
    "/documents/{document_id}/files/{file_id}/content": {"get"},
}


class TestContracts:
    def test_document_api_exposes_its_six_operations(self):
        paths = app.openapi()["paths"]
        for path, methods in DOCUMENT_PATHS.items():
            assert set(paths[path]) == methods, path

    def test_file_api_exposes_its_five_operations(self):
        paths = app.openapi()["paths"]
        for path, methods in FILE_PATHS.items():
            assert set(paths[path]) == methods, path

    def test_totals_are_eighteen_paths_and_thirty_two_operations(self):
        paths = app.openapi()["paths"]
        assert len(paths) == 18
        assert sum(len(item) for item in paths.values()) == 32

    def test_no_document_deletion_or_equipment_linking_is_declared(self):
        paths = app.openapi()["paths"]
        assert "delete" not in paths["/documents"]
        assert "delete" not in paths["/documents/{document_id}"]
        assert not any("products" in path for path in paths if "/documents/" in path)
        assert not any("variants" in path for path in paths if "/documents/" in path)

    def test_history_takes_no_paging_or_filter_parameters(self):
        operation = app.openapi()["paths"][
            "/documents/{document_id}/verification-history"
        ]["get"]
        query = [
            parameter
            for parameter in operation.get("parameters", [])
            if parameter.get("in") == "query"
        ]
        assert query == []

    def test_document_out_never_exposes_a_storage_key(self):
        schemas = app.openapi()["components"]["schemas"]
        assert "storage_key" not in schemas["DocumentOut"]["properties"]
        assert "storage_key" not in schemas["FileOut"]["properties"]
