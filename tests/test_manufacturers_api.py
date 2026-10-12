import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.manufacturers.schemas import ManufacturerCreate
from app.database.connection import get_db
from app.main import app
from app.models.manufacturer import Manufacturer
from app.services.manufacturer_service import ManufacturerService


@pytest.fixture
def client(db: Session):
    """HTTP client whose sessions point at the isolated test schema.

    Without this override `get_db` would hand out sessions bound to the
    working database, and these tests would write into real data.
    """
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_manufacturer(db):
    def _make(name: str) -> Manufacturer:
        return ManufacturerService.create(db, ManufacturerCreate(name=name))

    return _make


class TestCreateManufacturer:
    def test_returns_201(self, client):
        response = client.post("/manufacturers", json={"name": "ООО ИММИД"})
        assert response.status_code == 201

    def test_returns_created_body(self, client):
        response = client.post("/manufacturers", json={"name": "ООО ИММИД"})
        body = response.json()
        assert body["name"] == "ООО ИММИД"
        assert isinstance(body["id"], int)

    def test_content_type_is_json(self, client):
        response = client.post("/manufacturers", json={"name": "ООО ИММИД"})
        assert response.headers["content-type"].startswith("application/json")

    def test_body_has_only_id_and_name(self, client):
        body = client.post("/manufacturers", json={"name": "ООО ИММИД"}).json()
        assert set(body) == {"id", "name"}

    def test_row_is_persisted(self, client, db):
        body = client.post("/manufacturers", json={"name": "ООО ИММИД"}).json()
        stored = db.get(Manufacturer, body["id"])
        assert stored is not None
        assert stored.name == "ООО ИММИД"

    def test_location_header_present(self, client):
        response = client.post("/manufacturers", json={"name": "ООО ИММИД"})
        assert "Location" in response.headers

    def test_location_header_points_to_created_resource(self, client):
        response = client.post("/manufacturers", json={"name": "ООО ИММИД"})
        body = response.json()
        assert response.headers["Location"].endswith(f"/manufacturers/{body['id']}")

    def test_location_header_is_followable(self, client):
        response = client.post("/manufacturers", json={"name": "ООО ИММИД"})
        location = response.headers["Location"]
        follow_up = client.get(location)
        assert follow_up.status_code == 200
        assert follow_up.json() == response.json()

    def test_name_is_normalized(self, client, db):
        body = client.post("/manufacturers", json={"name": "  ООО ИММИД  "}).json()
        assert body["name"] == "ООО ИММИД"
        assert db.get(Manufacturer, body["id"]).name == "ООО ИММИД"

    def test_duplicate_names_allowed(self, client):
        first = client.post("/manufacturers", json={"name": "ALIAXIS"})
        second = client.post("/manufacturers", json={"name": "ALIAXIS"})
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] != second.json()["id"]

    def test_ids_are_unique(self, client):
        first = client.post("/manufacturers", json={"name": "Первый"}).json()
        second = client.post("/manufacturers", json={"name": "Второй"}).json()
        assert first["id"] != second["id"]


class TestCreateValidation:
    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"name": ""},
            {"name": "   "},
            {"name": None},
            {"name": "Я" * 256},
            {"name": 42},
        ],
    )
    def test_invalid_payload_returns_422(self, client, payload):
        assert client.post("/manufacturers", json=payload).status_code == 422

    def test_nothing_persisted_on_invalid_payload(self, client, db):
        client.post("/manufacturers", json={"name": "   "})
        total = db.scalar(select(func.count()).select_from(Manufacturer))
        assert total == 0

    def test_error_detail_locates_body_name(self, client):
        body = client.post("/manufacturers", json={"name": ""}).json()
        locations = [error["loc"] for error in body["detail"]]
        assert ["body", "name"] in locations

    def test_no_location_header_on_rejected_request(self, client):
        response = client.post("/manufacturers", json={"name": ""})
        assert "Location" not in response.headers


