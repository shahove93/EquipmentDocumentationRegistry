"""Service-level checks for `DocumentService.list` as a search.

The HTTP module pins the route contract; this one pins the SQL it delegates to,
where the awkward cases are cheaper to build directly than over HTTP:

* the composite filter has to be satisfied by **one** variant, never a union of
  two;
* an `EXISTS` match must not duplicate a document even when three of its variants
  match;
* only `document_variants` counts — a `document_products` link is not a search
  edge.

Everything runs against the scratch schema and is flushed, never committed: the
list is a read, so the same transaction is enough to see what was staged.
"""

import uuid
from decimal import Decimal

import pytest

from app.models.document import Document
from app.models.document_links import DocumentProduct
from app.models.document_type import DocumentType
from app.models.manufacturer import Manufacturer
from app.models.product import Product
from app.models.variant import ProductVariant
from app.services.document_service import DocumentService

PENDING = "pending"
VERIFIED = "verified"
REJECTED = "rejected"


def make_manufacturer(db, name: str | None = None) -> Manufacturer:
    manufacturer = Manufacturer(name=name or f"Завод {uuid.uuid4().hex[:8]}")
    db.add(manufacturer)
    db.flush()
    return manufacturer


def make_product(
    db,
    manufacturer: Manufacturer,
    name: str,
    standard: str = "ГОСТ 58121.2-2018",
) -> Product:
    product = Product(name=name, standard=standard, manufacturer=manufacturer)
    db.add(product)
    db.flush()
    return product


def make_variant(
    db,
    product: Product,
    size_text: str,
    diameter: Decimal | None = None,
) -> ProductVariant:
    variant = ProductVariant(
        product=product, size_text=size_text, diameter=diameter
    )
    db.add(variant)
    db.flush()
    return variant


def make_document(db, number: str, status: str = PENDING) -> Document:
    document = Document(
        document_type=DocumentType(name=f"Тип {uuid.uuid4().hex[:8]}"),
        number=number,
        verification_status=status,
    )
    db.add(document)
    db.flush()
    return document


def link(db, document: Document, variants: list[ProductVariant]) -> None:
    document.variants = list(variants)
    db.flush()


def ids(documents: list[Document]) -> list[int]:
    return [document.id for document in documents]


class TestFilters:
    def test_no_filters_returns_everything(self, db):
        first = make_document(db, "A")
        second = make_document(db, "B")

        assert ids(DocumentService.list(db)) == [first.id, second.id]

    def test_material_is_a_case_insensitive_substring(self, db):
        manufacturer = make_manufacturer(db)
        product = make_product(db, manufacturer, "Труба ПЭ100 SDR11")
        variant = make_variant(db, product, "Ø63")
        document = make_document(db, "A")
        link(db, document, [variant])

        assert ids(DocumentService.list(db, material="sdr11")) == [document.id]
        assert ids(DocumentService.list(db, material="ПЭ100")) == [document.id]

    def test_standard_is_a_case_insensitive_substring(self, db):
        manufacturer = make_manufacturer(db)
        product = make_product(
            db, manufacturer, "Труба", standard="ГОСТ 58121.2-2018"
        )
        variant = make_variant(db, product, "Ø63")
        document = make_document(db, "A")
        link(db, document, [variant])

        assert ids(DocumentService.list(db, standard="гост")) == [document.id]

    def test_number_is_a_case_insensitive_substring(self, db):
        first = make_document(db, "CERT-2026-001")
        second = make_document(db, "CERT-2026-002")

        assert ids(DocumentService.list(db, number="cert-2026")) == [
            first.id,
            second.id,
        ]
        assert ids(DocumentService.list(db, number="001")) == [first.id]

    def test_status_filter(self, db):
        pending = make_document(db, "A", status=PENDING)
        verified = make_document(db, "B", status=VERIFIED)
        rejected = make_document(db, "C", status=REJECTED)

        assert ids(DocumentService.list(db, status=VERIFIED)) == [verified.id]
        assert ids(DocumentService.list(db, status=PENDING)) == [pending.id]
        assert ids(DocumentService.list(db, status=REJECTED)) == [rejected.id]

    def test_size_text_is_exact(self, db):
        manufacturer = make_manufacturer(db)
        product = make_product(db, manufacturer, "Труба")
        variant = make_variant(db, product, "Ø63")
        document = make_document(db, "A")
        link(db, document, [variant])

        assert ids(DocumentService.list(db, size_text="Ø63")) == [document.id]
        assert ids(DocumentService.list(db, size_text="Ø 63")) == []

    def test_variant_id_is_exact(self, db):
        manufacturer = make_manufacturer(db)
        product = make_product(db, manufacturer, "Труба")
        linked = make_variant(db, product, "Ø63")
        unlinked = make_variant(db, product, "Ø110")
        document = make_document(db, "A")
        link(db, document, [linked])

        assert ids(DocumentService.list(db, variant_id=linked.id)) == [document.id]
        assert ids(DocumentService.list(db, variant_id=unlinked.id)) == []

    def test_manufacturer_id_is_exact(self, db):
        first = make_manufacturer(db, "Завод 1")
        second = make_manufacturer(db, "Завод 2")
        product = make_product(db, first, "Труба")
        variant = make_variant(db, product, "Ø63")
        document = make_document(db, "A")
        link(db, document, [variant])

        assert ids(DocumentService.list(db, manufacturer_id=first.id)) == [
            document.id
        ]
        assert ids(DocumentService.list(db, manufacturer_id=second.id)) == []

    def test_a_variant_with_no_diameter_is_found_by_size_text(self, db):
        manufacturer = make_manufacturer(db)
        product = make_product(db, manufacturer, "Труба")
        variant = make_variant(db, product, "Ø63", diameter=None)
        document = make_document(db, "A")
        link(db, document, [variant])

        assert variant.diameter is None
        assert ids(DocumentService.list(db, size_text="Ø63")) == [document.id]


