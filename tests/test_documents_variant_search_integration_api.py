"""End-to-end HTTP walk from a pipe to a downloadable certificate.

This is the scenario the whole material-linking slice exists for:

    create a maker and a product «Труба ПЭ100 SDR11» with three sizes →
    create a certificate → upload its PDF → link it to the three sizes →
    find it by Ø63 → open its card → download the PDF.

Everything in the main scenario is done through `TestClient`; no service is
imported or called to drive it, because the point is precisely that the approved
chain is reachable for a user, not just from Python. A few *additional* checks —
a `document_products` link, event counting — stage rows directly in the database
because there is no route for them or no route that exposes the raw count; those
tests say so where they do it.

Two behaviours are checked as hard as the happy path, because they are the ones a
reader would get wrong:

* linking a certificate to a size is **not** a verdict change — replacing the set
  leaves `verified` verified and adds no event, so the history stays exactly the
  one `verified` row;
* the material filters must be satisfied by **one** variant, and one matching
  document is returned **once**.

Runs against the scratch schema `test_file_service` and a temporary storage root;
the working database and `storage/` are untouched.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.connection import get_db
from app.main import app
from app.models.document_links import DocumentProduct
from app.models.document_verification_event import DocumentVerificationEvent

DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"
MAX_BYTES = 64 * 1024

# A structurally valid PDF with distinctive bytes, so the download check compares
# real content rather than an empty body.
PDF = (
    b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
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
# HTTP helpers — no service is called anywhere
# --------------------------------------------------------------------------- #


def create_manufacturer(client: TestClient, name: str | None = None) -> int:
    response = client.post(
        "/manufacturers", json={"name": name or f"Завод {uuid.uuid4().hex[:8]}"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_product(
    client: TestClient,
    manufacturer_id: int,
    name: str,
    standard: str = "ГОСТ 58121.2-2018",
) -> int:
    response = client.post(
        "/products",
        json={"name": name, "standard": standard, "manufacturer_id": manufacturer_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_variant(client: TestClient, product_id: int, size_text: str) -> int:
    response = client.post(
        f"/products/{product_id}/variants", json={"size_text": size_text}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_document_type(client: TestClient, name: str | None = None) -> int:
    response = client.post(
        "/document-types", json={"name": name or f"Тип {uuid.uuid4().hex[:8]}"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_document(
    client: TestClient, document_type_id: int, number: str
) -> dict:
    response = client.post(
        "/documents",
        json={"document_type_id": document_type_id, "number": number},
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload(client: TestClient, document_id: int, content: bytes = PDF) -> dict:
    response = client.post(
        f"/documents/{document_id}/files",
        files={"file": ("certificate.pdf", content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def decide(client: TestClient, document_id: int, decision: str, reason: str | None = None):
    body: dict[str, object] = {"decision": decision}
    if reason is not None:
        body["reason"] = reason
    return client.post(f"/documents/{document_id}/verification", json=body)


def put_variants(client: TestClient, document_id: int, variant_ids: list[int]):
    return client.put(
        f"/documents/{document_id}/variants", json={"variant_ids": variant_ids}
    )


def linked_ids(client: TestClient, document_id: int) -> list[int]:
    response = client.get(f"/documents/{document_id}/variants")
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()]


def get_document(client: TestClient, document_id: int) -> dict:
    response = client.get(f"/documents/{document_id}")
    assert response.status_code == 200, response.text
    return response.json()


def list_files(client: TestClient, document_id: int) -> list[dict]:
    response = client.get(f"/documents/{document_id}/files")
    assert response.status_code == 200, response.text
    return response.json()


def download(client: TestClient, document_id: int, file_id: int):
    return client.get(f"/documents/{document_id}/files/{file_id}/content")


def search(client: TestClient, **params):
    return client.get("/documents", params=params)


def found(client: TestClient, **params) -> list[int]:
    response = search(client, **params)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()]


def history(client: TestClient, document_id: int) -> list[dict]:
    response = client.get(f"/documents/{document_id}/verification-history")
    assert response.status_code == 200, response.text
    return response.json()


def event_types(client: TestClient, document_id: int) -> list[str]:
    return [event["event_type"] for event in history(client, document_id)]


def event_count(db: Session, document_id: int) -> int:
    """Raw history count — used only by checks that have no route for it."""
    return db.scalar(
        select(func.count())
        .select_from(DocumentVerificationEvent)
        .where(DocumentVerificationEvent.document_id == document_id)
    )


def certificate_ready_for_linking(
    client: TestClient,
) -> tuple[int, int, dict[str, int], int, dict]:
    """Maker, product, size→variant ids, document id and the uploaded file."""
    maker = create_manufacturer(client, "Завод Полипласт")
    product = create_product(
        client, maker, "Труба ПЭ100 SDR11", "ГОСТ 58121.2-2018"
    )
    sizes = {
        size: create_variant(client, product, size)
        for size in ("Ø32", "Ø63", "Ø110")
    }
    document_type = create_document_type(client, "Сертификат соответствия")
    document = create_document(client, document_type, "CERT-2026-063")["id"]
    file = upload(client, document)
    return maker, product, sizes, document, file


# --------------------------------------------------------------------------- #
# The scenario
# --------------------------------------------------------------------------- #


class TestCertificateCoversThreeSizes:
    def test_end_to_end(self, client):
        # 1-3. A maker, one product, three sizes.
        maker = create_manufacturer(client, "Завод Полипласт")
        product = create_product(
            client, maker, "Труба ПЭ100 SDR11", "ГОСТ 58121.2-2018"
        )
        sizes = {
            size: create_variant(client, product, size)
            for size in ("Ø32", "Ø63", "Ø110")
        }

        # 4-5. A certificate, born `pending` with no links and no history.
        document_type = create_document_type(client, "Сертификат соответствия")
        created = create_document(client, document_type, "CERT-2026-063")
        document = created["id"]
        assert created["verification_status"] == "pending"
        assert linked_ids(client, document) == []
        assert history(client, document) == []

        # 6. The scan.
        file = upload(client, document)
        assert file["document_id"] == document
        assert file["size_bytes"] == len(PDF)
        # attaching to a pending document is not a verdict change
        assert get_document(client, document)["verification_status"] == "pending"
        assert history(client, document) == []

        # 7-8. Link all three, sent out of order; the set comes back by id.
        response = put_variants(
            client, document, [sizes["Ø63"], sizes["Ø110"], sizes["Ø32"]]
        )
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()] == sorted(sizes.values())
        assert linked_ids(client, document) == sorted(sizes.values())

        # 9-10. Find it by material and size, then narrow by maker and standard.
        assert found(client, material="SDR11", size_text="Ø63") == [document]
        assert found(
            client,
            material="SDR11",
            size_text="Ø63",
            manufacturer_id=maker,
            standard="ГОСТ",
        ) == [document]
        # a different standard does not match
        assert found(
            client, size_text="Ø63", standard="ТУ 2248-002-2018"
        ) == []

        # 11. Open the card the search returned.
        card = get_document(client, document)
        assert card["number"] == "CERT-2026-063"
        assert card["verification_status"] == "pending"

        # 12-13. The attachment is listed and its bytes come back unchanged.
        attachments = list_files(client, document)
        assert [item["id"] for item in attachments] == [file["id"]]
        content = download(client, document, file["id"])
        assert content.status_code == 200, content.text
        assert content.content == PDF

        # 14. Confirm the certificate.
        confirmed = decide(client, document, "verified")
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["verification_status"] == "verified"

        # 15. The same search still finds it, now filtered by status.
        assert found(
            client, material="SDR11", size_text="Ø63", status="verified"
        ) == [document]
        assert event_types(client, document) == ["verified"]

        # 16-18. Drop Ø63 from the set; Ø63 stops matching, the others hold.
        assert put_variants(
            client, document, [sizes["Ø32"], sizes["Ø110"]]
        ).status_code == 200
        assert linked_ids(client, document) == sorted(
            [sizes["Ø32"], sizes["Ø110"]]
        )
        assert found(client, size_text="Ø63") == []
        assert found(client, size_text="Ø32") == [document]
        assert found(client, size_text="Ø110") == [document]

        # 19. Linking is not a verdict change: still verified, one event, no reopened.
        assert get_document(client, document)["verification_status"] == "verified"
        assert event_types(client, document) == ["verified"]

        # 20. Repeating the identical set is accepted and changes nothing.
        repeat = put_variants(client, document, [sizes["Ø32"], sizes["Ø110"]])
        assert repeat.status_code == 200, repeat.text
        assert [item["id"] for item in repeat.json()] == sorted(
            [sizes["Ø32"], sizes["Ø110"]]
        )
        assert linked_ids(client, document) == sorted(
            [sizes["Ø32"], sizes["Ø110"]]
        )
        assert get_document(client, document)["verification_status"] == "verified"


# --------------------------------------------------------------------------- #
# Additional checks — mostly extra HTTP; a couple stage rows directly
# --------------------------------------------------------------------------- #


class TestLinkingAndSearchConsistency:
    def test_one_size_can_be_shared_by_several_certificates(self, client):
        maker = create_manufacturer(client)
        product = create_product(client, maker, "Труба ПЭ100 SDR11")
        size = create_variant(client, product, "Ø63")
        document_type = create_document_type(client)
        first = create_document(client, document_type, "CERT-1")["id"]
        second = create_document(client, document_type, "CERT-2")["id"]

        assert put_variants(client, first, [size]).status_code == 200
        assert put_variants(client, second, [size]).status_code == 200

        assert found(client, size_text="Ø63") == [first, second]

    def test_composite_filter_must_share_one_variant(self, client):
        maker = create_manufacturer(client)
        sdr11 = create_product(client, maker, "Труба SDR11")
        sdr17 = create_product(client, maker, "Труба SDR17")
        small = create_variant(client, sdr11, "Ø32")
        large = create_variant(client, sdr17, "Ø63")
        document_type = create_document_type(client)
        document = create_document(client, document_type, "CERT")["id"]
        assert put_variants(client, document, [small, large]).status_code == 200

        assert found(client, material="SDR11", size_text="Ø63") == []
        assert found(client, material="SDR11", size_text="Ø32") == [document]
        assert found(client, material="SDR17", size_text="Ø63") == [document]

    def test_a_matching_document_is_returned_once(self, client):
        maker = create_manufacturer(client)
        product = create_product(client, maker, "Труба ПЭ100 SDR11")
        sizes = [
            create_variant(client, product, size)
            for size in ("Ø32", "Ø63", "Ø110")
        ]
        document_type = create_document_type(client)
        document = create_document(client, document_type, "CERT")["id"]
        assert put_variants(client, document, sizes).status_code == 200

        assert found(client, material="SDR11") == [document]

    def test_size_text_is_exact(self, client):
        maker = create_manufacturer(client)
        product = create_product(client, maker, "Труба")
        tight = create_variant(client, product, "Ø63")
        spaced = create_variant(client, product, "Ø 63")
        document_type = create_document_type(client)
        document = create_document(client, document_type, "CERT")["id"]
        assert put_variants(client, document, [tight, spaced]).status_code == 200

        # `Ø63` names only the tight variant, not the spaced one
        assert [item["id"] for item in client.get(
            f"/documents/{document}/variants"
        ).json()] == sorted([tight, spaced])
        assert found(client, size_text="Ø63") == [document]
        # but asking for the spaced size still finds the document through it
        assert found(client, size_text="Ø 63") == [document]
        # a lower-case `ø` is a different string and matches nothing
        assert found(client, size_text="ø63") == []

    def test_a_size_without_a_diameter_is_still_searchable(self, client):
        maker = create_manufacturer(client)
        product = create_product(client, maker, "Труба ПЭ100 SDR11")
        size = create_variant(client, product, "Ø63")
        document_type = create_document_type(client)
        document = create_document(client, document_type, "CERT")["id"]
        assert put_variants(client, document, [size]).status_code == 200

        variant = client.get(f"/variants/{size}").json()
        assert variant["diameter"] is None
        assert found(client, size_text="Ø63") == [document]

    def test_unknown_filter_ids_are_empty_not_missing(self, client):
        create_document(client, create_document_type(client), "CERT")

        for params in ({"variant_id": 9_999_999}, {"manufacturer_id": 9_999_999}):
            response = search(client, **params)
            assert response.status_code == 200, response.text
            assert response.json() == []

    def test_a_failed_put_leaves_no_partial_links(self, client):
        maker = create_manufacturer(client)
        product = create_product(client, maker, "Труба")
        first = create_variant(client, product, "Ø32")
        second = create_variant(client, product, "Ø63")
        document_type = create_document_type(client)
        document = create_document(client, document_type, "CERT")["id"]
        assert put_variants(client, document, [first, second]).status_code == 200

        failed = put_variants(client, document, [first, 9_999_999])

        assert failed.status_code == 422, failed.text
        assert linked_ids(client, document) == sorted([first, second])

    def test_product_and_batch_link_tables_are_untouched(self, client, db):
        document_type = create_document_type(client)
        document = create_document(client, document_type, "CERT")["id"]
        maker = create_manufacturer(client)
        product = create_product(client, maker, "Труба")
        size = create_variant(client, product, "Ø63")

        assert put_variants(client, document, [size]).status_code == 200
        assert found(client, size_text="Ø63") == [document]

        assert db.scalar(text_count("document_products")) == 0
        assert db.scalar(text_count("document_batches")) == 0

    def test_a_product_only_link_is_not_a_search_edge(self, client, db):
        # Preparatory: `document_products` has no route yet, so the link is
        # staged directly. The claim under test is that search ignores it.
        maker = create_manufacturer(client)
        product = create_product(client, maker, "Труба ПЭ100 SDR11")
        document_type = create_document_type(client)
        document = create_document(client, document_type, "CERT")["id"]
        db.add(DocumentProduct(document_id=document, product_id=product))
        db.commit()

        assert found(client, material="SDR11") == []
        assert found(client, material="Труба") == []

    def test_sequential_requests_never_produce_a_false_409(self, client):
        maker = create_manufacturer(client)
        product = create_product(client, maker, "Труба ПЭ100 SDR11")
        size = create_variant(client, product, "Ø63")
        document_type = create_document_type(client)
        document = create_document(client, document_type, "CERT")["id"]
        upload(client, document)

        responses = [
            client.get("/documents"),
            put_variants(client, document, [size]),
            client.get(f"/documents/{document}/variants"),
            client.get(f"/documents/{document}"),
            decide(client, document, "verified"),
            client.get(f"/documents/{document}/verification-history"),
            client.get("/documents", params={"size_text": "Ø63"}),
        ]

        assert [
            response.status_code for response in responses
        ] == [200, 200, 200, 200, 200, 200, 200]
        assert all(response.status_code != 409 for response in responses)

    def test_errors_reveal_no_internals(self, client):
        document_type = create_document_type(client)
        document = create_document(client, document_type, "CERT")["id"]
        upload(client, document)

        responses = [
            put_variants(client, document, [9_999_999]),
            search(client, material=""),
            search(client, status="nope"),
            client.get("/documents/9999999/variants"),
        ]
        for response in responses:
            lowered = response.text.lower()
            for needle in ("select", "traceback", "psycopg", "storage_key", "password"):
                assert needle not in lowered, (needle, response.text)

    def test_event_count_matches_the_history(self, client, db):
        # Preparatory: the raw count has no route; the history endpoint is the
        # user-visible view and the two must agree.
        document_type = create_document_type(client)
        document = create_document(client, document_type, "CERT")["id"]
        upload(client, document)
        assert decide(client, document, "verified").status_code == 200

        assert event_count(db, document) == len(history(client, document)) == 1


def text_count(table: str):
    from sqlalchemy import text

    return text(f"select count(*) from {table}")
