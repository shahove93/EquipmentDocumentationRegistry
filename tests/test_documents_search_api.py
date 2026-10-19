"""HTTP contract for searching documents by material and size.

`GET /documents` grew optional filters; the route, the response shape and the
operation count are unchanged. This module drives the search a user performs —
"a certificate for a ПЭ100 SDR11 pipe, size Ø63, a given maker, per GOST" — and
pins the parts that are easy to get wrong:

* an unknown `variant_id` or `manufacturer_id` is `200 []`, not `404`;
* a blank text filter is `422`, never a silent "no filter";
* two filters cannot be satisfied by two different covered variants;
* one matching document is returned once, not once per matching variant;
* a link made only through `document_products` is not a search edge.

Documents, products and variants are built over HTTP. Only the `document_products`
link — which has no route yet — is staged directly in the database, because the
point of that test is precisely that search ignores it.

Everything runs against the scratch schema `test_file_service` and a temporary
storage root; the working database and `storage/` are never touched.
"""

import ast
import inspect
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
# HTTP helpers
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


def create_document(client: TestClient, number: str | None = None) -> int:
    document_type = client.post(
        "/document-types", json={"name": f"Тип {uuid.uuid4().hex[:8]}"}
    )
    assert document_type.status_code == 201, document_type.text
    response = client.post(
        "/documents",
        json={
            "document_type_id": document_type.json()["id"],
            "number": number or f"D-{uuid.uuid4().hex[:8]}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def link(client: TestClient, document_id: int, variant_ids: list[int]) -> None:
    response = client.put(
        f"/documents/{document_id}/variants", json={"variant_ids": variant_ids}
    )
    assert response.status_code == 200, response.text


def upload(client: TestClient, document_id: int) -> dict:
    response = client.post(
        f"/documents/{document_id}/files",
        files={"file": ("scan.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def decide(client: TestClient, document_id: int, decision: str, reason: str | None = None):
    body: dict[str, object] = {"decision": decision}
    if reason is not None:
        body["reason"] = reason
    return client.post(f"/documents/{document_id}/verification", json=body)


def search(client: TestClient, **params):
    return client.get("/documents", params=params)


def found(client: TestClient, **params) -> list[int]:
    response = search(client, **params)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()]


def event_count(db: Session, document_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(DocumentVerificationEvent)
        .where(DocumentVerificationEvent.document_id == document_id)
    )


def product_with_sizes(
    client: TestClient,
    name: str,
    sizes: list[str],
    *,
    standard: str = "ГОСТ 58121.2-2018",
    manufacturer_name: str | None = None,
) -> tuple[int, int, dict[str, int]]:
    """One product holding the given sizes; returns ids keyed by size text."""
    manufacturer_id = create_manufacturer(client, manufacturer_name)
    product_id = create_product(client, manufacturer_id, name, standard)
    variants = {size: create_variant(client, product_id, size) for size in sizes}
    return manufacturer_id, product_id, variants


# --------------------------------------------------------------------------- #
# 1-10: the individual filters
# --------------------------------------------------------------------------- #


class TestFilters:
    def test_no_filters_is_the_plain_collection(self, client):
        first = create_document(client)
        second = create_document(client)
        third = create_document(client)

        assert found(client) == [first, second, third]

    def test_by_material(self, client):
        _, _, sizes = product_with_sizes(client, "Труба ПЭ100 SDR11", ["Ø63"])
        document = create_document(client)
        link(client, document, [sizes["Ø63"]])
        create_document(client)

        assert found(client, material="SDR11") == [document]

    def test_by_size_text(self, client):
        _, _, sizes = product_with_sizes(client, "Труба ПЭ100 SDR11", ["Ø32", "Ø63"])
        document = create_document(client)
        link(client, document, [sizes["Ø63"]])

        assert found(client, size_text="Ø63") == [document]
        assert found(client, size_text="Ø32") == []

    def test_by_variant_id(self, client):
        _, _, sizes = product_with_sizes(client, "Труба ПЭ100 SDR11", ["Ø32", "Ø63"])
        document = create_document(client)
        link(client, document, [sizes["Ø63"]])

        assert found(client, variant_id=sizes["Ø63"]) == [document]
        assert found(client, variant_id=sizes["Ø32"]) == []

    def test_by_manufacturer_id(self, client):
        maker, _, sizes = product_with_sizes(client, "Труба ПЭ100 SDR11", ["Ø63"])
        other_maker = create_manufacturer(client)
        document = create_document(client)
        link(client, document, [sizes["Ø63"]])

        assert found(client, manufacturer_id=maker) == [document]
        assert found(client, manufacturer_id=other_maker) == []

    def test_by_standard(self, client):
        _, _, sizes = product_with_sizes(
            client, "Труба", ["Ø63"], standard="ТУ 2248-002-2018"
        )
        document = create_document(client)
        link(client, document, [sizes["Ø63"]])

        assert found(client, standard="ТУ 2248") == [document]

    def test_by_number(self, client):
        first = create_document(client, "CERT-2026-001")
        second = create_document(client, "CERT-2026-002")

        assert found(client, number="2026-001") == [first]
        assert found(client, number="2026-002") == [second]

    def test_by_status(self, client):
        pending = create_document(client)
        verified = create_document(client)
        upload(client, verified)
        assert decide(client, verified, "verified").status_code == 200

        assert found(client, status="verified") == [verified]
        assert found(client, status="pending") == [pending]
        assert found(client, status="rejected") == []

    def test_several_filters_together(self, client):
        maker, _, sizes = product_with_sizes(
            client, "Труба ПЭ100 SDR11", ["Ø32", "Ø63", "Ø110"]
        )
        document = create_document(client, "CERT-2026-063")
        link(client, document, list(sizes.values()))
        upload(client, document)
        assert decide(client, document, "verified").status_code == 200

        assert found(
            client,
            material="SDR11",
            size_text="Ø63",
            manufacturer_id=maker,
            standard="ГОСТ",
            number="2026-063",
            status="verified",
        ) == [document]

        # one wrong value drops it
        assert found(client, material="SDR11", size_text="Ø99") == []

    @pytest.mark.parametrize("term", ["sdr11", "SDR11", "пэ100", "ПЭ100"])
    def test_text_filters_are_case_insensitive(self, client, term):
        _, _, sizes = product_with_sizes(client, "Труба ПЭ100 SDR11", ["Ø63"])
        document = create_document(client)
        link(client, document, [sizes["Ø63"]])

        assert found(client, material=term) == [document]


# --------------------------------------------------------------------------- #
# 11-17: exactness, one-variant rule, scope
# --------------------------------------------------------------------------- #


class TestSearchSemantics:
    def test_size_text_is_exact(self, client):
        _, _, sizes = product_with_sizes(client, "Труба", ["Ø63"])
        document = create_document(client)
        link(client, document, [sizes["Ø63"]])

        assert found(client, size_text="Ø63") == [document]
        assert found(client, size_text="Ø 63") == []
        assert found(client, size_text="ø63") == []

    def test_a_variant_without_a_diameter_is_found_by_size_text(self, client):
        _, _, sizes = product_with_sizes(client, "Труба", ["Ø63"])
        document = create_document(client)
        link(client, document, [sizes["Ø63"]])

        variant = client.get(f"/variants/{sizes['Ø63']}").json()
        assert variant["diameter"] is None
        assert found(client, size_text="Ø63") == [document]

    def test_matching_three_variants_returns_one_document(self, client):
        _, _, sizes = product_with_sizes(client, "Труба SDR11", ["Ø32", "Ø63", "Ø110"])
        document = create_document(client)
        link(client, document, list(sizes.values()))

        assert found(client, material="SDR11") == [document]
        assert len(found(client, material="SDR11")) == 1

    def test_two_variants_cannot_satisfy_one_composite_filter(self, client):
        _, _, first = product_with_sizes(client, "Труба SDR11", ["Ø32"])
        _, _, second = product_with_sizes(client, "Труба SDR17", ["Ø63"])
        document = create_document(client)
        link(client, document, [first["Ø32"], second["Ø63"]])

        # material from one variant, size from the other
        assert found(client, material="SDR11", size_text="Ø63") == []
        # each filter satisfied by its own variant
        assert found(client, material="SDR11", size_text="Ø32") == [document]
        assert found(client, material="SDR17", size_text="Ø63") == [document]

    def test_attributes_on_one_variant_are_found(self, client):
        maker, _, sizes = product_with_sizes(client, "Труба SDR11", ["Ø63"])
        document = create_document(client)
        link(client, document, [sizes["Ø63"]])

        assert found(
            client,
            material="SDR11",
            size_text="Ø63",
            manufacturer_id=maker,
        ) == [document]

    def test_an_unlinked_document_is_not_found_by_material(self, client):
        _, _, sizes = product_with_sizes(client, "Труба SDR11", ["Ø63"])
        linked = create_document(client)
        link(client, linked, [sizes["Ø63"]])
        unrelated = create_document(client)

        assert found(client, material="SDR11") == [linked]
        assert unrelated not in found(client, material="SDR11")

    def test_a_product_only_link_is_not_a_search_edge(self, client, db):
        _, product_id, _ = product_with_sizes(client, "Труба SDR11", ["Ø63"])
        document = create_document(client)
        db.add(DocumentProduct(document_id=document, product_id=product_id))
        db.commit()

        assert found(client, material="SDR11") == []
        assert found(client, size_text="Ø63") == []

    def test_autoescaped_wildcards_are_literal(self, client):
        _, _, literal = product_with_sizes(client, "Труба 100%", ["Ø63"])
        _, _, decoy = product_with_sizes(client, "Труба 1000", ["Ø110"])
        first = create_document(client)
        second = create_document(client)
        link(client, first, [literal["Ø63"]])
        link(client, second, [decoy["Ø110"]])

        # `100%` must not behave as "starts with 100"
        assert found(client, material="100%") == [first]


# --------------------------------------------------------------------------- #
# 18-21: paging, ordering, invalid and unknown values
# --------------------------------------------------------------------------- #


class TestPagingAndErrors:
    def test_paging_is_applied_after_filtering(self, client):
        manufacturer_id = create_manufacturer(client)
        product_id = create_product(client, manufacturer_id, "Труба SDR11")
        matching = []
        for size in ("Ø32", "Ø63", "Ø110"):
            variant_id = create_variant(client, product_id, size)
            document = create_document(client, f"D-{size}")
            link(client, document, [variant_id])
            matching.append(document)
        create_document(client, "NOISE")

        first_page = found(client, material="SDR11", limit=2, offset=0)
        second_page = found(client, material="SDR11", limit=2, offset=2)

        assert first_page == matching[:2]
        assert second_page == matching[2:]

    def test_results_are_ordered_by_id(self, client):
        manufacturer_id = create_manufacturer(client)
        product_id = create_product(client, manufacturer_id, "Труба SDR11")
        documents = []
        for size in ("Ø110", "Ø32", "Ø63"):
            variant_id = create_variant(client, product_id, size)
            document = create_document(client)
            link(client, document, [variant_id])
            documents.append(document)

        assert found(client, material="SDR11") == sorted(documents)

    def test_unknown_variant_and_manufacturer_are_empty_not_404(self, client):
        for params in ({"variant_id": 9_999_999}, {"manufacturer_id": 9_999_999}):
            response = search(client, **params)
            assert response.status_code == 200, response.text
            assert response.json() == []

    @pytest.mark.parametrize(
        "params",
        [
            {"material": ""},
            {"material": "   "},
            {"size_text": ""},
            {"standard": "   "},
            {"number": ""},
            {"status": "unknown"},
            {"status": ""},
            {"variant_id": 0},
            {"variant_id": -1},
            {"manufacturer_id": 0},
            {"manufacturer_id": -1},
            {"variant_id": "x"},
            {"material": "x" * 256},
            {"limit": 0},
            {"limit": 101},
            {"offset": -1},
        ],
    )
    def test_invalid_parameters_are_422(self, client, params):
        response = search(client, **params)
        assert response.status_code == 422, (params, response.text)

    def test_a_trimmed_term_is_used_as_sent(self, client):
        _, _, sizes = product_with_sizes(client, "Труба SDR11", ["Ø63"])
        document = create_document(client)
        link(client, document, [sizes["Ø63"]])

        assert found(client, material="  SDR11  ") == [document]


# --------------------------------------------------------------------------- #
# 22-23: search is read-only and scoped
# --------------------------------------------------------------------------- #


class TestSearchIsReadOnly:
    def test_search_changes_nothing(self, client, db):
        _, _, sizes = product_with_sizes(client, "Труба SDR11", ["Ø63"])
        document = create_document(client, "CERT-2026-001")
        link(client, document, [sizes["Ø63"]])
        file = upload(client, document)
        assert decide(client, document, "verified").status_code == 200

        before_events = event_count(db, document)
        before_links = client.get(f"/documents/{document}/variants").json()
        before_card = client.get(f"/documents/{document}").json()

        assert found(client, material="SDR11", size_text="Ø63") == [document]

        assert event_count(db, document) == before_events
        assert client.get(f"/documents/{document}/variants").json() == before_links
        card = client.get(f"/documents/{document}").json()
        assert card == before_card
        assert card["verification_status"] == "verified"
        assert client.get(f"/documents/{document}/files/{file['id']}").status_code == 200

    def test_neighbouring_documents_are_isolated(self, client):
        _, _, sizes = product_with_sizes(client, "Труба SDR11", ["Ø63"])
        matching = create_document(client)
        link(client, matching, [sizes["Ø63"]])
        other = create_document(client)

        assert found(client, material="SDR11") == [matching]
        assert other not in found(client, material="SDR11")


# --------------------------------------------------------------------------- #
# 24-27: router, neighbours, the documented surface, leakage
# --------------------------------------------------------------------------- #


class TestRouterAndSurface:
    def test_the_router_runs_no_sql_of_its_own(self):
        from app.api.documents import router as router_module

        tree = ast.parse(inspect.getsource(router_module))
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert "commit" not in attributes
        assert "rollback" not in attributes
        assert "with_for_update" not in attributes
        assert "select" not in called_names
        assert "execute" not in called_names

    def test_the_document_variant_and_file_api_still_work(self, client):
        _, _, sizes = product_with_sizes(client, "Труба SDR11", ["Ø63"])
        document = create_document(client)
        link(client, document, [sizes["Ø63"]])
        upload(client, document)

        assert client.get(f"/documents/{document}").status_code == 200
        assert client.get(f"/documents/{document}/files").status_code == 200
        assert client.get(f"/variants/{sizes['Ø63']}").status_code == 200
        assert client.get("/documents").status_code == 200

    def test_openapi_keeps_the_operation_count_and_shows_the_filters(self):
        schema = app.openapi()
        paths = schema["paths"]
        assert len(paths) == 19
        assert sum(len(item) for item in paths.values()) == 34

        parameters = paths["/documents"]["get"]["parameters"]
        names = {parameter["name"] for parameter in parameters}
        assert {
            "limit",
            "offset",
            "material",
            "size_text",
            "variant_id",
            "manufacturer_id",
            "standard",
            "number",
            "status",
        } <= names

    def test_search_errors_reveal_no_internals(self, client):
        responses = [
            search(client, **params)
            for params in (
                {"material": ""},
                {"status": "nope"},
                {"variant_id": 0},
                {"limit": 0},
            )
        ]
        for response in responses:
            lowered = response.text.lower()
            for needle in ("select", "traceback", "psycopg", "storage_key", "password"):
                assert needle not in lowered, (needle, response.text)


# --------------------------------------------------------------------------- #
# The scenario the feature exists for
# --------------------------------------------------------------------------- #


class TestCertificateIsFoundAndItsPdfDownloads:
    def test_find_by_size_and_download(self, client):
        maker, _, sizes = product_with_sizes(
            client,
            "Труба ПЭ100 SDR11",
            ["Ø32", "Ø63", "Ø110"],
            manufacturer_name="Завод Полипласт",
        )
        document = create_document(client, "CERT-2026-063")
        link(client, document, list(sizes.values()))
        file = upload(client, document)

        response = search(
            client,
            material="ПЭ100",
            size_text="Ø63",
            manufacturer_id=maker,
            standard="ГОСТ",
        )
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()] == [document]

        content = client.get(f"/documents/{document}/files/{file['id']}/content")
        assert content.status_code == 200, content.text
        assert content.content == PDF
