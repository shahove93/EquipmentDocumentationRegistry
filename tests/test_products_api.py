import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.manufacturers.schemas import ManufacturerCreate
from app.database.connection import get_db
from app.main import app
from app.models.manufacturer import Manufacturer
from app.models.product import Product
from app.services.manufacturer_service import ManufacturerService

VALID_PRODUCT = {
    "name": "Труба ПЭ100 SDR11",
    "standard": "ГОСТ 58121.2-2018",
}


@pytest.fixture
def client(db: Session):
    """HTTP client whose sessions point at the isolated test schema.

    Without this override `get_db` would hand out sessions bound to the working
    database, and these tests would write into real data. The overrides are
    cleared in the finally block so a failing test cannot leak them.
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
def make_product(client, db, manufacturer):
    """Create a product over HTTP and return the response body."""
    counter = {"n": 0}

    def _make(**overrides):
        counter["n"] += 1
        payload = {
            **VALID_PRODUCT,
            "manufacturer_id": manufacturer.id,
            **overrides,
        }
        response = client.post("/products", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _make


class TestCreateProduct:
    def test_returns_201(self, client, manufacturer):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id}
        )
        assert response.status_code == 201

    def test_returns_created_body(self, client, manufacturer):
        body = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id}
        ).json()
        assert body["name"] == "Труба ПЭ100 SDR11"
        assert body["standard"] == "ГОСТ 58121.2-2018"
        assert body["manufacturer_id"] == manufacturer.id
        assert isinstance(body["id"], int)

    def test_content_type_is_json(self, client, manufacturer):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id}
        )
        assert response.headers["content-type"].startswith("application/json")

    def test_all_fields_persisted(self, client, db, manufacturer):
        body = client.post(
            "/products",
            json={
                **VALID_PRODUCT,
                "manufacturer_id": manufacturer.id,
                "designation": "ТРУБА_ПЭ_110_SDR11",
                "product_type": "труба",
            },
        ).json()
        stored = db.get(Product, body["id"])
        assert stored.name == "Труба ПЭ100 SDR11"
        assert stored.standard == "ГОСТ 58121.2-2018"
        assert stored.manufacturer_id == manufacturer.id
        assert stored.designation == "ТРУБА_ПЭ_110_SDR11"
        assert stored.product_type == "труба"

    def test_response_contains_every_stored_field(self, client, manufacturer):
        body = client.post(
            "/products",
            json={
                **VALID_PRODUCT,
                "manufacturer_id": manufacturer.id,
                "designation": "АРТ-1",
                "product_type": "труба",
            },
        ).json()
        assert set(body) == {
            "id",
            "name",
            "standard",
            "manufacturer_id",
            "designation",
            "product_type",
        }
        assert body["designation"] == "АРТ-1"
        assert body["product_type"] == "труба"

    def test_optional_fields_default_to_null(self, client, manufacturer):
        body = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id}
        ).json()
        assert body["designation"] is None
        assert body["product_type"] is None

    def test_explicit_null_optional_accepted(self, client, manufacturer):
        response = client.post(
            "/products",
            json={
                **VALID_PRODUCT,
                "manufacturer_id": manufacturer.id,
                "designation": None,
                "product_type": None,
            },
        )
        assert response.status_code == 201

    def test_sdr_is_part_of_name(self, client, manufacturer):
        body = client.post(
            "/products",
            json={
                "name": "Труба ПЭ100 SDR17",
                "standard": "ГОСТ 58121.2-2018",
                "manufacturer_id": manufacturer.id,
            },
        ).json()
        assert body["name"] == "Труба ПЭ100 SDR17"
        assert "sdr" not in body

    def test_surrounding_whitespace_stripped(self, client, manufacturer):
        body = client.post(
            "/products",
            json={
                "name": "  Труба ПЭ100 SDR11  ",
                "standard": "  ГОСТ 58121.2-2018  ",
                "manufacturer_id": manufacturer.id,
                "designation": "  АРТ-1  ",
                "product_type": "  труба  ",
            },
        ).json()
        assert body["name"] == "Труба ПЭ100 SDR11"
        assert body["standard"] == "ГОСТ 58121.2-2018"
        assert body["designation"] == "АРТ-1"
        assert body["product_type"] == "труба"

    def test_duplicate_names_allowed(self, client, manufacturer):
        first = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id}
        )
        second = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id}
        )
        assert first.status_code == second.status_code == 201
        assert first.json()["id"] != second.json()["id"]


class TestCreateProductLocationHeader:
    def test_location_header_present(self, client, manufacturer):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id}
        )
        assert "Location" in response.headers

    def test_location_points_to_created_resource(self, client, manufacturer):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id}
        )
        assert response.headers["Location"].endswith(
            f"/products/{response.json()['id']}"
        )

    def test_location_is_followable(self, client, manufacturer):
        created = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id}
        )
        follow_up = client.get(created.headers["Location"])
        assert follow_up.status_code == 200
        assert follow_up.json() == created.json()

    def test_no_location_on_rejected_manufacturer(self, client):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": 999_999}
        )
        assert response.status_code == 404
        assert "Location" not in response.headers


class TestCreateProductUnknownManufacturer:
    def test_returns_404(self, client):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": 999_999}
        )
        assert response.status_code == 404

    def test_404_detail_mentions_manufacturer(self, client):
        body = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": 4242}
        ).json()
        assert "4242" in body["detail"]
        assert "Manufacturer" in body["detail"]

    def test_no_new_row_after_rejection(self, client, db):
        client.post("/products", json={**VALID_PRODUCT, "manufacturer_id": 999_999})
        assert db.scalar(select(func.count()).select_from(Product)) == 0

    def test_existing_rows_untouched_after_rejection(self, client, db, make_product):
        make_product()
        client.post("/products", json={**VALID_PRODUCT, "manufacturer_id": 999_999})
        assert db.scalar(select(func.count()).select_from(Product)) == 1


class TestCreateProductValidation:
    @pytest.mark.parametrize("field", ["name", "standard"])
    @pytest.mark.parametrize("value", ["", "   ", "\t\n "])
    def test_blank_required_text_rejected(self, client, manufacturer, field, value):
        response = client.post(
            "/products",
            json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id, field: value},
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("field", ["name", "standard", "manufacturer_id"])
    def test_missing_required_field_rejected(self, client, manufacturer, field):
        payload = {**VALID_PRODUCT, "manufacturer_id": manufacturer.id}
        payload.pop(field)
        assert client.post("/products", json=payload).status_code == 422

    def test_empty_payload_rejected(self, client):
        assert client.post("/products", json={}).status_code == 422

    def test_missing_body_rejected(self, client):
        assert client.post("/products").status_code == 422

    def test_error_detail_locates_body_field(self, client, manufacturer):
        body = client.post(
            "/products",
            json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id, "name": ""},
        ).json()
        assert ["body", "name"] in [error["loc"] for error in body["detail"]]

    @pytest.mark.parametrize("value", [True, False])
    def test_boolean_manufacturer_id_rejected(self, client, value):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": value}
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("value", [1.5, 2.9])
    def test_fractional_manufacturer_id_rejected(self, client, value):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": value}
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("value", [0, -1, -100])
    def test_non_positive_manufacturer_id_rejected(self, client, value):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": value}
        )
        assert response.status_code == 422

    def test_null_manufacturer_id_rejected(self, client):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": None}
        )
        assert response.status_code == 422

    def test_string_manufacturer_id_rejected(self, client):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": "abc"}
        )
        assert response.status_code == 422

    def test_unknown_field_ignored(self, client, manufacturer):
        response = client.post(
            "/products",
            json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id, "sdr": 11},
        )
        assert response.status_code == 201
        assert "sdr" not in response.json()

    def test_nothing_persisted_on_invalid_payload(self, client, db, manufacturer):
        client.post(
            "/products",
            json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id, "name": ""},
        )
        assert db.scalar(select(func.count()).select_from(Product)) == 0


class TestCreateProductBoundaries:
    @pytest.mark.parametrize("field", ["name", "standard"])
    def test_length_255_accepted(self, client, manufacturer, field):
        value = "Я" * 255
        response = client.post(
            "/products",
            json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id, field: value},
        )
        assert response.status_code == 201
        assert response.json()[field] == value

    @pytest.mark.parametrize("field", ["name", "standard"])
    def test_length_256_rejected(self, client, manufacturer, field):
        response = client.post(
            "/products",
            json={
                **VALID_PRODUCT,
                "manufacturer_id": manufacturer.id,
                field: "Я" * 256,
            },
        )
        assert response.status_code == 422

    def test_designation_255_accepted(self, client, manufacturer):
        value = "Я" * 255
        response = client.post(
            "/products",
            json={
                **VALID_PRODUCT,
                "manufacturer_id": manufacturer.id,
                "designation": value,
            },
        )
        assert response.status_code == 201
        assert response.json()["designation"] == value

    def test_designation_256_rejected(self, client, manufacturer):
        response = client.post(
            "/products",
            json={
                **VALID_PRODUCT,
                "manufacturer_id": manufacturer.id,
                "designation": "Я" * 256,
            },
        )
        assert response.status_code == 422

    def test_product_type_100_accepted(self, client, manufacturer):
        value = "Я" * 100
        response = client.post(
            "/products",
            json={
                **VALID_PRODUCT,
                "manufacturer_id": manufacturer.id,
                "product_type": value,
            },
        )
        assert response.status_code == 201
        assert response.json()["product_type"] == value

    def test_product_type_101_rejected(self, client, manufacturer):
        response = client.post(
            "/products",
            json={
                **VALID_PRODUCT,
                "manufacturer_id": manufacturer.id,
                "product_type": "Я" * 101,
            },
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("field", ["designation", "product_type"])
    def test_blank_optional_text_rejected(self, client, manufacturer, field):
        response = client.post(
            "/products",
            json={
                **VALID_PRODUCT,
                "manufacturer_id": manufacturer.id,
                field: "   ",
            },
        )
        assert response.status_code == 422


class TestGetProduct:
    def test_returns_200_for_existing(self, client, make_product):
        created = make_product()
        assert client.get(f"/products/{created['id']}").status_code == 200

    def test_returns_stored_representation(self, client, make_product):
        created = make_product()
        body = client.get(f"/products/{created['id']}").json()
        assert body == created

    def test_content_type_is_json(self, client, make_product):
        created = make_product()
        response = client.get(f"/products/{created['id']}")
        assert response.headers["content-type"].startswith("application/json")

    def test_returns_all_fields(self, client, make_product):
        created = make_product(designation="АРТ-1", product_type="труба")
        body = client.get(f"/products/{created['id']}").json()
        assert body["designation"] == "АРТ-1"
        assert body["product_type"] == "труба"
        assert body["manufacturer_id"] == created["manufacturer_id"]

    def test_returns_null_for_unset_optional_fields(self, client, make_product):
        created = make_product()
        body = client.get(f"/products/{created['id']}").json()
        assert body["designation"] is None
        assert body["product_type"] is None

    def test_returns_404_for_missing(self, client):
        assert client.get("/products/999999").status_code == 404

    def test_404_detail_mentions_id(self, client):
        body = client.get("/products/4242").json()
        assert "4242" in body["detail"]
        assert "Product" in body["detail"]

    def test_non_integer_id_returns_422(self, client):
        assert client.get("/products/abc").status_code == 422

    def test_negative_id_returns_404(self, client):
        assert client.get("/products/-1").status_code == 404


class TestProductsIsolation:
    def test_get_does_not_create_rows(self, client, db):
        client.get("/products/1")
        assert db.scalar(select(func.count()).select_from(Product)) == 0

    def test_manufacturer_still_untouched(self, client, db, manufacturer):
        make_body = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id}
        ).json()
        client.get(f"/products/{make_body['id']}")
        assert db.get(Manufacturer, manufacturer.id).name == "ООО ИММИД"


class TestManufacturerApiRegressions:
    def test_health_still_available(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_manufacturer_create_still_works(self, client):
        response = client.post("/manufacturers", json={"name": "Регрессия"})
        assert response.status_code == 201
        assert response.headers["Location"].endswith("/manufacturers/1")

    def test_manufacturer_get_still_works(self, client):
        created = client.post("/manufacturers", json={"name": "Регрессия"}).json()
        assert client.get(f"/manufacturers/{created['id']}").json() == created

    def test_manufacturer_list_still_works(self, client):
        client.post("/manufacturers", json={"name": "Регрессия"})
        assert client.get("/manufacturers").status_code == 200

    def test_manufacturer_patch_still_works(self, client):
        created = client.post("/manufacturers", json={"name": "Регрессия"}).json()
        response = client.patch(
            f"/manufacturers/{created['id']}", json={"name": "Изменено"}
        )
        assert response.status_code == 200

    def test_manufacturer_404_still_works(self, client):
        assert client.get("/manufacturers/999999").status_code == 404

    def test_product_routes_do_not_shadow_manufacturer_routes(self, client):
        assert client.get("/products/1").status_code == 404
        assert client.get("/manufacturers/1").status_code == 404


class TestUnimplementedRoutes:
    def test_delete_not_implemented_yet(self, client, make_product):
        created = make_product()
        assert client.delete(f"/products/{created['id']}").status_code == 405


class TestPatchProduct:
    def test_returns_200(self, client, make_product):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={"name": "Новое Имя"}
        )
        assert response.status_code == 200

    def test_returns_updated_body(self, client, make_product):
        created = make_product(name="Труба ПЭ100 SDR11")
        body = client.patch(
            f"/products/{created['id']}", json={"name": "Труба ПЭ100 SDR17"}
        ).json()
        assert body["name"] == "Труба ПЭ100 SDR17"
        assert body["id"] == created["id"]

    def test_content_type_is_json(self, client, make_product):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={"name": "X"}
        )
        assert response.headers["content-type"].startswith("application/json")

    def test_change_persisted(self, client, db, make_product):
        created = make_product(name="Труба ПЭ100 SDR11")
        client.patch(f"/products/{created['id']}", json={"name": "Новое"})
        db.expire_all()
        assert db.get(Product, created["id"]).name == "Новое"

    def test_change_visible_through_get(self, client, make_product):
        created = make_product()
        client.patch(f"/products/{created['id']}", json={"name": "Новое"})
        assert client.get(f"/products/{created['id']}").json()["name"] == "Новое"

    def test_change_visible_in_list(self, client, make_product):
        created = make_product()
        client.patch(f"/products/{created['id']}", json={"name": "Новое"})
        assert client.get("/products").json()[0]["name"] == "Новое"

    def test_updates_name(self, client, make_product):
        created = make_product(name="Труба ПЭ100 SDR11")
        body = client.patch(
            f"/products/{created['id']}", json={"name": "Труба ПЭ100 SDR17"}
        ).json()
        assert body["name"] == "Труба ПЭ100 SDR17"

    def test_updates_standard(self, client, make_product):
        created = make_product(standard="ГОСТ 58121.2-2018")
        body = client.patch(
            f"/products/{created['id']}",
            json={"standard": "ТУ 22.21.29-002-0106727451-2020"},
        ).json()
        assert body["standard"] == "ТУ 22.21.29-002-0106727451-2020"

    def test_updates_designation(self, client, make_product):
        created = make_product()
        body = client.patch(
            f"/products/{created['id']}", json={"designation": "АРТ-1"}
        ).json()
        assert body["designation"] == "АРТ-1"

    def test_updates_product_type(self, client, make_product):
        created = make_product()
        body = client.patch(
            f"/products/{created['id']}", json={"product_type": "труба"}
        ).json()
        assert body["product_type"] == "труба"

    def test_clears_designation_with_null(self, client, db, make_product):
        created = make_product(designation="АРТ-1")
        body = client.patch(
            f"/products/{created['id']}", json={"designation": None}
        ).json()
        assert body["designation"] is None
        db.expire_all()
        assert db.get(Product, created["id"]).designation is None

    def test_clears_product_type_with_null(self, client, db, make_product):
        created = make_product(product_type="труба")
        body = client.patch(
            f"/products/{created['id']}", json={"product_type": None}
        ).json()
        assert body["product_type"] is None

    def test_updates_several_fields(self, client, make_product):
        created = make_product()
        body = client.patch(
            f"/products/{created['id']}",
            json={
                "name": "Новое",
                "standard": "ТУ",
                "product_type": "труба",
            },
        ).json()
        assert body["name"] == "Новое"
        assert body["standard"] == "ТУ"
        assert body["product_type"] == "труба"

    def test_absent_fields_untouched(self, client, make_product):
        created = make_product(
            name="Труба", standard="ГОСТ", designation="АРТ-1"
        )
        body = client.patch(
            f"/products/{created['id']}", json={"name": "Новое"}
        ).json()
        assert body["name"] == "Новое"
        assert body["standard"] == "ГОСТ"
        assert body["designation"] == "АРТ-1"

    def test_whitespace_stripped(self, client, make_product):
        created = make_product()
        body = client.patch(
            f"/products/{created['id']}", json={"name": "   Новое Имя   "}
        ).json()
        assert body["name"] == "Новое Имя"

    def test_patch_appends_not_replaces(self, client, make_product):
        created = make_product()
        client.patch(f"/products/{created['id']}", json={"name": "Первый"})
        body = client.patch(
            f"/products/{created['id']}", json={"name": "Второй"}
        ).json()
        assert body["name"] == "Второй"

    def test_no_new_rows_created(self, client, db, make_product):
        created = make_product()
        client.patch(f"/products/{created['id']}", json={"name": "Новое"})
        assert db.scalar(select(func.count()).select_from(Product)) == 1

    def test_other_products_untouched(self, client, db, make_product):
        first = make_product(name="Первый")
        second = make_product(name="Второй")
        client.patch(f"/products/{first['id']}", json={"name": "Изменён"})
        db.expire_all()
        assert db.get(Product, second["id"]).name == "Второй"

    def test_manufacturer_relationship_survives(self, client, manufacturer, make_product):
        created = make_product()
        body = client.patch(
            f"/products/{created['id']}", json={"name": "Новое"}
        ).json()
        assert body["manufacturer_id"] == manufacturer.id


class TestPatchProductManufacturer:
    @pytest.fixture
    def second_manufacturer(self, db):
        return ManufacturerService.create(
            db, ManufacturerCreate(name="АИР-ГАЗ")
        )

    def test_changes_to_existing_manufacturer(
        self, client, manufacturer, second_manufacturer, make_product
    ):
        created = make_product()
        body = client.patch(
            f"/products/{created['id']}",
            json={"manufacturer_id": second_manufacturer.id},
        ).json()
        assert body["manufacturer_id"] == second_manufacturer.id

    def test_manufacturer_change_persisted(
        self, client, db, second_manufacturer, make_product
    ):
        created = make_product()
        client.patch(
            f"/products/{created['id']}",
            json={"manufacturer_id": second_manufacturer.id},
        )
        db.expire_all()
        assert db.get(Product, created["id"]).manufacturer_id == second_manufacturer.id

    def test_same_manufacturer_allowed(self, client, manufacturer, make_product):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}",
            json={"manufacturer_id": manufacturer.id},
        )
        assert response.status_code == 200

    def test_unknown_manufacturer_returns_404(self, client, make_product):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={"manufacturer_id": 999_999}
        )
        assert response.status_code == 404

    def test_404_detail_mentions_manufacturer(self, client, make_product):
        created = make_product()
        body = client.patch(
            f"/products/{created['id']}", json={"manufacturer_id": 4242}
        ).json()
        assert "4242" in body["detail"]
        assert "Manufacturer" in body["detail"]

    def test_no_partial_save_on_unknown_manufacturer(self, client, db, make_product):
        created = make_product(name="Труба", standard="ГОСТ")
        client.patch(
            f"/products/{created['id']}",
            json={"name": "Новое Имя", "manufacturer_id": 999_999},
        )
        db.expire_all()
        stored = db.get(Product, created["id"])
        assert stored.name == "Труба"
        assert stored.standard == "ГОСТ"

    def test_manufacturer_not_changed_after_rejection(self, client, db, manufacturer, make_product):
        created = make_product()
        client.patch(
            f"/products/{created['id']}", json={"manufacturer_id": 999_999}
        )
        db.expire_all()
        assert db.get(Product, created["id"]).manufacturer_id == manufacturer.id

    def test_designation_not_cleared_after_rejection(self, client, db, make_product):
        created = make_product(designation="АРТ-1")
        client.patch(
            f"/products/{created['id']}",
            json={"designation": None, "manufacturer_id": 999_999},
        )
        db.expire_all()
        assert db.get(Product, created["id"]).designation == "АРТ-1"

    def test_patch_to_duplicate_name_allowed(
        self, client, make_product
    ):
        first = make_product(name="Труба ПЭ100 SDR11")
        second = make_product(name="Другой")
        response = client.patch(
            f"/products/{second['id']}", json={"name": "Труба ПЭ100 SDR11"}
        )
        assert response.status_code == 200
        assert response.json()["id"] == second["id"] != first["id"]


class TestPatchProductNotFound:
    def test_returns_404(self, client):
        assert client.patch(
            "/products/999999", json={"name": "Новое"}
        ).status_code == 404

    def test_404_detail_mentions_product(self, client):
        body = client.patch("/products/4242", json={"name": "Новое"}).json()
        assert "4242" in body["detail"]
        assert "Product" in body["detail"]

    def test_empty_patch_on_missing_returns_404(self, client):
        assert client.patch("/products/999999", json={}).status_code == 404

    def test_invalid_payload_on_missing_returns_422(self, client):
        response = client.patch("/products/999999", json={"name": "  "})
        assert response.status_code == 422

    def test_non_integer_id_returns_422(self, client):
        response = client.patch("/products/abc", json={"name": "Новое"})
        assert response.status_code == 422

    def test_missing_product_not_created(self, client, db):
        client.patch("/products/999999", json={"name": "Новое"})
        assert db.scalar(select(func.count()).select_from(Product)) == 0


class TestPatchProductEmptyPayload:
    def test_empty_object_returns_200(self, client, make_product):
        created = make_product()
        assert client.patch(f"/products/{created['id']}", json={}).status_code == 200

    def test_empty_object_leaves_name_unchanged(self, client, db, make_product):
        created = make_product(name="Труба ПЭ100 SDR11")
        body = client.patch(f"/products/{created['id']}", json={}).json()
        assert body["name"] == "Труба ПЭ100 SDR11"
        db.expire_all()
        assert db.get(Product, created["id"]).name == "Труба ПЭ100 SDR11"

    def test_empty_object_returns_full_representation(self, client, make_product):
        created = make_product(designation="АРТ-1", product_type="труба")
        assert client.patch(f"/products/{created['id']}", json={}).json() == created

    def test_unknown_field_alone_is_ignored(self, client, make_product):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={"sdr": 11}
        )
        assert response.status_code == 200
        assert "sdr" not in response.json()


class TestPatchProductValidation:
    @pytest.mark.parametrize("field", ["name", "standard"])
    @pytest.mark.parametrize("value", ["", "   ", "\t\n "])
    def test_blank_required_text_rejected(self, client, make_product, field, value):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={field: value}
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("field", ["designation", "product_type"])
    @pytest.mark.parametrize("value", ["", "   "])
    def test_blank_optional_text_rejected(self, client, make_product, field, value):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={field: value}
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("field", ["name", "standard", "manufacturer_id"])
    def test_explicit_null_rejected_for_required(self, client, make_product, field):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={field: None}
        )
        assert response.status_code == 422

    def test_error_detail_locates_body_field(self, client, make_product):
        created = make_product()
        body = client.patch(
            f"/products/{created['id']}", json={"name": ""}
        ).json()
        assert ["body", "name"] in [error["loc"] for error in body["detail"]]

    @pytest.mark.parametrize("field", ["name", "standard"])
    def test_length_255_accepted(self, client, make_product, field):
        created = make_product()
        value = "Я" * 255
        response = client.patch(
            f"/products/{created['id']}", json={field: value}
        )
        assert response.status_code == 200
        assert response.json()[field] == value

    @pytest.mark.parametrize("field", ["name", "standard"])
    def test_length_256_rejected(self, client, make_product, field):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={field: "Я" * 256}
        )
        assert response.status_code == 422

    def test_product_type_101_rejected(self, client, make_product):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={"product_type": "Я" * 101}
        )
        assert response.status_code == 422

    def test_designation_255_accepted(self, client, make_product):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={"designation": "Я" * 255}
        )
        assert response.status_code == 200

    @pytest.mark.parametrize("value", [True, False])
    def test_boolean_manufacturer_id_rejected(self, client, make_product, value):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={"manufacturer_id": value}
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("value", [1.5, 2.9])
    def test_fractional_manufacturer_id_rejected(self, client, make_product, value):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={"manufacturer_id": value}
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("value", [0, -1])
    def test_non_positive_manufacturer_id_rejected(self, client, make_product, value):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}", json={"manufacturer_id": value}
        )
        assert response.status_code == 422

    def test_invalid_payload_leaves_row_untouched(self, client, db, make_product):
        created = make_product(name="Труба")
        client.patch(f"/products/{created['id']}", json={"name": "   "})
        db.expire_all()
        assert db.get(Product, created["id"]).name == "Труба"


class TestPatchProductRequestBody:
    def test_missing_body_returns_422(self, client, make_product):
        created = make_product()
        assert client.patch(f"/products/{created['id']}").status_code == 422

    def test_malformed_json_returns_422(self, client, make_product):
        created = make_product()
        response = client.patch(
            f"/products/{created['id']}",
            content=b'{"name": ',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_literal_null_body_returns_422(self, client, make_product):
        created = make_product()
        assert client.patch(
            f"/products/{created['id']}", json=None
        ).status_code == 422

    def test_array_body_returns_422(self, client, make_product):
        created = make_product()
        assert client.patch(
            f"/products/{created['id']}", json=[]
        ).status_code == 422

    def test_rejected_bodies_leave_row_untouched(self, client, db, make_product):
        created = make_product(name="Труба")
        client.patch(f"/products/{created['id']}")
        client.patch(
            f"/products/{created['id']}",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        db.expire_all()
        assert db.get(Product, created["id"]).name == "Труба"


class TestPatchRegressionChecks:
    def test_post_still_works(self, client, manufacturer):
        response = client.post(
            "/products",
            json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id},
        )
        assert response.status_code == 201

    def test_post_unknown_manufacturer_still_404(self, client):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": 999_999}
        )
        assert response.status_code == 404

    def test_get_by_id_still_works(self, client, make_product):
        created = make_product()
        assert client.get(f"/products/{created['id']}").json() == created

    def test_get_by_id_missing_still_404(self, client):
        assert client.get("/products/999999").status_code == 404

    def test_list_still_works(self, client, make_product):
        make_product()
        response = client.get("/products")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_patch_does_not_create_extra_rows(self, client, db, make_product):
        created = make_product()
        client.patch(f"/products/{created['id']}", json={"name": "Новое"})
        assert db.scalar(select(func.count()).select_from(Product)) == 1

    def test_list_reflects_patch(self, client, make_product):
        created = make_product(name="Старое")
        client.patch(f"/products/{created['id']}", json={"name": "Новое"})
        assert [i["name"] for i in client.get("/products").json()] == ["Новое"]

    def test_manufacturer_api_still_works(self, client):
        created = client.post("/manufacturers", json={"name": "Регрессия"}).json()
        assert client.get(f"/manufacturers/{created['id']}").json() == created
        assert client.get("/manufacturers").status_code == 200


class TestListProductsEmpty:
    def test_returns_200(self, client):
        assert client.get("/products").status_code == 200

    def test_empty_database_returns_empty_array(self, client):
        assert client.get("/products").json() == []

    def test_empty_with_explicit_params(self, client):
        response = client.get("/products", params={"limit": 10, "offset": 5})
        assert response.status_code == 200
        assert response.json() == []


class TestListProducts:
    def test_returns_all_when_within_default_limit(self, client, make_product):
        for index in range(3):
            make_product(name=f"П{index}")
        assert len(client.get("/products").json()) == 3

    def test_content_type_is_json(self, client, make_product):
        make_product()
        response = client.get("/products")
        assert response.headers["content-type"].startswith("application/json")

    def test_returns_json_array(self, client, make_product):
        make_product()
        assert isinstance(client.get("/products").json(), list)

    def test_items_have_all_read_fields(self, client, make_product):
        make_product(designation="АРТ-1", product_type="труба")
        body = client.get("/products").json()
        for item in body:
            assert set(item) == {
                "id",
                "name",
                "standard",
                "manufacturer_id",
                "designation",
                "product_type",
            }

    def test_item_field_values_correct(self, client, db, manufacturer, make_product):
        make_product(name="Труба ПЭ100 SDR11", designation="АРТ-9", product_type="труба")
        item = client.get("/products").json()[0]
        assert item["name"] == "Труба ПЭ100 SDR11"
        assert item["standard"] == "ГОСТ 58121.2-2018"
        assert item["manufacturer_id"] == manufacturer.id
        assert item["designation"] == "АРТ-9"
        assert item["product_type"] == "труба"

    def test_null_optional_fields_present_as_null(self, client, make_product):
        make_product()
        item = client.get("/products").json()[0]
        assert item["designation"] is None
        assert item["product_type"] is None

    def test_no_sdr_in_response(self, client, make_product):
        make_product(name="Труба ПЭ100 SDR11")
        assert "sdr" not in client.get("/products").json()[0]

    def test_matches_created_representations(self, client, make_product):
        created = [make_product(name=f"П{i}") for i in range(3)]
        body = client.get("/products").json()
        assert [item["id"] for item in body] == [c["id"] for c in created]


class TestListOrdering:
    def test_ordered_by_ascending_id(self, client, make_product):
        for index in range(5):
            make_product(name=f"П{index}")
        ids = [item["id"] for item in client.get("/products").json()]
        assert ids == sorted(ids)

    def test_order_independent_of_name(self, client, db, manufacturer):
        # insertion order deliberately differs from alphabetical order:
        # under the C.UTF-8 collation "ЯМАЛ" would sort before "ALIAXIS"
        for name in ("ЯМАЛ", "ALIAXIS", "ИММИД"):
            response = client.post(
                "/products",
                json={
                    "name": name,
                    "standard": "ГОСТ 58121.2-2018",
                    "manufacturer_id": manufacturer.id,
                },
            )
            assert response.status_code == 201
        body = client.get("/products").json()
        assert [item["name"] for item in body] == ["ЯМАЛ", "ALIAXIS", "ИММИД"]
        assert [item["id"] for item in body] == sorted(
            item["id"] for item in body
        )

    def test_order_follows_insertion_not_name(self, client, make_product):
        for name in ("Б", "А", "В"):
            make_product(name=name)
        body = client.get("/products").json()
        assert [item["name"] for item in body] == ["Б", "А", "В"]


class TestListPagination:
    def test_limit_1(self, client, make_product):
        for index in range(3):
            make_product(name=f"П{index}")
        body = client.get("/products", params={"limit": 1}).json()
        assert len(body) == 1

    def test_limit_returns_first_n(self, client, make_product):
        for index in range(5):
            make_product(name=f"П{index}")
        body = client.get("/products", params={"limit": 2}).json()
        assert [item["name"] for item in body] == ["П0", "П1"]

    def test_offset_skips_from_start(self, client, make_product):
        for index in range(5):
            make_product(name=f"П{index}")
        body = client.get("/products", params={"offset": 2}).json()
        assert [item["name"] for item in body] == ["П2", "П3", "П4"]

    def test_offset_zero_returns_all(self, client, make_product):
        for index in range(3):
            make_product(name=f"П{index}")
        assert len(client.get("/products", params={"offset": 0}).json()) == 3

    def test_offset_beyond_end_returns_empty(self, client, make_product):
        make_product()
        assert client.get("/products", params={"offset": 100}).json() == []

    def test_limit_and_offset_paging(self, client, make_product):
        for index in range(5):
            make_product(name=f"П{index}")
        first = client.get("/products", params={"limit": 2, "offset": 0}).json()
        second = client.get("/products", params={"limit": 2, "offset": 2}).json()
        third = client.get("/products", params={"limit": 2, "offset": 4}).json()
        assert [i["name"] for i in first] == ["П0", "П1"]
        assert [i["name"] for i in second] == ["П2", "П3"]
        assert [i["name"] for i in third] == ["П4"]

    def test_pages_do_not_overlap(self, client, make_product):
        for index in range(6):
            make_product(name=f"П{index}")
        first = client.get("/products", params={"limit": 3, "offset": 0}).json()
        second = client.get("/products", params={"limit": 3, "offset": 3}).json()
        assert {i["id"] for i in first}.isdisjoint({i["id"] for i in second})
        assert len(first) + len(second) == 6

    def test_limit_larger_than_total(self, client, make_product):
        for index in range(3):
            make_product(name=f"П{index}")
        assert len(client.get("/products", params={"limit": 100}).json()) == 3


class TestListParameterBoundaries:
    def test_limit_minimum_accepted(self, client, make_product):
        make_product()
        assert client.get("/products", params={"limit": 1}).status_code == 200

    def test_limit_maximum_accepted(self, client, make_product):
        make_product()
        assert client.get("/products", params={"limit": 100}).status_code == 200

    def test_offset_minimum_accepted(self, client, make_product):
        make_product()
        assert client.get("/products", params={"offset": 0}).status_code == 200

    @pytest.mark.parametrize("value", [0, -1, -100, 101, 1000])
    def test_limit_out_of_range_returns_422(self, client, value):
        assert client.get("/products", params={"limit": value}).status_code == 422

    @pytest.mark.parametrize("value", [-1, -50])
    def test_offset_out_of_range_returns_422(self, client, value):
        assert client.get("/products", params={"offset": value}).status_code == 422

    @pytest.mark.parametrize("value", ["abc", "", "1.5"])
    def test_non_integer_limit_returns_422(self, client, value):
        assert client.get(
            "/products", params={"limit": value}
        ).status_code == 422

    @pytest.mark.parametrize("value", ["abc", "", "2.5"])
    def test_non_integer_offset_returns_422(self, client, value):
        assert client.get(
            "/products", params={"offset": value}
        ).status_code == 422

    def test_invalid_params_report_query_location(self, client):
        body = client.get("/products", params={"limit": 0}).json()
        assert ["query", "limit"] in [
            error["loc"] for error in body["detail"]
        ]

    def test_invalid_params_create_no_rows(self, client, db):
        client.get("/products", params={"limit": 500})
        assert db.scalar(select(func.count()).select_from(Product)) == 0


class TestListDefaultParameters:
    def test_default_limit_is_50(self, client, make_product):
        for index in range(55):
            make_product(name=f"П{index:03d}")
        assert len(client.get("/products").json()) == 50

    def test_default_limit_caps_result(self, client, make_product):
        for index in range(52):
            make_product(name=f"П{index:03d}")
        assert len(client.get("/products").json()) == 50

    def test_default_offset_is_zero(self, client, make_product):
        for index in range(3):
            make_product(name=f"П{index}")
        body = client.get("/products").json()
        assert [item["name"] for item in body] == ["П0", "П1", "П2"]


class TestProductsRouteRegressions:
    def test_post_still_works(self, client, manufacturer):
        response = client.post(
            "/products",
            json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id},
        )
        assert response.status_code == 201

    def test_post_location_still_correct(self, client, manufacturer):
        response = client.post(
            "/products",
            json={**VALID_PRODUCT, "manufacturer_id": manufacturer.id},
        )
        assert response.headers["Location"].endswith(
            f"/products/{response.json()['id']}"
        )

    def test_post_unknown_manufacturer_still_404(self, client):
        response = client.post(
            "/products", json={**VALID_PRODUCT, "manufacturer_id": 999_999}
        )
        assert response.status_code == 404

    def test_get_by_id_still_works(self, client, make_product):
        created = make_product()
        assert client.get(f"/products/{created['id']}").json() == created

    def test_get_by_id_missing_still_404(self, client):
        assert client.get("/products/999999").status_code == 404

    def test_list_does_not_create_rows(self, client, db, make_product):
        make_product()
        before = db.scalar(select(func.count()).select_from(Product))
        client.get("/products")
        assert db.scalar(select(func.count()).select_from(Product)) == before

    def test_list_route_does_not_shadow_by_id_route(self, client, make_product):
        created = make_product()
        assert client.get("/products").status_code == 200
        assert client.get(f"/products/{created['id']}").status_code == 200
        assert isinstance(client.get("/products").json(), list)