class TestGetManufacturer:
    def test_returns_200_for_existing(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.get(f"/manufacturers/{created.id}")
        assert response.status_code == 200

    def test_returns_stored_representation(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        body = client.get(f"/manufacturers/{created.id}").json()
        assert body == {"id": created.id, "name": "ООО ИММИД"}

    def test_content_type_is_json(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.get(f"/manufacturers/{created.id}")
        assert response.headers["content-type"].startswith("application/json")

    def test_round_trip_after_create(self, client):
        created = client.post("/manufacturers", json={"name": "ООО ИММИД"}).json()
        fetched = client.get(f"/manufacturers/{created['id']}").json()
        assert fetched == created

    def test_returns_404_for_missing(self, client):
        assert client.get("/manufacturers/999999").status_code == 404

    def test_404_detail_mentions_id(self, client):
        body = client.get("/manufacturers/4242").json()
        assert "4242" in body["detail"]

    def test_non_integer_id_returns_422(self, client):
        assert client.get("/manufacturers/abc").status_code == 422

    def test_negative_id_returns_404(self, client):
        assert client.get("/manufacturers/-1").status_code == 404


class TestWorkingDataIsolation:
    def test_empty_database_returns_404(self, client):
        assert client.get("/manufacturers/1").status_code == 404

    def test_health_still_available(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.fixture
def make_many(db, request):
    """Create N manufacturers and return their created ids."""

    def _make(count: int, prefix: str = "П") -> list[int]:
        ids = []
        for index in range(count):
            manufacturer = ManufacturerService.create(
                db, ManufacturerCreate(name=f"{prefix}{index}")
            )
            ids.append(manufacturer.id)
        return ids

    return _make


class TestListManufacturersEmpty:
    def test_empty_database_returns_200(self, client):
        assert client.get("/manufacturers").status_code == 200

    def test_empty_database_returns_empty_array(self, client):
        assert client.get("/manufacturers").json() == []

    def test_empty_with_explicit_params(self, client):
        response = client.get("/manufacturers", params={"limit": 10, "offset": 5})
        assert response.status_code == 200
        assert response.json() == []


class TestListManufacturers:
    def test_returns_all_when_within_default_limit(self, client, make_many):
        make_many(3)
        body = client.get("/manufacturers").json()
        assert len(body) == 3

    def test_content_type_is_json(self, client, make_many):
        make_many(1)
        response = client.get("/manufacturers")
        assert response.headers["content-type"].startswith("application/json")

    def test_items_have_only_id_and_name(self, client, make_many):
        make_many(2)
        body = client.get("/manufacturers").json()
        for item in body:
            assert set(item) == {"id", "name"}

    def test_matches_created_representations(self, client, make_many):
        ids = make_many(2)
        body = client.get("/manufacturers").json()
        assert [item["id"] for item in body] == ids

    def test_default_limit_is_50(self, client, make_many):
        make_many(55)
        assert len(client.get("/manufacturers").json()) == 50

    def test_default_limit_caps_result(self, client, make_many):
        make_many(52)
        assert len(client.get("/manufacturers").json()) == 50

    def test_default_offset_is_zero(self, client, make_many):
        ids = make_many(3)
        body = client.get("/manufacturers").json()
        assert [item["id"] for item in body] == ids


class TestListOrdering:
    def test_ordered_by_ascending_id(self, client, make_many):
        make_many(5)
        body = client.get("/manufacturers").json()
        ids = [item["id"] for item in body]
        assert ids == sorted(ids)

    def test_order_does_not_follow_name_alphabetically(self, client, db):
        for name in ["ЯМАЛ", "ALIAXIS", "ИММИД"]:
            ManufacturerService.create(db, ManufacturerCreate(name=name))
        body = client.get("/manufacturers").json()
        ids = [item["id"] for item in body]
        assert ids == sorted(ids)
        assert body[0]["name"] == "ЯМАЛ"


class TestListPagination:
    def test_limit_1(self, client, make_many):
        ids = make_many(3)
        body = client.get("/manufacturers", params={"limit": 1}).json()
        assert len(body) == 1
        assert body[0]["id"] == ids[0]

    def test_limit_returns_first_n(self, client, make_many):
        ids = make_many(5)
        body = client.get("/manufacturers", params={"limit": 2}).json()
        assert [item["id"] for item in body] == ids[:2]

    def test_offset_skips_from_start(self, client, make_many):
        ids = make_many(5)
        body = client.get("/manufacturers", params={"offset": 2}).json()
        assert [item["id"] for item in body] == ids[2:]

    def test_offset_zero_returns_all(self, client, make_many):
        ids = make_many(3)
        body = client.get("/manufacturers", params={"offset": 0}).json()
        assert [item["id"] for item in body] == ids

    def test_offset_beyond_end_returns_empty(self, client, make_many):
        make_many(3)
        assert client.get("/manufacturers", params={"offset": 100}).json() == []

    def test_limit_and_offset_paging(self, client, make_many):
        ids = make_many(5)
        first = client.get("/manufacturers", params={"limit": 2, "offset": 0}).json()
        second = client.get("/manufacturers", params={"limit": 2, "offset": 2}).json()
        third = client.get("/manufacturers", params={"limit": 2, "offset": 4}).json()
        assert [i["id"] for i in first] == ids[0:2]
        assert [i["id"] for i in second] == ids[2:4]
        assert [i["id"] for i in third] == ids[4:5]

    def test_pages_do_not_overlap(self, client, make_many):
        ids = make_many(6)
        first = client.get("/manufacturers", params={"limit": 3, "offset": 0}).json()
        second = client.get("/manufacturers", params={"limit": 3, "offset": 3}).json()
        assert set(i["id"] for i in first).isdisjoint(
            {i["id"] for i in second}
        )
        assert len(first) + len(second) == len(ids)

    def test_limit_larger_than_total_returns_all(self, client, make_many):
        ids = make_many(3)
        body = client.get("/manufacturers", params={"limit": 100}).json()
        assert [item["id"] for item in body] == ids


class TestListParameterBoundaries:
    def test_limit_minimum_accepted(self, client, make_many):
        make_many(3)
        assert client.get("/manufacturers", params={"limit": 1}).status_code == 200

    def test_limit_maximum_accepted(self, client, make_many):
        make_many(3)
        assert client.get("/manufacturers", params={"limit": 100}).status_code == 200

    def test_offset_minimum_accepted(self, client, make_many):
        make_many(3)
        assert client.get("/manufacturers", params={"offset": 0}).status_code == 200

    @pytest.mark.parametrize("value", [0, -1, -100, 101, 1000])
    def test_limit_out_of_range_returns_422(self, client, value):
        assert client.get("/manufacturers", params={"limit": value}).status_code == 422

    @pytest.mark.parametrize("value", [-1, -50])
    def test_offset_out_of_range_returns_422(self, client, value):
        assert client.get("/manufacturers", params={"offset": value}).status_code == 422

    @pytest.mark.parametrize("value", ["abc", "", "1.5", "null"])
    def test_non_integer_limit_returns_422(self, client, value):
        assert client.get(
            "/manufacturers", params={"limit": value}
        ).status_code == 422

    @pytest.mark.parametrize("value", ["abc", "", "2.5"])
    def test_non_integer_offset_returns_422(self, client, value):
        assert client.get(
            "/manufacturers", params={"offset": value}
        ).status_code == 422

    def test_invalid_params_report_query_location(self, client):
        body = client.get("/manufacturers", params={"limit": 0}).json()
        locations = [error["loc"] for error in body["detail"]]
        assert ["query", "limit"] in locations

    def test_invalid_params_execute_no_query(self, client, db):
        from sqlalchemy import func, select

        client.get("/manufacturers", params={"limit": 500})
        total = db.scalar(select(func.count()).select_from(Manufacturer))
        assert total == 0


class TestPatchManufacturer:
    def test_returns_200(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(
            f"/manufacturers/{created.id}", json={"name": "ООО ИММИД (Москва)"}
        )
        assert response.status_code == 200

    def test_returns_updated_body(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        body = client.patch(
            f"/manufacturers/{created.id}", json={"name": "Новое Имя"}
        ).json()
        assert body == {"id": created.id, "name": "Новое Имя"}

    def test_content_type_is_json(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(
            f"/manufacturers/{created.id}", json={"name": "Новое"}
        )
        assert response.headers["content-type"].startswith("application/json")

    def test_change_is_persisted(self, client, db, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        client.patch(f"/manufacturers/{created.id}", json={"name": "Новое Имя"})
        db.expire_all()
        assert db.get(Manufacturer, created.id).name == "Новое Имя"

    def test_change_visible_through_get(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        client.patch(f"/manufacturers/{created.id}", json={"name": "Новое Имя"})
        fetched = client.get(f"/manufacturers/{created.id}").json()
        assert fetched["name"] == "Новое Имя"

    def test_change_visible_in_list(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        client.patch(f"/manufacturers/{created.id}", json={"name": "Новое Имя"})
        body = client.get("/manufacturers").json()
        assert body[0]["name"] == "Новое Имя"

    def test_surrounding_whitespace_stripped(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        body = client.patch(
            f"/manufacturers/{created.id}", json={"name": "   Новое Имя   "}
        ).json()
        assert body["name"] == "Новое Имя"

    def test_inner_whitespace_preserved(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        body = client.patch(
            f"/manufacturers/{created.id}", json={"name": "  Новое   Имя  "}
        ).json()
        assert body["name"] == "Новое   Имя"

    def test_id_unchanged(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        body = client.patch(
            f"/manufacturers/{created.id}", json={"name": "Новое"}
        ).json()
        assert body["id"] == created.id

    def test_patch_to_duplicate_name_allowed(self, client, make_manufacturer):
        first = make_manufacturer("ALIAXIS")
        second = make_manufacturer("Другой")
        response = client.patch(
            f"/manufacturers/{second.id}", json={"name": "ALIAXIS"}
        )
        assert response.status_code == 200
        assert response.json()["id"] == second.id != first.id

    def test_other_rows_untouched(self, client, db, make_manufacturer):
        first = make_manufacturer("Первый")
        second = make_manufacturer("Второй")
        client.patch(f"/manufacturers/{first.id}", json={"name": "Изменён"})
        assert db.get(Manufacturer, second.id).name == "Второй"

    def test_no_new_rows_created(self, client, db, make_manufacturer):
        make_manufacturer("ООО ИММИД")
        from sqlalchemy import func, select

        client.patch("/manufacturers/1", json={"name": "Новое"})
        total = db.scalar(select(func.count()).select_from(Manufacturer))
        assert total == 1

    def test_patch_appends_not_replaces(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        client.patch(f"/manufacturers/{created.id}", json={"name": "Первый"})
        body = client.patch(
            f"/manufacturers/{created.id}", json={"name": "Второй"}
        ).json()
        assert body["name"] == "Второй"


class TestPatchEmptyPayload:
    def test_empty_object_returns_200(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        assert client.patch(f"/manufacturers/{created.id}", json={}).status_code == 200

    def test_empty_object_leaves_name_unchanged(self, client, db, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        body = client.patch(f"/manufacturers/{created.id}", json={}).json()
        assert body["name"] == "ООО ИММИД"
        db.expire_all()
        assert db.get(Manufacturer, created.id).name == "ООО ИММИД"

    def test_empty_object_returns_full_representation(
        self, client, make_manufacturer
    ):
        created = make_manufacturer("ООО ИММИД")
        body = client.patch(f"/manufacturers/{created.id}", json={}).json()
        assert body == {"id": created.id, "name": "ООО ИММИД"}

    def test_unknown_field_alone_is_ignored(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(
            f"/manufacturers/{created.id}", json={"unknown_field": "x"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "ООО ИММИД"


class TestPatchNotFound:
    def test_returns_404(self, client):
        response = client.patch("/manufacturers/999999", json={"name": "Новое"})
        assert response.status_code == 404

    def test_404_detail_mentions_id(self, client):
        body = client.patch("/manufacturers/4242", json={"name": "Новое"}).json()
        assert "4242" in body["detail"]

    def test_missing_manufacturer_not_created(self, client, db):
        from sqlalchemy import func, select

        client.patch("/manufacturers/999999", json={"name": "Новое"})
        total = db.scalar(select(func.count()).select_from(Manufacturer))
        assert total == 0

    def test_empty_payload_on_missing_still_404(self, client):
        assert client.patch("/manufacturers/999999", json={}).status_code == 404

    def test_invalid_payload_on_missing_returns_422(self, client):
        response = client.patch("/manufacturers/999999", json={"name": "  "})
        assert response.status_code == 422

    def test_non_integer_id_returns_422(self, client):
        response = client.patch("/manufacturers/abc", json={"name": "Новое"})
        assert response.status_code == 422


class TestPatchValidation:
    def test_empty_string_returns_422(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(f"/manufacturers/{created.id}", json={"name": ""})
        assert response.status_code == 422

    def test_whitespace_only_returns_422(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(f"/manufacturers/{created.id}", json={"name": "   "})
        assert response.status_code == 422

    def test_tabs_and_newlines_return_422(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(
            f"/manufacturers/{created.id}", json={"name": "\t\n "}
        )
        assert response.status_code == 422

    def test_explicit_null_returns_422(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(f"/manufacturers/{created.id}", json={"name": None})
        assert response.status_code == 422

    def test_length_255_accepted(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        name = "Я" * 255
        response = client.patch(f"/manufacturers/{created.id}", json={"name": name})
        assert response.status_code == 200
        assert response.json()["name"] == name

    def test_length_256_returns_422(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(
            f"/manufacturers/{created.id}", json={"name": "Я" * 256}
        )
        assert response.status_code == 422

    def test_invalid_payload_leaves_row_untouched(
        self, client, db, make_manufacturer
    ):
        created = make_manufacturer("ООО ИММИД")
        client.patch(f"/manufacturers/{created.id}", json={"name": "   "})
        db.expire_all()
        assert db.get(Manufacturer, created.id).name == "ООО ИММИД"

    def test_error_detail_locates_body_name(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        body = client.patch(f"/manufacturers/{created.id}", json={"name": ""}).json()
        assert ["body", "name"] in [error["loc"] for error in body["detail"]]

    def test_non_string_returns_422(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(f"/manufacturers/{created.id}", json={"name": 42})
        assert response.status_code == 422


class TestPatchRequestBodyHandling:
    def test_missing_body_returns_422(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(f"/manufacturers/{created.id}")
        assert response.status_code == 422

    def test_malformed_json_returns_422(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(
            f"/manufacturers/{created.id}",
            content=b'{"name": ',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_literal_null_body_returns_422(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(f"/manufacturers/{created.id}", json=None)
        assert response.status_code == 422

    def test_array_body_returns_422(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.patch(f"/manufacturers/{created.id}", json=[])
        assert response.status_code == 422

    def test_rejected_bodies_leave_row_untouched(
        self, client, db, make_manufacturer
    ):
        created = make_manufacturer("ООО ИММИД")
        client.patch(f"/manufacturers/{created.id}")
        client.patch(
            f"/manufacturers/{created.id}",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        db.expire_all()
        assert db.get(Manufacturer, created.id).name == "ООО ИММИД"


class TestPatchDoesNotAffectOtherContracts:
    def test_get_still_works(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        assert client.get(f"/manufacturers/{created.id}").status_code == 200

    def test_list_still_works(self, client, make_manufacturer):
        make_manufacturer("ООО ИММИД")
        assert client.get("/manufacturers").status_code == 200

    def test_post_still_works(self, client):
        assert client.post(
            "/manufacturers", json={"name": "Новый"}
        ).status_code == 201

    def test_delete_not_registered(self, client, make_manufacturer):
        created = make_manufacturer("ООО ИММИД")
        response = client.delete(f"/manufacturers/{created.id}")
        assert response.status_code == 405