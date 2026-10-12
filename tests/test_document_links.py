from sqlalchemy import ForeignKey, Index, Integer

from app.models import (
    Base,
    Batch,
    Document,
    DocumentBatch,
    DocumentProduct,
    DocumentType,
    DocumentVariant,
    Manufacturer,
    Product,
    ProductVariant,
)

LINKS = {
    DocumentProduct: ("document_products", "document_id", "product_id", "documents", "products", "document_id", "product_id"),
    DocumentVariant: ("document_variants", "document_id", "variant_id", "documents", "product_variants", "document_id", "variant_id"),
    DocumentBatch: ("document_batches", "document_id", "batch_id", "documents", "batches", "document_id", "batch_id"),
}


class TestLinkTablesRegistered:
    def test_all_three_tables_registered(self):
        for model in LINKS:
            assert LINKS[model][0] in Base.metadata.tables

    def test_no_separate_id_column(self):
        for model, spec in LINKS.items():
            columns = list(model.__table__.columns.keys())
            assert columns == [spec[5], spec[6]]
            assert "id" not in columns

    def test_only_two_columns_each(self):
        for model in LINKS:
            assert len(model.__table__.columns) == 2


class TestLinkColumns:
    def test_document_id_not_null(self):
        for model, spec in LINKS.items():
            col = model.__table__.c[spec[1]]
            assert isinstance(col.type, Integer)
            assert col.nullable is False

    def test_entity_id_not_null(self):
        for model, spec in LINKS.items():
            col = model.__table__.c[spec[2]]
            assert isinstance(col.type, Integer)
            assert col.nullable is False

    def test_document_fk_targets_documents(self):
        for model, spec in LINKS.items():
            fks = list(model.__table__.c[spec[1]].foreign_keys)
            assert len(fks) == 1
            assert isinstance(fks[0], ForeignKey)
            assert fks[0].column.table.name == spec[3]
            assert fks[0].column.name == "id"

    def test_entity_fk_targets_correct_table(self):
        for model, spec in LINKS.items():
            fks = list(model.__table__.c[spec[2]].foreign_keys)
            assert len(fks) == 1
            assert fks[0].column.table.name == spec[4]
            assert fks[0].column.name == "id"

    def test_cascade_only_on_link_rows(self):
        for model, spec in LINKS.items():
            for fk in model.__table__.columns[0].foreign_keys:
                assert fk.ondelete == "CASCADE"


class TestLinkPrimaryKeys:
    def test_composite_primary_keys(self):
        assert [c.name for c in DocumentProduct.__table__.primary_key.columns] == [
            "document_id",
            "product_id",
        ]
        assert [c.name for c in DocumentVariant.__table__.primary_key.columns] == [
            "document_id",
            "variant_id",
        ]
        assert [c.name for c in DocumentBatch.__table__.primary_key.columns] == [
            "document_id",
            "batch_id",
        ]

    def test_no_single_column_primary_key(self):
        for model in LINKS:
            assert len(model.__table__.primary_key.columns) == 2

    def test_composite_pk_implies_uniqueness_of_pair(self):
        for model, spec in LINKS.items():
            columns = {c.name for c in model.__table__.primary_key.columns}
            assert columns == {spec[1], spec[2]}


class TestLinkIndexes:
    def test_index_on_product_id(self):
        indexes = {i.name: i for i in DocumentProduct.__table__.indexes}
        assert "ix_document_products_product_id" in indexes
        target = indexes["ix_document_products_product_id"]
        assert isinstance(target, Index)
        assert [c.name for c in target.columns] == ["product_id"]
        assert target.unique is False

    def test_index_on_variant_id(self):
        indexes = {i.name: i for i in DocumentVariant.__table__.indexes}
        assert "ix_document_variants_variant_id" in indexes
        target = indexes["ix_document_variants_variant_id"]
        assert [c.name for c in target.columns] == ["variant_id"]
        assert target.unique is False

    def test_index_on_batch_id(self):
        indexes = {i.name: i for i in DocumentBatch.__table__.indexes}
        assert "ix_document_batches_batch_id" in indexes
        target = indexes["ix_document_batches_batch_id"]
        assert [c.name for c in target.columns] == ["batch_id"]
        assert target.unique is False

    def test_no_index_on_document_id(self):
        # document_id покрыт составным PK, отдельный индекс не нужен
        for model in LINKS:
            index_names = {i.name for i in model.__table__.indexes}
            assert not any(name.endswith("document_id") for name in index_names)


