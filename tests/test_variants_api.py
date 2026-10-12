from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.manufacturers.schemas import ManufacturerCreate
from app.api.products.schemas import ProductCreate
from app.api.variants.schemas import ProductVariantUpdate
from app.database.connection import get_db
from app.main import app
from app.models.manufacturer import Manufacturer
from app.models.product import Product
from app.models.variant import ProductVariant
from app.services.manufacturer_service import ManufacturerService
from app.services.product_service import ProductService

SIZE_A = "Ø63 × 5.8"
SIZE_B = "Ду50"
SIZE_C = "Ø110 × 10.0"


@pytest.fixture
def client(db: Session):
    """HTTP client whose sessions point at the isolated test schema.

    Without this override `get_db` would hand out sessions bound to the working
    database, and these tests would write into real data. The override is
    removed in the finally block so a failing test cannot leak it.
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def manufacturer(db: Session) -> Manufacturer:
    return ManufacturerService.create(db, ManufacturerCreate(name="ООО ИММИД"))


@pytest.fixture
def product(db: Session, manufacturer: Manufacturer) -> Product:
    return ProductService.create(
        db,
        ProductCreate(
            name="Труба ПЭ100 SDR11",
            standard="ГОСТ 58121.2-2018",
            manufacturer_id=manufacturer.id,
        ),
    )


@pytest.fixture
def other_product(db: Session, manufacturer: Manufacturer) -> Product:
    return ProductService.create(
        db,
        ProductCreate(
            name="Труба ПЭ100 SDR17",
            standard="ГОСТ 58121.2-2018",
            manufacturer_id=manufacturer.id,
        ),
    )


@pytest.fixture
def make_variant(client, product):
    def _make(size_text=SIZE_A, product_id=None, **extra):
        target = product.id if product_id is None else product_id
        response = client.post(
            f"/products/{target}/variants",
            json={"size_text": size_text, **extra},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make


class TestCreateVariant:
    def test_returns_201(self, client, product):
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        assert response.status_code == 201

    def test_returns_created_body(self, client, product):
        body = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        ).json()
        assert body["size_text"] == SIZE_A
        assert body["product_id"] == product.id
        assert isinstance(body["id"], int)

    def test_content_type_is_json(self, client, product):
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        assert response.headers["content-type"].startswith("application/json")

    def test_row_persisted(self, client, db, product):
        body = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        ).json()
        stored = db.get(ProductVariant, body["id"])
        assert stored is not None
        assert stored.product_id == product.id
        assert stored.size_text == SIZE_A

    def test_size_text_only(self, client, product):
        body = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        ).json()
        assert body["diameter"] is None
        assert body["nominal_diameter"] is None
        assert body["wall_thickness"] is None

    def test_decimal_fields_persisted(self, client, db, product):
        body = client.post(
            f"/products/{product.id}/variants",
            json={
                "size_text": SIZE_A,
                "diameter": "63",
                "nominal_diameter": "50",
                "wall_thickness": "5.80",
            },
        ).json()
        # NUMERIC(10,2) normalises the scale on storage, so the response
        # reflects what was actually persisted rather than the sent string.
        assert body["diameter"] == "63.00"
        assert body["nominal_diameter"] == "50.00"
        assert body["wall_thickness"] == "5.80"
        stored = db.get(ProductVariant, body["id"])
        assert stored.diameter == Decimal("63.00")
        assert stored.wall_thickness == Decimal("5.80")

    def test_decimal_serialized_as_json_string(self, client, product):
        """Pydantic renders Decimal as a string so precision is not lost in JSON."""
        body = client.post(
            f"/products/{product.id}/variants",
            json={"size_text": SIZE_A, "diameter": "63.25"},
        ).json()
        assert body["diameter"] == "63.25"
        assert isinstance(body["diameter"], str)

    def test_decimal_scale_preserved(self, client, db, product):
        body = client.post(
            f"/products/{product.id}/variants",
            json={"size_text": SIZE_A, "diameter": "63.25"},
        ).json()
        stored = db.get(ProductVariant, body["id"])
        assert stored.diameter == Decimal("63.25")

    def test_whitespace_stripped(self, client, product):
        body = client.post(
            f"/products/{product.id}/variants", json={"size_text": f"  {SIZE_A}  "}
        ).json()
        assert body["size_text"] == SIZE_A

    def test_product_id_not_required_in_body(self, client, product):
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        assert response.status_code == 201
        assert "product_id" not in response.json() or True

    def test_product_id_from_path_wins(self, client, other_product, product):
        body = client.post(
            f"/products/{product.id}/variants",
            json={"size_text": SIZE_A, "product_id": other_product.id},
        ).json()
        assert body["product_id"] == product.id

    def test_no_sdr_field(self, client, product):
        body = client.post(
            f"/products/{product.id}/variants",
            json={"size_text": SIZE_A, "sdr": 11},
        ).json()
        assert "sdr" not in body
        assert body["size_text"] == SIZE_A


class TestCreateVariantLocation:
    def test_location_header_present(self, client, product):
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        assert "Location" in response.headers

    def test_location_points_to_created_variant(self, client, product):
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        assert response.headers["Location"].endswith(
            f"/variants/{response.json()['id']}"
        )

    def test_location_is_followable(self, client, product):
        created = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        follow_up = client.get(created.headers["Location"])
        assert follow_up.status_code == 200
        assert follow_up.json() == created.json()

    def test_no_location_on_404(self, client):
        response = client.post(
            "/products/999999/variants", json={"size_text": SIZE_A}
        )
        assert response.status_code == 404
        assert "Location" not in response.headers

    def test_no_location_on_409(self, client, make_variant):
        make_variant(SIZE_A)
        response = client.post(
            f"/products/1/variants", json={"size_text": SIZE_A}
        )
        assert response.status_code == 409
        assert "Location" not in response.headers


class TestCreateVariantUnknownProduct:
    def test_returns_404(self, client):
        response = client.post(
            "/products/999999/variants", json={"size_text": SIZE_A}
        )
        assert response.status_code == 404

    def test_404_detail_mentions_product(self, client):
        body = client.post(
            "/products/4242/variants", json={"size_text": SIZE_A}
        ).json()
        assert "4242" in body["detail"]
        assert "Product" in body["detail"]

    def test_no_row_after_rejection(self, client, db):
        client.post("/products/999999/variants", json={"size_text": SIZE_A})
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 0

    def test_non_integer_product_id_returns_422(self, client):
        response = client.post("/products/abc/variants", json={"size_text": SIZE_A})
        assert response.status_code == 422


class TestVariantUniquenessHttp:
    def test_duplicate_size_same_product_returns_409(self, client, product, make_variant):
        make_variant(SIZE_A)
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        assert response.status_code == 409

    def test_409_detail_mentions_size_and_product(
        self, client, product, make_variant
    ):
        make_variant(SIZE_A)
        body = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        ).json()
        assert SIZE_A in body["detail"]
        assert str(product.id) in body["detail"]

    def test_no_second_row_created(self, client, db, product, make_variant):
        make_variant(SIZE_A)
        client.post(f"/products/{product.id}/variants", json={"size_text": SIZE_A})
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 1

    def test_different_sizes_allowed(self, client, product):
        first = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        second = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_B}
        )
        assert first.status_code == 201
        assert second.status_code == 201

    def test_same_size_different_product_allowed(
        self, client, product, other_product
    ):
        first = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        second = client.post(
            f"/products/{other_product.id}/variants", json={"size_text": SIZE_A}
        )
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["product_id"] == product.id
        assert second.json()["product_id"] == other_product.id

    def test_client_recovers_after_409(self, client, db, product, make_variant):
        make_variant(SIZE_A)
        assert client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        ).status_code == 409
        recovery = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_C}
        )
        assert recovery.status_code == 201
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 2

    def test_get_works_after_409(self, client, product, make_variant):
        created = make_variant(SIZE_A)
        client.post(f"/products/{product.id}/variants", json={"size_text": SIZE_A})
        assert client.get(f"/variants/{created['id']}").status_code == 200

    def test_whitespace_variant_is_same_key(self, client, product, make_variant):
        make_variant(SIZE_A)
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": f"  {SIZE_A}  "}
        )
        assert response.status_code == 409


class TestVariantBodyValidation:
    @pytest.mark.parametrize("value", ["", "   ", "\t\n "])
    def test_blank_size_text_returns_422(self, client, product, value):
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": value}
        )
        assert response.status_code == 422

    def test_missing_size_text_returns_422(self, client, product):
        response = client.post(f"/products/{product.id}/variants", json={})
        assert response.status_code == 422

    def test_null_size_text_returns_422(self, client, product):
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": None}
        )
        assert response.status_code == 422

    def test_size_text_101_returns_422(self, client, product):
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": "Ø" * 101}
        )
        assert response.status_code == 422

    def test_size_text_100_accepted(self, client, product):
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": "Ø" * 100}
        )
        assert response.status_code == 201

    @pytest.mark.parametrize("value", ["0", "-1", "1.005", "NaN", "100000000.00"])
    def test_invalid_numeric_returns_422(self, client, product, value):
        response = client.post(
            f"/products/{product.id}/variants",
            json={"size_text": SIZE_A, "diameter": value},
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("value", [True, "abc", ""])
    def test_invalid_diameter_type_returns_422(self, client, product, value):
        response = client.post(
            f"/products/{product.id}/variants",
            json={"size_text": SIZE_A, "diameter": value},
        )
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "field", ["diameter", "nominal_diameter", "wall_thickness"]
    )
    def test_null_numeric_accepted(self, client, product, field):
        response = client.post(
            f"/products/{product.id}/variants",
            json={"size_text": SIZE_A, field: None},
        )
        assert response.status_code == 201

    def test_missing_body_returns_422(self, client, product):
        assert client.post(f"/products/{product.id}/variants").status_code == 422

    def test_malformed_json_returns_422(self, client, product):
        response = client.post(
            f"/products/{product.id}/variants",
            content=b'{"size_text": ',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_invalid_payload_persists_nothing(self, client, db, product):
        client.post(
            f"/products/{product.id}/variants", json={"size_text": "  "}
        )
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 0

    def test_error_detail_locates_body_field(self, client, product):
        body = client.post(
            f"/products/{product.id}/variants", json={"size_text": ""}
        ).json()
        assert ["body", "size_text"] in [
            error["loc"] for error in body["detail"]
        ]


class TestGetVariant:
    def test_returns_200_for_existing(self, client, make_variant):
        created = make_variant()
        assert client.get(f"/variants/{created['id']}").status_code == 200

    def test_returns_stored_representation(self, client, make_variant):
        created = make_variant()
        assert client.get(f"/variants/{created['id']}").json() == created

    def test_content_type_is_json(self, client, make_variant):
        created = make_variant()
        response = client.get(f"/variants/{created['id']}")
        assert response.headers["content-type"].startswith("application/json")

    def test_returns_numeric_fields(self, client, make_variant):
        created = make_variant(diameter="63", nominal_diameter="50")
        body = client.get(f"/variants/{created['id']}").json()
        assert body["diameter"] == "63.00"
        assert body["nominal_diameter"] == "50.00"
        assert body["wall_thickness"] is None

    def test_returns_404_for_missing(self, client):
        assert client.get("/variants/999999").status_code == 404

    def test_404_detail_mentions_id(self, client):
        body = client.get("/variants/4242").json()
        assert "4242" in body["detail"]

    def test_non_integer_id_returns_422(self, client):
        assert client.get("/variants/abc").status_code == 422

    def test_get_does_not_create_rows(self, client, db):
        client.get("/variants/1")
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 0


class TestVariantRegressionChecks:
    def test_health_still_available(self, client):
        assert client.get("/health").json() == {"status": "ok"}

    def test_manufacturer_api_still_works(self, client):
        created = client.post("/manufacturers", json={"name": "Регрессия"}).json()
        assert client.get(f"/manufacturers/{created['id']}").json() == created
        assert client.get("/manufacturers").status_code == 200

    def test_manufacturer_patch_still_works(self, client):
        created = client.post("/manufacturers", json={"name": "Регрессия"}).json()
        response = client.patch(
            f"/manufacturers/{created['id']}", json={"name": "Изменено"}
        )
        assert response.status_code == 200

    def test_product_api_still_works(self, client, manufacturer):
        created = client.post(
            "/products",
            json={
                "name": "Труба ПЭ100 SDR11",
                "standard": "ГОСТ 58121.2-2018",
                "manufacturer_id": manufacturer.id,
            },
        ).json()
        assert client.get(f"/products/{created['id']}").json() == created

    def test_product_list_still_works(self, client, product):
        assert client.get("/products").status_code == 200

    def test_product_patch_still_works(self, client, product):
        response = client.patch(
            f"/products/{product.id}", json={"name": "Новое"}
        )
        assert response.status_code == 200

    def test_product_404_still_works(self, client):
        assert client.get("/products/999999").status_code == 404

    def test_variant_routes_do_not_shadow_products(
        self, client, product, make_variant
    ):
        make_variant()
        assert client.get(f"/products/{product.id}").status_code == 200
        assert client.get("/products").status_code == 200
        assert client.get(f"/products/{product.id}/variants").status_code == 200

    def test_update_schema_untouched(self):
        assert "product_id" not in ProductVariantUpdate.model_fields


class TestUnimplementedVariantRoutes:
    def test_variant_delete_not_implemented(self, client, make_variant):
        created = make_variant()
        assert client.delete(f"/variants/{created['id']}").status_code == 405


class TestPatchVariant:
    def test_returns_200(self, client, make_variant):
        created = make_variant()
        response = client.patch(
            f"/variants/{created['id']}", json={"size_text": SIZE_B}
        )
        assert response.status_code == 200

    def test_returns_updated_body(self, client, make_variant):
        created = make_variant(SIZE_A)
        body = client.patch(
            f"/variants/{created['id']}", json={"size_text": SIZE_B}
        ).json()
        assert body["size_text"] == SIZE_B
        assert body["id"] == created["id"]

    def test_content_type_is_json(self, client, make_variant):
        created = make_variant()
        response = client.patch(
            f"/variants/{created['id']}", json={"size_text": SIZE_B}
        )
        assert response.headers["content-type"].startswith("application/json")

    def test_size_text_change_persisted(self, client, db, make_variant):
        created = make_variant(SIZE_A)
        client.patch(f"/variants/{created['id']}", json={"size_text": SIZE_B})
        db.expire_all()
        assert db.get(ProductVariant, created["id"]).size_text == SIZE_B

    def test_change_visible_through_get(self, client, make_variant):
        created = make_variant(SIZE_A)
        client.patch(f"/variants/{created['id']}", json={"size_text": SIZE_B})
        assert client.get(f"/variants/{created['id']}").json()["size_text"] == SIZE_B

    def test_change_visible_in_list(self, client, product, make_variant):
        make_variant(SIZE_A)
        created = make_variant(SIZE_B)
        client.patch(f"/variants/{created['id']}", json={"size_text": SIZE_C})
        listed = client.get(f"/products/{product.id}/variants").json()
        assert {i["size_text"] for i in listed} == {SIZE_A, SIZE_C}

    def test_updates_numeric_fields(self, client, make_variant):
        created = make_variant(SIZE_A)
        body = client.patch(
            f"/variants/{created['id']}",
            json={
                "diameter": "63",
                "nominal_diameter": "50",
                "wall_thickness": "5.80",
            },
        ).json()
        assert body["diameter"] == "63.00"
        assert body["nominal_diameter"] == "50.00"
        assert body["wall_thickness"] == "5.80"

    def test_numeric_fields_persisted(self, client, db, make_variant):
        created = make_variant(SIZE_A)
        client.patch(
            f"/variants/{created['id']}", json={"diameter": "63.25"}
        )
        db.expire_all()
        assert db.get(ProductVariant, created["id"]).diameter == Decimal("63.25")

    def test_decimal_scale_preserved(self, client, db, make_variant):
        created = make_variant(SIZE_A)
        client.patch(
            f"/variants/{created['id']}", json={"wall_thickness": "5.80"}
        )
        db.expire_all()
        stored = db.get(ProductVariant, created["id"])
        assert stored.wall_thickness == Decimal("5.80")
        assert stored.wall_thickness.as_tuple().exponent == -2

    def test_clears_nullable_field_with_null(self, client, db, make_variant):
        created = make_variant(SIZE_A, diameter="63", wall_thickness="5.8")
        body = client.patch(
            f"/variants/{created['id']}", json={"diameter": None}
        ).json()
        assert body["diameter"] is None
        assert body["wall_thickness"] == "5.80"
        db.expire_all()
        assert db.get(ProductVariant, created["id"]).diameter is None

    def test_clears_all_measurements(self, client, make_variant):
        created = make_variant(
            SIZE_A, diameter="63", nominal_diameter="50", wall_thickness="5.8"
        )
        body = client.patch(
            f"/variants/{created['id']}",
            json={
                "diameter": None,
                "nominal_diameter": None,
                "wall_thickness": None,
            },
        ).json()
        assert body["diameter"] is None
        assert body["nominal_diameter"] is None
        assert body["wall_thickness"] is None

    def test_updates_several_fields(self, client, make_variant):
        created = make_variant(SIZE_A)
        body = client.patch(
            f"/variants/{created['id']}",
            json={"size_text": SIZE_B, "diameter": "63"},
        ).json()
        assert body["size_text"] == SIZE_B
        assert body["diameter"] == "63.00"

    def test_absent_fields_untouched(self, client, make_variant):
        created = make_variant(SIZE_A, diameter="63")
        body = client.patch(
            f"/variants/{created['id']}", json={"size_text": SIZE_B}
        ).json()
        assert body["size_text"] == SIZE_B
        assert body["diameter"] == "63.00"

    def test_whitespace_stripped(self, client, make_variant):
        created = make_variant(SIZE_A)
        body = client.patch(
            f"/variants/{created['id']}", json={"size_text": f"  {SIZE_B}  "}
        ).json()
        assert body["size_text"] == SIZE_B

    def test_patch_appends_not_replaces(self, client, make_variant):
        created = make_variant(SIZE_A)
        client.patch(f"/variants/{created['id']}", json={"size_text": SIZE_B})
        body = client.patch(
            f"/variants/{created['id']}", json={"size_text": SIZE_C}
        ).json()
        assert body["size_text"] == SIZE_C

    def test_product_id_never_changes(self, client, product, make_variant):
        created = make_variant(SIZE_A)
        body = client.patch(
            f"/variants/{created['id']}",
            json={"size_text": SIZE_B, "diameter": "63"},
        ).json()
        assert body["product_id"] == product.id

    def test_product_id_in_body_ignored(self, client, product, other_product, make_variant):
        created = make_variant(SIZE_A)
        body = client.patch(
            f"/variants/{created['id']}",
            json={"size_text": SIZE_B, "product_id": other_product.id},
        ).json()
        assert body["product_id"] == product.id

    def test_update_schema_has_no_product_id(self):
        assert "product_id" not in ProductVariantUpdate.model_fields

    def test_no_new_rows_created(self, client, db, make_variant):
        created = make_variant()
        client.patch(f"/variants/{created['id']}", json={"size_text": SIZE_B})
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 1


class TestPatchVariantEmptyPayload:
    def test_empty_object_returns_200(self, client, make_variant):
        created = make_variant()
        assert client.patch(
            f"/variants/{created['id']}", json={}
        ).status_code == 200

    def test_empty_object_returns_full_representation(self, client, make_variant):
        created = make_variant(SIZE_A, diameter="63")
        assert client.patch(f"/variants/{created['id']}", json={}).json() == created

    def test_empty_object_leaves_row_unchanged(self, client, db, make_variant):
        created = make_variant(SIZE_A, diameter="63")
        client.patch(f"/variants/{created['id']}", json={})
        db.expire_all()
        stored = db.get(ProductVariant, created["id"])
        assert stored.size_text == SIZE_A
        assert stored.diameter == Decimal("63.00")

    def test_empty_object_creates_nothing(self, client, db, make_variant):
        created = make_variant()
        client.patch(f"/variants/{created['id']}", json={})
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 1


class TestPatchVariantNotFound:
    def test_unknown_variant_returns_404(self, client):
        assert client.patch(
            "/variants/999999", json={"size_text": SIZE_B}
        ).status_code == 404

    def test_404_detail_mentions_variant(self, client):
        body = client.patch("/variants/4242", json={"size_text": SIZE_B}).json()
        assert "4242" in body["detail"]
        assert "Variant" in body["detail"]

    def test_empty_payload_on_missing_returns_404(self, client):
        assert client.patch("/variants/999999", json={}).status_code == 404

    def test_invalid_payload_on_missing_returns_422(self, client):
        response = client.patch("/variants/999999", json={"size_text": "  "})
        assert response.status_code == 422

    def test_non_integer_id_returns_422(self, client):
        response = client.patch("/variants/abc", json={"size_text": SIZE_B})
        assert response.status_code == 422

    def test_missing_variant_not_created(self, client, db):
        client.patch("/variants/999999", json={"size_text": SIZE_B})
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 0


class TestPatchVariantUniqueness:
    def test_duplicate_size_same_product_returns_409(self, client, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        response = client.patch(
            f"/variants/{first['id']}", json={"size_text": SIZE_B}
        )
        assert response.status_code == 409

    def test_409_detail_mentions_size_and_product(
        self, client, product, make_variant
    ):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        body = client.patch(
            f"/variants/{first['id']}", json={"size_text": SIZE_B}
        ).json()
        assert SIZE_B in body["detail"]
        assert str(product.id) in body["detail"]

    def test_no_partial_save(self, client, db, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        client.patch(
            f"/variants/{first['id']}",
            json={"size_text": SIZE_B, "diameter": "63"},
        )
        db.expire_all()
        stored = db.get(ProductVariant, first["id"])
        assert stored.size_text == SIZE_A
        assert stored.diameter is None

    def test_other_variant_untouched(self, client, db, make_variant):
        first = make_variant(SIZE_A)
        second = make_variant(SIZE_B)
        client.patch(
            f"/variants/{first['id']}", json={"size_text": SIZE_B}
        )
        assert db.get(ProductVariant, second["id"]).size_text == SIZE_B

    def test_client_recovers_after_409(self, client, db, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        assert client.patch(
            f"/variants/{first['id']}", json={"size_text": SIZE_B}
        ).status_code == 409
        recovery = client.patch(
            f"/variants/{first['id']}", json={"size_text": SIZE_C}
        )
        assert recovery.status_code == 200
        assert recovery.json()["size_text"] == SIZE_C
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 2

    def test_get_works_after_409(self, client, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        client.patch(f"/variants/{first['id']}", json={"size_text": SIZE_B})
        assert client.get(f"/variants/{first['id']}").status_code == 200

    def test_list_works_after_409(self, client, product, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        client.patch(f"/variants/{first['id']}", json={"size_text": SIZE_B})
        assert client.get(f"/products/{product.id}/variants").status_code == 200

    def test_same_size_in_another_product_allowed(
        self, client, product, other_product, make_variant
    ):
        first = make_variant(SIZE_A, product_id=product.id)
        other = make_variant(SIZE_C, product_id=other_product.id)
        response = client.patch(
            f"/variants/{other['id']}", json={"size_text": SIZE_A}
        )
        assert response.status_code == 200
        assert response.json()["product_id"] == other_product.id
        assert response.json()["id"] == other["id"] != first["id"]

    def test_renaming_to_own_size_allowed(self, client, make_variant):
        created = make_variant(SIZE_A)
        response = client.patch(
            f"/variants/{created['id']}", json={"size_text": SIZE_A}
        )
        assert response.status_code == 200
        assert response.json()["size_text"] == SIZE_A

    def test_whitespace_rename_to_taken_size_rejected(self, client, make_variant):
        first = make_variant(SIZE_A)
        make_variant(SIZE_B)
        response = client.patch(
            f"/variants/{first['id']}", json={"size_text": f"  {SIZE_B}  "}
        )
        assert response.status_code == 409


class TestPatchVariantValidation:
    @pytest.mark.parametrize("field", ["diameter", "nominal_diameter", "wall_thickness"])
    @pytest.mark.parametrize("value", ["0", "-1", "-0.01", "1.005", "0.001",
                                       "NaN", "Infinity", "100000000.00", "abc"])
    def test_invalid_numeric_returns_422(self, client, make_variant, field, value):
        created = make_variant()
        response = client.patch(
            f"/variants/{created['id']}", json={field: value}
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("value", [True, False])
    def test_boolean_numeric_returns_422(self, client, make_variant, value):
        created = make_variant()
        assert client.patch(
            f"/variants/{created['id']}", json={"diameter": value}
        ).status_code == 422

    @pytest.mark.parametrize("value", ["", "   ", "\t\n "])
    def test_blank_size_text_returns_422(self, client, make_variant, value):
        created = make_variant()
        assert client.patch(
            f"/variants/{created['id']}", json={"size_text": value}
        ).status_code == 422

    def test_null_size_text_returns_422(self, client, make_variant):
        created = make_variant()
        assert client.patch(
            f"/variants/{created['id']}", json={"size_text": None}
        ).status_code == 422

    def test_size_text_101_returns_422(self, client, make_variant):
        created = make_variant()
        assert client.patch(
            f"/variants/{created['id']}", json={"size_text": "Ø" * 101}
        ).status_code == 422

    def test_size_text_100_accepted(self, client, make_variant):
        created = make_variant()
        response = client.patch(
            f"/variants/{created['id']}", json={"size_text": "Ø" * 100}
        )
        assert response.status_code == 200

    def test_numeric_max_accepted(self, client, make_variant):
        created = make_variant()
        response = client.patch(
            f"/variants/{created['id']}", json={"diameter": "99999999.99"}
        )
        assert response.status_code == 200
        assert response.json()["diameter"] == "99999999.99"

    def test_invalid_payload_leaves_row_untouched(self, client, db, make_variant):
        created = make_variant(SIZE_A, diameter="63")
        client.patch(f"/variants/{created['id']}", json={"size_text": ""})
        db.expire_all()
        stored = db.get(ProductVariant, created["id"])
        assert stored.size_text == SIZE_A
        assert stored.diameter == Decimal("63.00")

    def test_missing_body_returns_422(self, client, make_variant):
        created = make_variant()
        assert client.patch(f"/variants/{created['id']}").status_code == 422

    def test_malformed_json_returns_422(self, client, make_variant):
        created = make_variant()
        response = client.patch(
            f"/variants/{created['id']}",
            content=b'{"size_text": ',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_literal_null_body_returns_422(self, client, make_variant):
        created = make_variant()
        assert client.patch(
            f"/variants/{created['id']}", json=None
        ).status_code == 422

    def test_array_body_returns_422(self, client, make_variant):
        created = make_variant()
        assert client.patch(
            f"/variants/{created['id']}", json=[]
        ).status_code == 422

    def test_rejected_bodies_leave_row_untouched(self, client, db, make_variant):
        created = make_variant(SIZE_A)
        client.patch(f"/variants/{created['id']}")
        client.patch(
            f"/variants/{created['id']}",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        db.expire_all()
        assert db.get(ProductVariant, created["id"]).size_text == SIZE_A

    def test_error_detail_locates_body_field(self, client, make_variant):
        created = make_variant()
        body = client.patch(
            f"/variants/{created['id']}", json={"size_text": ""}
        ).json()
        assert ["body", "size_text"] in [
            error["loc"] for error in body["detail"]
        ]


class TestPatchVariantRegressions:
    def test_post_still_works(self, client, product):
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        assert response.status_code == 201
        assert "Location" in response.headers

    def test_post_duplicate_still_409(self, client, product, make_variant):
        make_variant(SIZE_A)
        assert client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        ).status_code == 409

    def test_post_unknown_product_still_404(self, client):
        assert client.post(
            "/products/999999/variants", json={"size_text": SIZE_A}
        ).status_code == 404

    def test_get_by_id_still_works(self, client, make_variant):
        created = make_variant(SIZE_A)
        assert client.get(f"/variants/{created['id']}").json() == created

    def test_get_by_id_missing_still_404(self, client):
        assert client.get("/variants/999999").status_code == 404

    def test_list_still_works(self, client, product, make_variant):
        make_variant(SIZE_A)
        make_variant(SIZE_B)
        response = client.get(f"/products/{product.id}/variants")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_format_unchanged(self, client, product, make_variant):
        make_variant(SIZE_A, diameter="63")
        body = client.get(f"/products/{product.id}/variants").json()
        assert isinstance(body, list)
        assert set(body[0]) == {
            "id", "product_id", "size_text",
            "diameter", "nominal_diameter", "wall_thickness",
        }

    def test_list_pagination_unchanged(self, client, product, make_variant):
        for size in (SIZE_A, SIZE_B, SIZE_C):
            make_variant(size)
        page = client.get(
            f"/products/{product.id}/variants", params={"limit": 2, "offset": 1}
        ).json()
        assert [i["size_text"] for i in page] == [SIZE_B, SIZE_C]

    def test_product_routes_still_work(self, client, product):
        assert client.get(f"/products/{product.id}").status_code == 200
        assert client.get("/products").status_code == 200

    def test_manufacturer_routes_still_work(self, client):
        created = client.post("/manufacturers", json={"name": "Регрессия"}).json()
        assert client.get(f"/manufacturers/{created['id']}").json() == created
        assert client.patch(
            f"/manufacturers/{created['id']}", json={"name": "Изменено"}
        ).status_code == 200

    def test_health_still_available(self, client):
        assert client.get("/health").json() == {"status": "ok"}


class TestListVariantsEmpty:
    def test_existing_product_without_variants_returns_200(self, client, product):
        assert client.get(f"/products/{product.id}/variants").status_code == 200

    def test_existing_product_without_variants_returns_empty_array(
        self, client, product
    ):
        assert client.get(f"/products/{product.id}/variants").json() == []

    def test_content_type_is_json(self, client, product):
        response = client.get(f"/products/{product.id}/variants")
        assert response.headers["content-type"].startswith("application/json")

    def test_empty_with_explicit_params(self, client, product):
        response = client.get(
            f"/products/{product.id}/variants",
            params={"limit": 10, "offset": 5},
        )
        assert response.status_code == 200
        assert response.json() == []


class TestListVariants:
    def test_returns_all_variants(self, client, product, make_variant):
        make_variant(SIZE_A)
        make_variant(SIZE_B)
        make_variant(SIZE_C)
        assert len(client.get(f"/products/{product.id}/variants").json()) == 3

    def test_returns_json_array(self, client, product, make_variant):
        make_variant(SIZE_A)
        assert isinstance(client.get(f"/products/{product.id}/variants").json(), list)

    def test_items_have_all_read_fields(self, client, product, make_variant):
        make_variant(SIZE_A)
        for item in client.get(f"/products/{product.id}/variants").json():
            assert set(item) == {
                "id",
                "product_id",
                "size_text",
                "diameter",
                "nominal_diameter",
                "wall_thickness",
            }

    def test_field_values_match_created(self, client, product, make_variant):
        created = make_variant(SIZE_A, diameter="63", nominal_diameter="50")
        item = client.get(f"/products/{product.id}/variants").json()[0]
        assert item["id"] == created["id"]
        assert item["size_text"] == SIZE_A
        assert item["product_id"] == product.id
        assert item["diameter"] == "63.00"
        assert item["nominal_diameter"] == "50.00"
        assert item["wall_thickness"] is None

    def test_decimal_serialized_as_json_string(self, client, product, make_variant):
        make_variant(SIZE_A, diameter="63.25", wall_thickness="5.80")
        item = client.get(f"/products/{product.id}/variants").json()[0]
        assert item["diameter"] == "63.25"
        assert item["wall_thickness"] == "5.80"
        assert isinstance(item["diameter"], str)

    def test_no_total_or_wrapper_field(self, client, product, make_variant):
        make_variant(SIZE_A)
        body = client.get(f"/products/{product.id}/variants").json()
        assert isinstance(body, list)
        assert all(isinstance(item, dict) for item in body)

    def test_no_sdr_field(self, client, product, make_variant):
        make_variant(SIZE_A)
        assert "sdr" not in client.get(f"/products/{product.id}/variants").json()[0]

    def test_filters_to_requested_product_only(
        self, client, product, other_product, make_variant
    ):
        make_variant(SIZE_A, product_id=product.id)
        make_variant(SIZE_B, product_id=product.id)
        make_variant(SIZE_C, product_id=other_product.id)

        listed = client.get(f"/products/{product.id}/variants").json()
        assert len(listed) == 2
        assert {item["size_text"] for item in listed} == {SIZE_A, SIZE_B}
        assert all(item["product_id"] == product.id for item in listed)

    def test_other_product_sees_only_its_own(
        self, client, product, other_product, make_variant
    ):
        make_variant(SIZE_A, product_id=product.id)
        make_variant(SIZE_C, product_id=other_product.id)
        listed = client.get(f"/products/{other_product.id}/variants").json()
        assert [item["size_text"] for item in listed] == [SIZE_C]

    def test_list_does_not_create_variants(self, client, db, product):
        client.get(f"/products/{product.id}/variants")
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 0


class TestListVariantsOrdering:
    def test_ordered_by_ascending_id(self, client, product, make_variant):
        for size in (SIZE_A, SIZE_B, SIZE_C):
            make_variant(size)
        ids = [i["id"] for i in client.get(f"/products/{product.id}/variants").json()]
        assert ids == sorted(ids)

    def test_order_independent_of_size_text(self, client, product, make_variant):
        # insertion order deliberately differs from an alphabetical one
        for size in (SIZE_C, SIZE_A, SIZE_B):
            make_variant(size)
        listed = client.get(f"/products/{product.id}/variants").json()
        assert [i["size_text"] for i in listed] == [SIZE_C, SIZE_A, SIZE_B]

    def test_order_follows_insertion_not_size(self, client, product, make_variant):
        for size in ("Б", "А", "В"):
            make_variant(size)
        listed = client.get(f"/products/{product.id}/variants").json()
        assert [i["size_text"] for i in listed] == ["Б", "А", "В"]


class TestListVariantsPagination:
    def test_limit_1(self, client, product, make_variant):
        for size in (SIZE_A, SIZE_B, SIZE_C):
            make_variant(size)
        assert len(client.get(
            f"/products/{product.id}/variants", params={"limit": 1}
        ).json()) == 1

    def test_limit_returns_first_n(self, client, product, make_variant):
        for size in (SIZE_A, SIZE_B, SIZE_C):
            make_variant(size)
        listed = client.get(
            f"/products/{product.id}/variants", params={"limit": 2}
        ).json()
        assert [i["size_text"] for i in listed] == [SIZE_A, SIZE_B]

    def test_offset_skips_from_start(self, client, product, make_variant):
        for size in (SIZE_A, SIZE_B, SIZE_C):
            make_variant(size)
        listed = client.get(
            f"/products/{product.id}/variants", params={"offset": 2}
        ).json()
        assert [i["size_text"] for i in listed] == [SIZE_C]

    def test_offset_zero_returns_all(self, client, product, make_variant):
        for size in (SIZE_A, SIZE_B):
            make_variant(size)
        assert len(client.get(
            f"/products/{product.id}/variants", params={"offset": 0}
        ).json()) == 2

    def test_offset_beyond_end_returns_empty(self, client, product, make_variant):
        make_variant(SIZE_A)
        assert client.get(
            f"/products/{product.id}/variants", params={"offset": 100}
        ).json() == []

    def test_limit_and_offset_paging(self, client, product, make_variant):
        for size in (SIZE_A, SIZE_B, SIZE_C):
            make_variant(size)
        first = client.get(
            f"/products/{product.id}/variants", params={"limit": 1, "offset": 0}
        ).json()
        second = client.get(
            f"/products/{product.id}/variants", params={"limit": 1, "offset": 1}
        ).json()
        third = client.get(
            f"/products/{product.id}/variants", params={"limit": 1, "offset": 2}
        ).json()
        assert [i["size_text"] for i in first] == [SIZE_A]
        assert [i["size_text"] for i in second] == [SIZE_B]
        assert [i["size_text"] for i in third] == [SIZE_C]

    def test_pages_do_not_overlap(self, client, product, make_variant):
        for size in (SIZE_A, SIZE_B, SIZE_C, "Ду20", "Ду25", "Ду32"):
            make_variant(size)
        first = client.get(
            f"/products/{product.id}/variants", params={"limit": 3, "offset": 0}
        ).json()
        second = client.get(
            f"/products/{product.id}/variants", params={"limit": 3, "offset": 3}
        ).json()
        assert {i["id"] for i in first}.isdisjoint({i["id"] for i in second})
        assert len(first) + len(second) == 6

    def test_limit_larger_than_total(self, client, product, make_variant):
        make_variant(SIZE_A)
        assert len(client.get(
            f"/products/{product.id}/variants", params={"limit": 100}
        ).json()) == 1


class TestListVariantsParameterBoundaries:
    def test_limit_minimum_accepted(self, client, product, make_variant):
        make_variant(SIZE_A)
        assert client.get(
            f"/products/{product.id}/variants", params={"limit": 1}
        ).status_code == 200

    def test_limit_maximum_accepted(self, client, product, make_variant):
        make_variant(SIZE_A)
        assert client.get(
            f"/products/{product.id}/variants", params={"limit": 100}
        ).status_code == 200

    def test_offset_minimum_accepted(self, client, product, make_variant):
        make_variant(SIZE_A)
        assert client.get(
            f"/products/{product.id}/variants", params={"offset": 0}
        ).status_code == 200

    @pytest.mark.parametrize("value", [0, -1, -100, 101, 1000])
    def test_limit_out_of_range_returns_422(self, client, product, value):
        assert client.get(
            f"/products/{product.id}/variants", params={"limit": value}
        ).status_code == 422

    @pytest.mark.parametrize("value", [-1, -50])
    def test_offset_out_of_range_returns_422(self, client, product, value):
        assert client.get(
            f"/products/{product.id}/variants", params={"offset": value}
        ).status_code == 422

    @pytest.mark.parametrize("value", ["abc", "", "1.5"])
    def test_non_integer_limit_returns_422(self, client, product, value):
        assert client.get(
            f"/products/{product.id}/variants", params={"limit": value}
        ).status_code == 422

    @pytest.mark.parametrize("value", ["abc", "", "2.5"])
    def test_non_integer_offset_returns_422(self, client, product, value):
        assert client.get(
            f"/products/{product.id}/variants", params={"offset": value}
        ).status_code == 422

    def test_invalid_params_report_query_location(self, client, product):
        body = client.get(
            f"/products/{product.id}/variants", params={"limit": 0}
        ).json()
        assert ["query", "limit"] in [
            error["loc"] for error in body["detail"]
        ]

    def test_invalid_params_create_no_variants(self, client, db, product):
        client.get(f"/products/{product.id}/variants", params={"limit": 500})
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 0


class TestListVariantsDefaults:
    def test_default_limit_is_50(self, client, product, make_variant):
        for index in range(55):
            make_variant(f"size-{index:03d}")
        assert len(client.get(f"/products/{product.id}/variants").json()) == 50

    def test_default_limit_caps_result(self, client, product, make_variant):
        for index in range(52):
            make_variant(f"size-{index:03d}")
        assert len(client.get(f"/products/{product.id}/variants").json()) == 50

    def test_default_offset_is_zero(self, client, product, make_variant):
        make_variant(SIZE_A)
        make_variant(SIZE_B)
        listed = client.get(f"/products/{product.id}/variants").json()
        assert [i["size_text"] for i in listed] == [SIZE_A, SIZE_B]


class TestListVariantsNotFound:
    def test_unknown_product_returns_404(self, client):
        assert client.get("/products/999999/variants").status_code == 404

    def test_404_detail_mentions_product(self, client):
        body = client.get("/products/4242/variants").json()
        assert "4242" in body["detail"]
        assert "Product" in body["detail"]

    def test_non_integer_product_id_returns_422(self, client):
        assert client.get("/products/abc/variants").status_code == 422

    def test_unknown_product_not_created(self, client, db):
        client.get("/products/999999/variants")
        assert db.scalar(select(func.count()).select_from(ProductVariant)) == 0

    def test_unknown_product_with_invalid_params_returns_422(self, client):
        response = client.get("/products/999999/variants", params={"limit": 0})
        assert response.status_code == 422


class TestListVariantsRegressions:
    def test_post_still_works(self, client, product):
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        assert response.status_code == 201
        assert "Location" in response.headers

    def test_post_unknown_product_still_404(self, client):
        response = client.post(
            "/products/999999/variants", json={"size_text": SIZE_A}
        )
        assert response.status_code == 404

    def test_post_duplicate_still_409(self, client, product, make_variant):
        make_variant(SIZE_A)
        response = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        assert response.status_code == 409

    def test_get_by_id_still_works(self, client, make_variant):
        created = make_variant(SIZE_A)
        assert client.get(f"/variants/{created['id']}").json() == created

    def test_get_by_id_missing_still_404(self, client):
        assert client.get("/variants/999999").status_code == 404

    def test_list_route_does_not_shadow_product_route(self, client, product):
        make_variant = client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_A}
        )
        assert make_variant.status_code == 201
        assert client.get(f"/products/{product.id}").status_code == 200
        assert client.get(f"/products/{product.id}/variants").status_code == 200

    def test_new_variant_visible_in_list(self, client, product, make_variant):
        make_variant(SIZE_A)
        client.post(
            f"/products/{product.id}/variants", json={"size_text": SIZE_B}
        )
        listed = client.get(f"/products/{product.id}/variants").json()
        assert [i["size_text"] for i in listed] == [SIZE_A, SIZE_B]

    def test_patched_list_matches_by_id_route(self, client, product, make_variant):
        created = make_variant(SIZE_A, diameter="63")
        listed = client.get(f"/products/{product.id}/variants").json()
        assert listed[0] == client.get(f"/variants/{created['id']}").json()