class TestCompositeFilterSharesOneVariant:
    def test_two_variants_cannot_satisfy_two_filters(self, db):
        manufacturer = make_manufacturer(db)
        sdr11 = make_product(db, manufacturer, "Труба SDR11")
        sdr17 = make_product(db, manufacturer, "Труба SDR17")
        small = make_variant(db, sdr11, "Ø32")
        large = make_variant(db, sdr17, "Ø63")
        document = make_document(db, "A")
        link(db, document, [small, large])

        # material on one variant, size on the other: no single variant matches
        assert ids(DocumentService.list(db, material="SDR11", size_text="Ø63")) == []

    def test_one_variant_matching_all_filters_returns_the_document(self, db):
        manufacturer = make_manufacturer(db)
        sdr11 = make_product(db, manufacturer, "Труба SDR11")
        sdr17 = make_product(db, manufacturer, "Труба SDR17")
        small = make_variant(db, sdr11, "Ø32")
        large = make_variant(db, sdr17, "Ø63")
        document = make_document(db, "A")
        link(db, document, [small, large])

        assert ids(
            DocumentService.list(db, material="SDR11", size_text="Ø32")
        ) == [document.id]
        assert ids(
            DocumentService.list(db, material="SDR17", size_text="Ø63")
        ) == [document.id]

    def test_manufacturer_and_size_must_share_a_variant(self, db):
        first = make_manufacturer(db, "Завод 1")
        second = make_manufacturer(db, "Завод 2")
        large = make_variant(db, make_product(db, first, "Труба 1"), "Ø63")
        small = make_variant(db, make_product(db, second, "Труба 2"), "Ø32")
        document = make_document(db, "A")
        link(db, document, [large, small])

        # manufacturer on one variant, size on the other
        assert ids(
            DocumentService.list(db, manufacturer_id=first.id, size_text="Ø32")
        ) == []
        assert ids(
            DocumentService.list(db, manufacturer_id=first.id, size_text="Ø63")
        ) == [document.id]

    def test_three_matching_variants_do_not_duplicate_the_document(self, db):
        manufacturer = make_manufacturer(db)
        product = make_product(db, manufacturer, "Труба SDR11")
        variants = [
            make_variant(db, product, size) for size in ("Ø32", "Ø63", "Ø110")
        ]
        document = make_document(db, "A")
        link(db, document, variants)

        assert ids(DocumentService.list(db, material="SDR11")) == [document.id]


class TestScopeAndPaging:
    def test_an_unlinked_document_is_not_found_by_material(self, db):
        manufacturer = make_manufacturer(db)
        product = make_product(db, manufacturer, "Труба SDR11")
        variant = make_variant(db, product, "Ø63")
        linked = make_document(db, "A")
        link(db, linked, [variant])
        unlinked = make_document(db, "B")

        assert ids(DocumentService.list(db, material="SDR11")) == [linked.id]
        assert unlinked.id not in ids(DocumentService.list(db, material="SDR11"))

    def test_a_product_only_link_is_not_a_search_edge(self, db):
        manufacturer = make_manufacturer(db)
        product = make_product(db, manufacturer, "Труба SDR11")
        document = make_document(db, "A")
        db.add(DocumentProduct(document_id=document.id, product_id=product.id))
        db.flush()

        assert ids(DocumentService.list(db, material="SDR11")) == []
        assert ids(DocumentService.list(db, material="Труба")) == []

    def test_unknown_ids_match_nothing(self, db):
        assert ids(DocumentService.list(db, variant_id=999_999)) == []
        assert ids(DocumentService.list(db, manufacturer_id=999_999)) == []

    def test_paging_is_applied_after_filtering(self, db):
        manufacturer = make_manufacturer(db)
        product = make_product(db, manufacturer, "Труба SDR11")
        matching = []
        for size in ("Ø32", "Ø63", "Ø110"):
            variant = make_variant(db, product, size)
            document = make_document(db, f"D-{size}")
            link(db, document, [variant])
            matching.append(document.id)
        # a document that does not match, added after the matches
        noise = make_document(db, "NOISE")

        page = DocumentService.list(db, limit=2, offset=1, material="SDR11")

        assert ids(page) == matching[1:3]
        assert noise.id not in matching

    def test_correlated_exists_orders_by_id(self, db):
        manufacturer = make_manufacturer(db)
        product = make_product(db, manufacturer, "Труба SDR11")
        documents = []
        for size in ("Ø32", "Ø63", "Ø110"):
            variant = make_variant(db, product, size)
            document = make_document(db, f"D-{size}")
            link(db, document, [variant])
            documents.append(document.id)

        found = ids(DocumentService.list(db, material="SDR11"))

        assert found == sorted(documents)


class TestCompatibility:
    def test_positional_arguments_still_work(self, db):
        documents = [make_document(db, letter) for letter in ("A", "B", "C")]

        assert ids(DocumentService.list(db, 10, 0)) == [d.id for d in documents]
        assert ids(DocumentService.list(db, 1, 1)) == [documents[1].id]

    def test_filters_are_keyword_only(self):
        # a positional call with three arguments must not be reinterpreted as
        # `limit, offset, material`
        import inspect

        signature = inspect.signature(DocumentService.list)
        parameters = list(signature.parameters.values())
        names = [parameter.name for parameter in parameters]
        assert names[:3] == ["db", "limit", "offset"]
        for parameter in parameters[3:]:
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