def make_document(number="D-1"):
    return Document(document_type=DocumentType(name="Паспорт"), number=number)


def make_product(name="Труба ПЭ 100"):
    return Product(name=name, standard="ГОСТ 58121.2-2018")


def make_variant(product, size_text="Ø63 × 5.8"):
    return ProductVariant(product=product, size_text=size_text)


def make_batch(variant):
    return Batch(variant=variant)


class TestRelationships:
    def test_document_side_relationships_exist(self):
        for key, target in (
            ("products", Product),
            ("variants", ProductVariant),
            ("batches", Batch),
        ):
            relationship = Document.__mapper__.relationships[key]
            assert relationship.mapper.class_ is target
            assert relationship.uselist is True
            assert relationship.secondary is not None

    def test_entity_side_relationships_exist(self):
        for model in (Product, ProductVariant, Batch):
            relationship = model.__mapper__.relationships["documents"]
            assert relationship.mapper.class_ is Document
            assert relationship.secondary is not None

    def test_document_to_product_bidirectional(self):
        document = make_document()
        product = make_product()
        document.products.append(product)
        assert document.products == [product]
        assert product.documents == [document]

    def test_document_to_variant_bidirectional(self):
        document = make_document()
        product = make_product()
        variant = make_variant(product)
        document.variants.append(variant)
        assert document.variants == [variant]
        assert variant.documents == [document]

    def test_document_to_batch_bidirectional(self):
        document = make_document()
        product = make_product()
        variant = make_variant(product)
        batch = make_batch(variant)
        document.batches.append(batch)
        assert document.batches == [batch]
        assert batch.documents == [document]

    def test_document_without_links(self):
        document = make_document()
        assert document.products == []
        assert document.variants == []
        assert document.batches == []

    def test_one_document_many_variants(self):
        product = make_product()
        first = make_variant(product, "Ø63 × 5.8")
        second = make_variant(product, "Ø110 × 10.0")
        document = make_document()
        document.variants.append(first)
        document.variants.append(second)
        assert document.variants == [first, second]
        assert first.documents == [document]
        assert second.documents == [document]

    def test_one_document_many_batches(self):
        product = make_product()
        variant = make_variant(product)
        first = make_batch(variant)
        second = make_batch(variant)
        document = make_document()
        document.batches.append(first)
        document.batches.append(second)
        assert document.batches == [first, second]
        assert first.documents == [document]
        assert second.documents == [document]

    def test_one_product_many_documents(self):
        product = make_product()
        first = make_document("D-1")
        second = make_document("D-2")
        first.products.append(product)
        second.products.append(product)
        assert product.documents == [first, second]
        assert first.products == [product]
        assert second.products == [product]

    def test_one_variant_many_documents(self):
        product = make_product()
        variant = make_variant(product)
        first = make_document("D-1")
        second = make_document("D-2")
        first.variants.append(variant)
        second.variants.append(variant)
        assert variant.documents == [first, second]

    def test_one_batch_many_documents(self):
        product = make_product()
        variant = make_variant(product)
        batch = make_batch(variant)
        first = make_document("D-1")
        second = make_document("D-2")
        first.batches.append(batch)
        second.batches.append(batch)
        assert batch.documents == [first, second]

    def test_links_are_independent(self):
        document = make_document()
        product = make_product()
        variant = make_variant(product)
        document.products.append(product)
        assert document.variants == []
        assert document.batches == []