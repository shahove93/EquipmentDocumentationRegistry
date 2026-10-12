import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.issuers.schemas import IssuerCreate
from app.database.connection import get_db
from app.main import app
from app.models.issuer import Issuer
from app.services.issuer_service import IssuerService

NAME = "Федеральный центр сертификации"
OTHER = "TÜV SÜD Product Services"
THIRD = "Росаккредитация"

_MISSING = object()


@pytest.fixture
def client(db: Session):
    """HTTP client whose sessions point at the isolated test schema.

    Without this override `get_db` would hand out sessions bound to the
    working database, and these tests would write into real data.

    Any override that was already registered for `get_db` is saved and put back
    in the finally block, and overrides for other dependencies are never
    touched. A failing test cannot leak the override either way.
    """
    previous = app.dependency_overrides.get(get_db, _MISSING)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous is _MISSING:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous


@pytest.fixture
def make_issuer(db):
    def _make(name: str = NAME) -> Issuer:
        return IssuerService.create(db, IssuerCreate(name=name))

    return _make


class TestCreateIssuer:
    def test_returns_201(self, client):
        assert client.post("/issuers", json={"name": NAME}).status_code == 201

    def test_returns_created_body(self, client):
        body = client.post("/issuers", json={"name": NAME}).json()
        assert body["name"] == NAME
        assert isinstance(body["id"], int)

    def test_body_has_only_id_and_name(self, client):
        body = client.post("/issuers", json={"name": NAME}).json()
        assert set(body) == {"id", "name"}

    def test_content_type_is_json(self, client):
        response = client.post("/issuers", json={"name": NAME})
        assert response.headers["content-type"].startswith("application/json")

    def test_row_is_persisted(self, client, db):
        body = client.post("/issuers", json={"name": NAME}).json()
        db.expire_all()
        stored = db.get(Issuer, body["id"])
        assert stored is not None
        assert stored.name == NAME

    def test_persisted_in_isolated_schema(self, client, db):
        body = client.post("/issuers", json={"name": NAME}).json()
        assert db.scalar(select(func.count()).select_from(Issuer)) == 1
        assert db.get(Issuer, body["id"]) is not None

    def test_russian_name_accepted(self, client, db):
        body = client.post("/issuers", json={"name": THIRD}).json()
        assert body["name"] == THIRD
        db.expire_all()
        assert db.get(Issuer, body["id"]).name == THIRD

    def test_latin_name_accepted(self, client, db):
        body = client.post("/issuers", json={"name": OTHER}).json()
        assert body["name"] == OTHER
        db.expire_all()
        assert db.get(Issuer, body["id"]).name == OTHER

    def test_name_is_normalized(self, client, db):
        body = client.post("/issuers", json={"name": f"  {NAME}  "}).json()
        assert body["name"] == NAME
        db.expire_all()
        assert db.get(Issuer, body["id"]).name == NAME

    def test_max_length_accepted(self, client, db):
        name = "Я" * 255
        response = client.post("/issuers", json={"name": name})
        assert response.status_code == 201
        db.expire_all()
        assert db.get(Issuer, response.json()["id"]).name == name

    def test_over_max_length_rejected(self, client):
        assert client.post("/issuers", json={"name": "Я" * 256}).status_code == 422

    def test_over_max_length_persists_nothing(self, client, db):
        client.post("/issuers", json={"name": "Я" * 256})
        assert db.scalar(select(func.count()).select_from(Issuer)) == 0

    def test_ids_are_unique(self, client):
        first = client.post("/issuers", json={"name": NAME}).json()
        second = client.post("/issuers", json={"name": OTHER}).json()
        assert first["id"] != second["id"]

    def test_creating_issuer_touches_no_manufacturer(self, client, db):
        from app.models.manufacturer import Manufacturer

        client.post("/issuers", json={"name": NAME})
        assert db.scalar(select(func.count()).select_from(Manufacturer)) == 0


class TestCreateLocationHeader:
    def test_location_header_present(self, client):
        response = client.post("/issuers", json={"name": NAME})
        assert "Location" in response.headers

    def test_location_points_to_created_resource(self, client):
        response = client.post("/issuers", json={"name": NAME})
        body = response.json()
        assert response.headers["Location"].endswith(f"/issuers/{body['id']}")

    def test_location_is_followable_and_matches_body(self, client):
        response = client.post("/issuers", json={"name": NAME})
        follow_up = client.get(response.headers["Location"])
        assert follow_up.status_code == 200
        assert follow_up.json() == response.json()

    def test_location_is_absolute_url(self, client):
        location = client.post("/issuers", json={"name": NAME}).headers["Location"]
        assert location.startswith("http://")

    def test_location_absent_on_conflict(self, client):
        client.post("/issuers", json={"name": NAME})
        conflict = client.post("/issuers", json={"name": NAME})
        assert conflict.status_code == 409
        assert "Location" not in conflict.headers

    def test_location_absent_on_validation_error(self, client):
        response = client.post("/issuers", json={"name": ""})
        assert response.status_code == 422
        assert "Location" not in response.headers


class TestCreateConflict:
    def test_duplicate_name_returns_409(self, client):
        client.post("/issuers", json={"name": NAME})
        assert client.post("/issuers", json={"name": NAME}).status_code == 409

    def test_conflict_detail_mentions_name(self, client):
        client.post("/issuers", json={"name": NAME})
        body = client.post("/issuers", json={"name": NAME}).json()
        assert NAME in body["detail"]

    def test_conflict_persists_nothing(self, client, db):
        client.post("/issuers", json={"name": NAME})
        client.post("/issuers", json={"name": NAME})
        assert db.scalar(select(func.count()).select_from(Issuer)) == 1

    def test_whitespace_variant_is_a_conflict(self, client):
        client.post("/issuers", json={"name": NAME})
        assert client.post(
            "/issuers", json={"name": f"  {NAME}  "}
        ).status_code == 409

    def test_can_create_after_conflict(self, client, db):
        client.post("/issuers", json={"name": NAME})
        assert client.post("/issuers", json={"name": NAME}).status_code == 409
        assert not db.in_transaction()
        recovered = client.post("/issuers", json={"name": OTHER})
        assert recovered.status_code == 201
        assert recovered.json()["name"] == OTHER

    def test_repeated_conflicts_then_success(self, client):
        client.post("/issuers", json={"name": NAME})
        for _ in range(3):
            assert client.post("/issuers", json={"name": NAME}).status_code == 409
        assert client.post("/issuers", json={"name": THIRD}).status_code == 201

    def test_distinct_names_both_created(self, client):
        assert client.post("/issuers", json={"name": NAME}).status_code == 201
        assert client.post("/issuers", json={"name": OTHER}).status_code == 201


class TestCreateCaseSensitivity:
    """Documented current behaviour: C.UTF-8 compares case-sensitively."""

    def test_different_case_is_accepted(self, client):
        first = client.post("/issuers", json={"name": "Росаккредитация"})
        second = client.post("/issuers", json={"name": "РОСАККРЕДИТАЦИЯ"})
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] != second.json()["id"]

    def test_identical_case_is_a_conflict(self, client):
        client.post("/issuers", json={"name": "Росаккредитация"})
        assert client.post(
            "/issuers", json={"name": "Росаккредитация"}
        ).status_code == 409

    def test_case_is_preserved(self, client, db):
        body = client.post("/issuers", json={"name": "ПАСПОРТ"}).json()
        assert body["name"] == "ПАСПОРТ"
        db.expire_all()
        assert db.get(Issuer, body["id"]).name == "ПАСПОРТ"

    def test_latin_case_behaves_the_same(self, client):
        assert client.post("/issuers", json={"name": "Manual"}).status_code == 201
        assert client.post("/issuers", json={"name": "manual"}).status_code == 201
        assert client.post("/issuers", json={"name": "Manual"}).status_code == 409


class TestCreateValidation:
    def test_empty_name_returns_422(self, client):
        assert client.post("/issuers", json={"name": ""}).status_code == 422

    def test_whitespace_name_returns_422(self, client):
        assert client.post("/issuers", json={"name": "   "}).status_code == 422

    def test_tabs_only_name_returns_422(self, client):
        assert client.post("/issuers", json={"name": "\t\n "}).status_code == 422

    def test_missing_name_returns_422(self, client):
        assert client.post("/issuers", json={}).status_code == 422

    def test_null_name_returns_422(self, client):
        assert client.post("/issuers", json={"name": None}).status_code == 422

    def test_wrong_type_returns_422(self, client):
        assert client.post("/issuers", json={"name": 42}).status_code == 422

    def test_validation_error_has_detail_list(self, client):
        body = client.post("/issuers", json={"name": ""}).json()
        assert isinstance(body["detail"], list)
        assert body["detail"][0]["loc"] == ["body", "name"]

    def test_validation_errors_persist_nothing(self, client, db):
        for payload in ({"name": ""}, {"name": "  "}, {}, {"name": "Я" * 256}):
            client.post("/issuers", json=payload)
        assert db.scalar(select(func.count()).select_from(Issuer)) == 0


class TestGetIssuer:
    def test_returns_existing(self, client, make_issuer):
        created = make_issuer()
        response = client.get(f"/issuers/{created.id}")
        assert response.status_code == 200
        assert response.json() == {"id": created.id, "name": NAME}

    def test_body_has_only_id_and_name(self, client, make_issuer):
        created = make_issuer()
        assert set(client.get(f"/issuers/{created.id}").json()) == {"id", "name"}

    def test_content_type_is_json(self, client, make_issuer):
        created = make_issuer()
        response = client.get(f"/issuers/{created.id}")
        assert response.headers["content-type"].startswith("application/json")

    def test_created_id_is_retrievable(self, client):
        created = client.post("/issuers", json={"name": NAME}).json()
        assert client.get(f"/issuers/{created['id']}").json() == created

    def test_latin_name_round_trip(self, client, make_issuer):
        created = make_issuer(OTHER)
        assert client.get(f"/issuers/{created.id}").json()["name"] == OTHER

    def test_max_length_name_round_trip(self, client, make_issuer):
        created = make_issuer("Я" * 255)
        assert client.get(f"/issuers/{created.id}").json()["name"] == "Я" * 255

    def test_returns_404_when_missing(self, client):
        assert client.get("/issuers/999999").status_code == 404

    def test_missing_detail_mentions_id(self, client):
        assert "4242" in client.get("/issuers/4242").json()["detail"]

    def test_non_integer_id_returns_422(self, client):
        assert client.get("/issuers/abc").status_code == 422

    def test_float_id_returns_422(self, client):
        assert client.get("/issuers/1.5").status_code == 422

    def test_get_creates_nothing(self, client, db):
        client.get("/issuers/999999")
        assert db.scalar(select(func.count()).select_from(Issuer)) == 0

    def test_get_does_not_commit(self, client, db, make_issuer, monkeypatch):
        created = make_issuer()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        client.get(f"/issuers/{created.id}")
        assert calls == []


class TestRoutesNotImplementedYet:
    """Scope guard: DELETE and PUT are deliberately absent.

    PATCH and `GET /issuers` used to live here expecting 405; both are now real
    routes (TestPatchIssuer, TestListIssuers).
    """

    def test_delete_not_available(self, client, make_issuer):
        created = make_issuer()
        assert client.delete(f"/issuers/{created.id}").status_code == 405

    def test_put_not_available(self, client, make_issuer):
        created = make_issuer()
        assert client.put(
            f"/issuers/{created.id}", json={"name": OTHER}
        ).status_code == 405

    def test_delete_leaves_row_untouched(self, client, db, make_issuer):
        created = make_issuer()
        client.delete(f"/issuers/{created.id}")
        db.expire_all()
        stored = db.get(Issuer, created.id)
        assert stored is not None
        assert stored.name == NAME

    def test_put_leaves_row_unchanged(self, client, db, make_issuer):
        created = make_issuer()
        client.put(f"/issuers/{created.id}", json={"name": OTHER})
        db.expire_all()
        assert db.get(Issuer, created.id).name == NAME


class TestListIssuers:
    def test_empty_list_when_no_rows(self, client, db):
        assert db.scalar(select(func.count()).select_from(Issuer)) == 0
        response = client.get("/issuers")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_200(self, client):
        assert client.get("/issuers").status_code == 200

    def test_content_type_is_json(self, client):
        response = client.get("/issuers")
        assert response.headers["content-type"].startswith("application/json")

    def test_returns_all_rows(self, client, make_issuer):
        for name in (NAME, OTHER, THIRD):
            make_issuer(name)
        assert len(client.get("/issuers").json()) == 3

    def test_response_is_a_bare_json_array(self, client, make_issuer):
        make_issuer()
        body = client.get("/issuers").json()
        assert isinstance(body, list)
        assert not isinstance(body, dict)

    def test_response_has_no_envelope_fields(self, client, make_issuer):
        make_issuer()
        body = client.get("/issuers").json()
        # no total, no pagination object, no search criteria in the payload
        assert body == [{"id": 1, "name": NAME}]

    def test_items_have_only_id_and_name(self, client, make_issuer):
        make_issuer()
        assert set(client.get("/issuers").json()[0]) == {"id", "name"}

    def test_ids_are_integers(self, client, make_issuer):
        make_issuer()
        assert isinstance(client.get("/issuers").json()[0]["id"], int)

    def test_names_match_stored_rows(self, client, make_issuer):
        for name in (NAME, OTHER, THIRD):
            make_issuer(name)
        listed = client.get("/issuers").json()
        assert [item["name"] for item in listed] == [NAME, OTHER, THIRD]

    def test_russian_and_latin_names_round_trip(self, client, make_issuer):
        for name in (NAME, OTHER):
            make_issuer(name)
        listed = client.get("/issuers").json()
        assert [item["name"] for item in listed] == [NAME, OTHER]

    def test_max_length_name_round_trip(self, client, make_issuer):
        make_issuer("Я" * 255)
        assert client.get("/issuers").json()[0]["name"] == "Я" * 255

    def test_order_independent_of_name(self, client, make_issuer):
        # insertion order deliberately differs from alphabetical order
        for name in ("Яблочный", "Абрикосовый", "Янтарный"):
            make_issuer(name)
        listed = client.get("/issuers").json()
        assert [item["name"] for item in listed] == [
            "Яблочный",
            "Абрикосовый",
            "Янтарный",
        ]

    def test_order_independent_of_name_with_limit(self, client, make_issuer):
        for name in ("Яблочный", "Абрикосовый", "Янтарный"):
            make_issuer(name)
        listed = client.get("/issuers?limit=2").json()
        assert [item["name"] for item in listed] == ["Яблочный", "Абрикосовый"]

    def test_ids_are_ascending(self, client, make_issuer):
        for name in (THIRD, NAME, OTHER):
            make_issuer(name)
        ids = [item["id"] for item in client.get("/issuers").json()]
        assert ids == sorted(ids)

    def test_limit(self, client, make_issuer):
        for name in (NAME, OTHER, THIRD):
            make_issuer(name)
        assert len(client.get("/issuers?limit=2").json()) == 2

    def test_offset(self, client, make_issuer):
        for name in (NAME, OTHER, THIRD):
            make_issuer(name)
        page = client.get("/issuers?offset=2").json()
        assert [item["name"] for item in page] == [THIRD]

    def test_limit_and_offset(self, client, make_issuer):
        for name in (NAME, OTHER, THIRD):
            make_issuer(name)
        page = client.get("/issuers?limit=1&offset=1").json()
        assert [item["name"] for item in page] == [OTHER]

    def test_offset_zero_returns_from_start(self, client, make_issuer):
        for name in (NAME, OTHER, THIRD):
            make_issuer(name)
        page = client.get("/issuers?offset=0").json()
        assert [item["name"] for item in page] == [NAME, OTHER, THIRD]

    def test_offset_beyond_end_returns_empty(self, client, make_issuer):
        make_issuer()
        assert client.get("/issuers?offset=100").json() == []

    def test_limit_larger_than_table_returns_everything(self, client, make_issuer):
        make_issuer()
        assert len(client.get("/issuers?limit=100").json()) == 1

    def test_pagination_covers_every_row_exactly_once(self, client, make_issuer):
        for index in range(5):
            make_issuer(f"Организация {index}")
        seen = [
            item["id"]
            for offset in (0, 2, 4)
            for item in client.get(f"/issuers?limit=2&offset={offset}").json()
        ]
        assert len(seen) == len(set(seen)) == 5
        assert seen == sorted(seen)

    def test_pagination_is_stable_across_requests(self, client, make_issuer):
        for index in range(4):
            make_issuer(f"Организация {index}")
        first = client.get("/issuers?limit=2&offset=0").json()
        second = client.get("/issuers?limit=2&offset=0").json()
        assert first == second

    def test_defaults_are_fifty_and_zero(self):
        schema = app.openapi()["paths"]["/issuers"]["get"]["parameters"]
        defaults = {p["name"]: p["schema"]["default"] for p in schema}
        assert defaults == {"limit": 50, "offset": 0}

    def test_default_parameters_return_all_small_sets(self, client, make_issuer):
        for name in (NAME, OTHER, THIRD):
            make_issuer(name)
        page = client.get("/issuers").json()
        assert [item["name"] for item in page] == [NAME, OTHER, THIRD]

    def test_minimum_limit_allowed(self, client, make_issuer):
        for name in (NAME, OTHER, THIRD):
            make_issuer(name)
        assert len(client.get("/issuers?limit=1").json()) == 1

    def test_maximum_limit_allowed(self, client):
        assert client.get("/issuers?limit=100").status_code == 200

    def test_minimum_offset_allowed(self, client, make_issuer):
        make_issuer()
        assert len(client.get("/issuers?offset=0").json()) == 1

    def test_read_creates_no_rows(self, client, db):
        client.get("/issuers")
        assert db.scalar(select(func.count()).select_from(Issuer)) == 0

    def test_read_does_not_modify_rows(self, client, db, make_issuer):
        created = make_issuer(NAME)
        client.get("/issuers")
        client.get("/issuers?limit=1&offset=1")
        db.expire_all()
        stored = db.get(Issuer, created.id)
        assert stored is not None
        assert stored.name == NAME
        assert db.scalar(select(func.count()).select_from(Issuer)) == 1

    def test_read_does_not_commit(self, client, db, make_issuer, monkeypatch):
        make_issuer()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        client.get("/issuers")
        client.get("/issuers?limit=1&offset=0")
        assert calls == []

    def test_listed_row_is_gettable_by_id(self, client, make_issuer):
        make_issuer(NAME)
        listed = client.get("/issuers").json()[0]
        assert client.get(f"/issuers/{listed['id']}").json() == listed

    def test_item_matches_create_response(self, client):
        created = client.post("/issuers", json={"name": NAME}).json()
        assert client.get("/issuers").json() == [created]


class TestListIssuersValidation:
    def test_limit_zero_returns_422(self, client):
        assert client.get("/issuers?limit=0").status_code == 422

    def test_limit_above_max_returns_422(self, client):
        assert client.get("/issuers?limit=101").status_code == 422

    def test_negative_limit_returns_422(self, client):
        assert client.get("/issuers?limit=-1").status_code == 422

    def test_negative_offset_returns_422(self, client):
        assert client.get("/issuers?offset=-1").status_code == 422

    def test_non_integer_limit_returns_422(self, client):
        assert client.get("/issuers?limit=abc").status_code == 422

    def test_non_integer_offset_returns_422(self, client):
        assert client.get("/issuers?offset=abc").status_code == 422

    def test_float_limit_returns_422(self, client):
        assert client.get("/issuers?limit=1.5").status_code == 422

    def test_empty_limit_returns_422(self, client):
        assert client.get("/issuers?limit=").status_code == 422

    def test_unknown_query_parameter_is_ignored(self, client):
        # extra query parameters are not part of the contract and must not fail
        assert client.get("/issuers?order=name").status_code == 200

    def test_validation_error_is_a_list(self, client):
        body = client.get("/issuers?limit=0").json()
        assert isinstance(body["detail"], list)
        assert body["detail"][0]["loc"] == ["query", "limit"]

    def test_offset_validation_error_locates_offset(self, client):
        body = client.get("/issuers?offset=-1").json()
        assert body["detail"][0]["loc"] == ["query", "offset"]

    def test_invalid_parameters_create_no_rows(self, client, db):
        client.get("/issuers?limit=0")
        client.get("/issuers?offset=-1")
        assert db.scalar(select(func.count()).select_from(Issuer)) == 0

    def test_repeated_limit_uses_the_last_value(self, client, make_issuer):
        # documented FastAPI behaviour: a repeated scalar query parameter is
        # not ambiguous to the framework, so the last occurrence wins
        for name in (NAME, OTHER, THIRD):
            make_issuer(name)
        response = client.get("/issuers?limit=1&limit=2")
        assert response.status_code == 200
        assert [item["name"] for item in response.json()] == [NAME, OTHER]


class TestListDoesNotBreakOtherRoutes:
    """The collection route must not shadow the parameterised one."""

    def test_get_by_id_still_resolves(self, client, make_issuer):
        created = make_issuer()
        assert client.get(f"/issuers/{created.id}").status_code == 200

    def test_get_by_id_still_404s(self, client):
        assert client.get("/issuers/999999").status_code == 404

    def test_post_still_creates(self, client):
        assert client.post("/issuers", json={"name": NAME}).status_code == 201

    def test_post_conflict_still_409(self, client, make_issuer):
        make_issuer()
        assert client.post("/issuers", json={"name": NAME}).status_code == 409

    def test_post_location_still_resolves(self, client):
        response = client.post("/issuers", json={"name": NAME})
        assert client.get(response.headers["Location"]).status_code == 200

    def test_new_row_appears_in_list(self, client, make_issuer):
        make_issuer(NAME)
        before = len(client.get("/issuers").json())
        client.post("/issuers", json={"name": OTHER})
        after = client.get("/issuers").json()
        assert len(after) == before + 1
        assert after[-1]["name"] == OTHER

    def test_patch_still_works(self, client, make_issuer):
        created = make_issuer()
        assert client.patch(
            f"/issuers/{created.id}", json={"name": OTHER}
        ).status_code == 200

    def test_delete_still_405(self, client, make_issuer):
        created = make_issuer()
        assert client.delete(f"/issuers/{created.id}").status_code == 405

    def test_list_declared_in_openapi(self):
        operation = app.openapi()["paths"]["/issuers"]["get"]
        assert sorted(operation["responses"]) == ["200", "422"]


class TestListDoesNotBreakOtherApis:
    """Requirement: no regression in the endpoints shipped earlier."""

    def test_health(self, client):
        assert client.get("/health").json() == {"status": "ok"}

    def test_manufacturer_api(self, client):
        created = client.post("/manufacturers", json={"name": "ООО ИММИД"})
        assert created.status_code == 201
        assert client.get("/manufacturers").status_code == 200
        assert client.get(
            f"/manufacturers/{created.json()['id']}"
        ).status_code == 200

    def test_product_api(self, client):
        manufacturer = client.post("/manufacturers", json={"name": "ООО ИММИД"}).json()
        product = client.post(
            "/products",
            json={
                "name": "Труба ПЭ100 SDR11",
                "standard": "ГОСТ 58121.2-2018",
                "manufacturer_id": manufacturer["id"],
            },
        )
        assert product.status_code == 201
        assert client.get("/products").status_code == 200

    def test_variant_api(self, client):
        manufacturer = client.post("/manufacturers", json={"name": "ООО ИММИД"}).json()
        product = client.post(
            "/products",
            json={
                "name": "Труба ПЭ100 SDR11",
                "standard": "ГОСТ 58121.2-2018",
                "manufacturer_id": manufacturer["id"],
            },
        ).json()
        payload = {"size_text": "Ø63 × 5.8"}
        variant = client.post(f"/products/{product['id']}/variants", json=payload)
        assert variant.status_code == 201
        assert client.get(
            f"/products/{product['id']}/variants"
        ).status_code == 200
        assert client.post(
            f"/products/{product['id']}/variants", json=payload
        ).status_code == 409

    def test_document_type_api(self, client):
        created = client.post("/document-types", json={"name": "Паспорт"})
        assert created.status_code == 201
        assert client.get("/document-types").status_code == 200
        assert client.patch(
            f"/document-types/{created.json()['id']}", json={"name": "Декларация"}
        ).status_code == 200

    def test_issuer_and_document_type_lists_are_independent(
        self, client, db
    ):
        from app.models.document_type import DocumentType

        client.post("/issuers", json={"name": "Паспорт"})
        assert len(client.get("/issuers").json()) == 1
        assert client.get("/document-types").json() == []
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 0


class TestPatchIssuer:
    def test_returns_200(self, client, make_issuer):
        created = make_issuer()
        response = client.patch(f"/issuers/{created.id}", json={"name": OTHER})
        assert response.status_code == 200

    def test_returns_updated_body(self, client, make_issuer):
        created = make_issuer()
        body = client.patch(f"/issuers/{created.id}", json={"name": OTHER}).json()
        assert body == {"id": created.id, "name": OTHER}

    def test_body_has_only_id_and_name(self, client, make_issuer):
        created = make_issuer()
        body = client.patch(f"/issuers/{created.id}", json={"name": OTHER}).json()
        assert set(body) == {"id", "name"}

    def test_id_is_unchanged(self, client, make_issuer):
        created = make_issuer()
        body = client.patch(f"/issuers/{created.id}", json={"name": OTHER}).json()
        assert body["id"] == created.id

    def test_new_name_persisted(self, client, db, make_issuer):
        created = make_issuer()
        client.patch(f"/issuers/{created.id}", json={"name": OTHER})
        db.expire_all()
        assert db.get(Issuer, created.id).name == OTHER

    def test_whitespace_stripped(self, client, db, make_issuer):
        created = make_issuer()
        body = client.patch(
            f"/issuers/{created.id}", json={"name": f"  {OTHER}  "}
        ).json()
        assert body["name"] == OTHER
        db.expire_all()
        assert db.get(Issuer, created.id).name == OTHER

    def test_whitespace_variant_conflicts_with_stripped_row(
        self, client, make_issuer
    ):
        created = make_issuer(NAME)
        make_issuer(OTHER)
        response = client.patch(
            f"/issuers/{created.id}", json={"name": f"  {OTHER}  "}
        )
        assert response.status_code == 409

    def test_unicode_whitespace_stripped(self, client, db, make_issuer):
        created = make_issuer()
        padded = chr(0x00A0) + OTHER + chr(0x3000)
        body = client.patch(f"/issuers/{created.id}", json={"name": padded}).json()
        assert body["name"] == OTHER
        db.expire_all()
        assert db.get(Issuer, created.id).name == OTHER

    def test_updated_row_reflected_in_get(self, client, make_issuer):
        created = make_issuer()
        client.patch(f"/issuers/{created.id}", json={"name": OTHER})
        assert client.get(f"/issuers/{created.id}").json()["name"] == OTHER

    def test_updated_row_reflected_in_list(self, client, make_issuer):
        created = make_issuer()
        client.patch(f"/issuers/{created.id}", json={"name": OTHER})
        assert [i["name"] for i in client.get("/issuers").json()] == [OTHER]

    def test_rename_to_own_name_allowed(self, client, make_issuer):
        created = make_issuer()
        body = client.patch(f"/issuers/{created.id}", json={"name": NAME}).json()
        assert body["name"] == NAME

    def test_rename_frees_the_previous_name(self, client, make_issuer):
        created = make_issuer(NAME)
        client.patch(f"/issuers/{created.id}", json={"name": OTHER})
        assert client.post("/issuers", json={"name": NAME}).status_code == 201

    def test_latin_rename(self, client, db, make_issuer):
        created = make_issuer(NAME)
        body = client.patch(f"/issuers/{created.id}", json={"name": OTHER}).json()
        assert body["name"] == OTHER
        db.expire_all()
        assert db.get(Issuer, created.id).name == OTHER

    def test_row_count_unchanged(self, client, db, make_issuer):
        created = make_issuer(NAME)
        make_issuer(OTHER)
        client.patch(f"/issuers/{created.id}", json={"name": THIRD})
        assert db.scalar(select(func.count()).select_from(Issuer)) == 2

    def test_no_location_header_on_update(self, client, make_issuer):
        created = make_issuer()
        response = client.patch(f"/issuers/{created.id}", json={"name": OTHER})
        assert "Location" not in response.headers


class TestPatchIssuerLength:
    def test_max_length_accepted(self, client, db, make_issuer):
        created = make_issuer()
        name = "Я" * 255
        response = client.patch(f"/issuers/{created.id}", json={"name": name})
        assert response.status_code == 200
        db.expire_all()
        assert db.get(Issuer, created.id).name == name

    def test_over_max_length_returns_422(self, client, make_issuer):
        created = make_issuer()
        response = client.patch(f"/issuers/{created.id}", json={"name": "Я" * 256})
        assert response.status_code == 422

    def test_over_max_length_leaves_name_unchanged(self, client, db, make_issuer):
        created = make_issuer()
        client.patch(f"/issuers/{created.id}", json={"name": "Я" * 256})
        db.expire_all()
        assert db.get(Issuer, created.id).name == NAME

    def test_length_measured_after_strip(self, client, db, make_issuer):
        created = make_issuer()
        padded = f"  {'Я' * 255}  "
        response = client.patch(f"/issuers/{created.id}", json={"name": padded})
        assert response.status_code == 200
        db.expire_all()
        assert db.get(Issuer, created.id).name == "Я" * 255


class TestPatchIssuerNotFound:
    def test_unknown_id_returns_404(self, client):
        assert (
            client.patch("/issuers/999999", json={"name": OTHER}).status_code == 404
        )

    def test_unknown_id_detail_mentions_id(self, client):
        assert "4242" in client.patch("/issuers/4242", json={"name": OTHER}).json()[
            "detail"
        ]

    def test_unknown_id_with_empty_body_returns_404(self, client):
        assert client.patch("/issuers/999999", json={}).status_code == 404

    def test_unknown_id_with_invalid_body_returns_422(self, client):
        # validation runs before the lookup, so a bad body wins over the 404
        assert (
            client.patch("/issuers/999999", json={"name": ""}).status_code == 422
        )

    def test_unknown_id_creates_nothing(self, client, db):
        client.patch("/issuers/999999", json={"name": OTHER})
        assert db.scalar(select(func.count()).select_from(Issuer)) == 0

    def test_unknown_id_does_not_commit(self, client, db, monkeypatch):
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        client.patch("/issuers/999999", json={"name": OTHER})
        assert calls == []

    def test_non_integer_id_returns_422(self, client):
        assert client.patch("/issuers/abc", json={"name": OTHER}).status_code == 422


class TestPatchIssuerConflict:
    def test_rename_to_existing_returns_409(self, client, make_issuer):
        created = make_issuer(NAME)
        make_issuer(OTHER)
        assert (
            client.patch(f"/issuers/{created.id}", json={"name": OTHER}).status_code
            == 409
        )

    def test_conflict_detail_mentions_name(self, client, make_issuer):
        created = make_issuer(NAME)
        make_issuer(OTHER)
        body = client.patch(
            f"/issuers/{created.id}", json={"name": OTHER}
        ).json()
        assert OTHER in body["detail"]

    def test_name_unchanged_after_conflict(self, client, db, make_issuer):
        created = make_issuer(NAME)
        make_issuer(OTHER)
        client.patch(f"/issuers/{created.id}", json={"name": OTHER})
        db.expire_all()
        assert db.get(Issuer, created.id).name == NAME

    def test_conflict_does_not_partially_save(self, client, make_issuer):
        created = make_issuer(NAME)
        make_issuer(OTHER)
        before = client.get(f"/issuers/{created.id}").json()
        client.patch(f"/issuers/{created.id}", json={"name": OTHER})
        assert client.get(f"/issuers/{created.id}").json() == before

    def test_session_usable_after_conflict(self, client, db, make_issuer):
        created = make_issuer(NAME)
        make_issuer(OTHER)
        assert client.patch(
            f"/issuers/{created.id}", json={"name": OTHER}
        ).status_code == 409
        assert not db.in_transaction()
        recovered = client.patch(
            f"/issuers/{created.id}", json={"name": THIRD}
        )
        assert recovered.status_code == 200
        assert recovered.json()["name"] == THIRD

    def test_create_usable_after_conflict(self, client, make_issuer):
        created = make_issuer(NAME)
        make_issuer(OTHER)
        client.patch(f"/issuers/{created.id}", json={"name": OTHER})
        assert client.post("/issuers", json={"name": "Новая организация"}).status_code == 201

    def test_other_issuers_untouched_after_conflict(self, client, db, make_issuer):
        created = make_issuer(NAME)
        other = make_issuer(OTHER)
        client.patch(f"/issuers/{created.id}", json={"name": OTHER})
        db.expire_all()
        assert db.get(Issuer, other.id).name == OTHER

    def test_conflict_persists_nothing_new(self, client, db, make_issuer):
        created = make_issuer(NAME)
        make_issuer(OTHER)
        client.patch(f"/issuers/{created.id}", json={"name": OTHER})
        assert db.scalar(select(func.count()).select_from(Issuer)) == 2


class TestPatchIssuerCaseSensitivity:
    """Documented current behaviour: C.UTF-8 compares case-sensitively."""

    def test_rename_to_different_case_is_allowed(self, client, db, make_issuer):
        created = make_issuer("Росаккредитация")
        response = client.patch(
            f"/issuers/{created.id}", json={"name": "РОСАККРЕДИТАЦИЯ"}
        )
        assert response.status_code == 200
        db.expire_all()
        assert db.get(Issuer, created.id).name == "РОСАККРЕДИТАЦИЯ"

    def test_rename_to_identical_case_of_other_row_conflicts(
        self, client, make_issuer
    ):
        created = make_issuer("Росаккредитация")
        make_issuer("РОСАККРЕДИТАЦИЯ")
        response = client.patch(
            f"/issuers/{created.id}", json={"name": "РОСАККРЕДИТАЦИЯ"}
        )
        assert response.status_code == 409

    def test_rename_to_own_identical_name_allowed(self, client, make_issuer):
        created = make_issuer("Росаккредитация")
        response = client.patch(
            f"/issuers/{created.id}", json={"name": "Росаккредитация"}
        )
        assert response.status_code == 200

    def test_case_only_change_persisted(self, client, db, make_issuer):
        created = make_issuer("Росаккредитация")
        client.patch(f"/issuers/{created.id}", json={"name": "пАсПоРт"})
        db.expire_all()
        assert db.get(Issuer, created.id).name == "пАсПоРт"


class TestPatchIssuerEmptyPayload:
    def test_empty_object_returns_200(self, client, make_issuer):
        created = make_issuer()
        assert client.patch(f"/issuers/{created.id}", json={}).status_code == 200

    def test_empty_object_returns_current_representation(self, client, make_issuer):
        created = make_issuer()
        body = client.patch(f"/issuers/{created.id}", json={}).json()
        assert body == {"id": created.id, "name": NAME}

    def test_empty_object_changes_nothing(self, client, db, make_issuer):
        created = make_issuer()
        client.patch(f"/issuers/{created.id}", json={})
        db.expire_all()
        assert db.get(Issuer, created.id).name == NAME

    def test_empty_object_does_not_commit(self, client, db, make_issuer, monkeypatch):
        created = make_issuer()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        client.patch(f"/issuers/{created.id}", json={})
        assert calls == []

    def test_missing_body_returns_422(self, client, make_issuer):
        created = make_issuer()
        assert client.patch(f"/issuers/{created.id}").status_code == 422

    def test_missing_body_leaves_row_unchanged(self, client, db, make_issuer):
        created = make_issuer()
        client.patch(f"/issuers/{created.id}")
        db.expire_all()
        assert db.get(Issuer, created.id).name == NAME

    def test_invalid_json_returns_422(self, client, make_issuer):
        created = make_issuer()
        response = client.patch(
            f"/issuers/{created.id}",
            content="{not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_invalid_json_leaves_row_unchanged(self, client, db, make_issuer):
        created = make_issuer()
        client.patch(
            f"/issuers/{created.id}",
            content="{not json",
            headers={"Content-Type": "application/json"},
        )
        db.expire_all()
        assert db.get(Issuer, created.id).name == NAME

    def test_empty_json_body_returns_422(self, client, make_issuer):
        created = make_issuer()
        response = client.patch(
            f"/issuers/{created.id}",
            content="",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_non_object_body_returns_422(self, client, make_issuer):
        created = make_issuer()
        response = client.patch(
            f"/issuers/{created.id}",
            content='"строка"',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestPatchIssuerValidation:
    def test_null_name_returns_422(self, client, make_issuer):
        created = make_issuer()
        assert (
            client.patch(f"/issuers/{created.id}", json={"name": None}).status_code
            == 422
        )

    def test_null_name_leaves_row_unchanged(self, client, db, make_issuer):
        created = make_issuer()
        client.patch(f"/issuers/{created.id}", json={"name": None})
        db.expire_all()
        assert db.get(Issuer, created.id).name == NAME

    def test_empty_string_returns_422(self, client, make_issuer):
        created = make_issuer()
        assert (
            client.patch(f"/issuers/{created.id}", json={"name": ""}).status_code
            == 422
        )

    def test_ascii_whitespace_returns_422(self, client, make_issuer):
        created = make_issuer()
        assert (
            client.patch(f"/issuers/{created.id}", json={"name": "   "}).status_code
            == 422
        )

    def test_unicode_whitespace_returns_422(self, client, make_issuer):
        created = make_issuer()
        for codepoint in (0x00A0, 0x2009, 0x3000, 0x202F):
            response = client.patch(
                f"/issuers/{created.id}", json={"name": chr(codepoint)}
            )
            assert response.status_code == 422

    def test_mixed_unicode_whitespace_returns_422(self, client, make_issuer):
        created = make_issuer()
        response = client.patch(
            f"/issuers/{created.id}", json={"name": chr(0x00A0) + chr(0x2009) + " "}
        )
        assert response.status_code == 422

    def test_wrong_type_returns_422(self, client, make_issuer):
        created = make_issuer()
        assert (
            client.patch(f"/issuers/{created.id}", json={"name": 42}).status_code
            == 422
        )

    def test_unknown_field_is_ignored(self, client, make_issuer):
        created = make_issuer()
        response = client.patch(
            f"/issuers/{created.id}", json={"country": "РФ"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == NAME

    def test_validation_error_is_a_list(self, client, make_issuer):
        created = make_issuer()
        body = client.patch(f"/issuers/{created.id}", json={"name": None}).json()
        assert isinstance(body["detail"], list)
        assert body["detail"][0]["loc"] == ["body", "name"]

    def test_validation_failures_persist_nothing(self, client, db, make_issuer):
        created = make_issuer()
        for payload in (
            {"name": None},
            {"name": ""},
            {"name": "  "},
            {"name": chr(0x00A0)},
            {"name": "Я" * 256},
        ):
            client.patch(f"/issuers/{created.id}", json=payload)
        db.expire_all()
        assert db.get(Issuer, created.id).name == NAME
        assert db.scalar(select(func.count()).select_from(Issuer)) == 1


class TestPatchDoesNotBreakOtherRoutes:
    def test_post_still_creates(self, client):
        assert client.post("/issuers", json={"name": NAME}).status_code == 201

    def test_post_location_still_resolves(self, client):
        response = client.post("/issuers", json={"name": NAME})
        assert client.get(response.headers["Location"]).status_code == 200

    def test_post_conflict_still_409(self, client, make_issuer):
        make_issuer()
        assert client.post("/issuers", json={"name": NAME}).status_code == 409

    def test_get_by_id_still_works(self, client, make_issuer):
        created = make_issuer()
        assert client.get(f"/issuers/{created.id}").status_code == 200

    def test_get_by_id_still_404s(self, client):
        assert client.get("/issuers/999999").status_code == 404

    def test_list_still_works(self, client, make_issuer):
        make_issuer()
        assert client.get("/issuers").status_code == 200

    def test_list_still_paginates(self, client, make_issuer):
        for name in (NAME, OTHER, THIRD):
            make_issuer(name)
        assert len(client.get("/issuers?limit=2&offset=1").json()) == 2

    def test_delete_still_405(self, client, make_issuer):
        created = make_issuer()
        assert client.delete(f"/issuers/{created.id}").status_code == 405

    def test_put_still_405(self, client, make_issuer):
        created = make_issuer()
        assert client.put(
            f"/issuers/{created.id}", json={"name": OTHER}
        ).status_code == 405

    def test_create_patch_round_trip(self, client):
        created = client.post("/issuers", json={"name": NAME}).json()
        patched = client.patch(
            f"/issuers/{created['id']}", json={"name": OTHER}
        ).json()
        assert patched["id"] == created["id"]
        assert client.get(f"/issuers/{created['id']}").json() == patched
        assert client.get("/issuers").json() == [patched]

    def test_patch_declared_in_openapi(self):
        operation = app.openapi()["paths"]["/issuers/{issuer_id}"]["patch"]
        assert sorted(operation["responses"]) == ["200", "422"]
        ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("IssuerUpdate")


class TestDependencyOverrideHygiene:
    """Requirement 15: the override must be scoped to the test that asked for it."""

    def test_override_active_during_test(self, client):
        assert get_db in app.dependency_overrides

    def test_override_absent_for_tests_that_do_not_request_it(self, db):
        # this test does not use the `client` fixture, so no override was set
        assert get_db not in app.dependency_overrides

    def test_client_writes_only_to_the_test_session(self, client, db):
        client.post("/issuers", json={"name": NAME})
        assert db.scalar(select(func.count()).select_from(Issuer)) == 1

    def test_previous_override_is_restored_when_one_existed(self, db):
        sentinel = lambda: db
        app.dependency_overrides[get_db] = sentinel
        try:
            generator = client.__wrapped__(db)
            next(generator)
            assert app.dependency_overrides[get_db] is not sentinel
            with pytest.raises(StopIteration):
                next(generator)
            assert app.dependency_overrides[get_db] is sentinel
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_override_is_removed_when_none_existed(self, db):
        assert get_db not in app.dependency_overrides
        generator = client.__wrapped__(db)
        next(generator)
        with pytest.raises(StopIteration):
            next(generator)
        assert get_db not in app.dependency_overrides

    def test_unrelated_overrides_are_never_removed(self, db):
        unrelated = object()
        app.dependency_overrides[unrelated] = lambda: None
        try:
            generator = client.__wrapped__(db)
            next(generator)
            with pytest.raises(StopIteration):
                next(generator)
            assert unrelated in app.dependency_overrides
            assert get_db not in app.dependency_overrides
        finally:
            app.dependency_overrides.pop(unrelated, None)

    def test_override_is_removed_when_the_test_body_raises(self, db):
        # pytest propagates a failing test body into the fixture by throwing
        # into the generator, so the finally block must still restore state
        generator = client.__wrapped__(db)
        next(generator)
        assert get_db in app.dependency_overrides
        with pytest.raises(RuntimeError):
            generator.throw(RuntimeError("boom"))
        assert get_db not in app.dependency_overrides

    def test_previous_override_is_restored_when_the_test_body_raises(self, db):
        sentinel = lambda: db
        app.dependency_overrides[get_db] = sentinel
        try:
            generator = client.__wrapped__(db)
            next(generator)
            with pytest.raises(RuntimeError):
                generator.throw(RuntimeError("boom"))
            assert app.dependency_overrides[get_db] is sentinel
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestOtherApisUnaffected:
    """Requirement 14: no regression in the endpoints shipped earlier."""

    def test_health_still_works(self, client):
        assert client.get("/health").json() == {"status": "ok"}

    def test_manufacturer_api_still_works(self, client):
        created = client.post("/manufacturers", json={"name": "ООО ИММИД"})
        assert created.status_code == 201
        assert client.get(f"/manufacturers/{created.json()['id']}").status_code == 200
        assert client.get("/manufacturers").status_code == 200

    def test_product_api_still_works(self, client):
        manufacturer = client.post("/manufacturers", json={"name": "ООО ИММИД"}).json()
        product = client.post(
            "/products",
            json={
                "name": "Труба ПЭ100 SDR11",
                "standard": "ГОСТ 58121.2-2018",
                "manufacturer_id": manufacturer["id"],
            },
        )
        assert product.status_code == 201
        assert client.get(f"/products/{product.json()['id']}").status_code == 200

    def test_variant_api_still_works(self, client):
        manufacturer = client.post("/manufacturers", json={"name": "ООО ИММИД"}).json()
        product = client.post(
            "/products",
            json={
                "name": "Труба ПЭ100 SDR11",
                "standard": "ГОСТ 58121.2-2018",
                "manufacturer_id": manufacturer["id"],
            },
        ).json()
        payload = {"size_text": "Ø63 × 5.8"}
        variant = client.post(f"/products/{product['id']}/variants", json=payload)
        assert variant.status_code == 201
        assert client.get(f"/variants/{variant.json()['id']}").status_code == 200
        assert client.post(
            f"/products/{product['id']}/variants", json=payload
        ).status_code == 409

    def test_document_type_api_still_works(self, client):
        created = client.post("/document-types", json={"name": "Паспорт"})
        assert created.status_code == 201
        assert client.get(f"/document-types/{created.json()['id']}").status_code == 200
        assert client.get("/document-types").status_code == 200
        assert client.post(
            "/document-types", json={"name": "Паспорт"}
        ).status_code == 409

    def test_issuer_does_not_share_rows_with_document_types(self, client, db):
        from app.models.document_type import DocumentType

        client.post("/issuers", json={"name": "Паспорт"})
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 0


class TestOpenApiContract:
    def test_paths_exposed(self):
        paths = app.openapi()["paths"]
        assert "post" in paths["/issuers"]
        assert "get" in paths["/issuers/{issuer_id}"]

    def test_create_declares_201(self):
        assert "201" in app.openapi()["paths"]["/issuers"]["post"]["responses"]

    def test_create_body_is_issuer_create(self):
        ref = app.openapi()["paths"]["/issuers"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        assert ref.endswith("IssuerCreate")

    def test_get_response_is_issuer_read(self):
        ref = app.openapi()["paths"]["/issuers/{issuer_id}"]["get"]["responses"][
            "200"
        ]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("IssuerRead")

    def test_error_codes_are_not_declared(self):
        # project convention: no router passes `responses=`, so 404/409 are
        # raised via HTTPException and documented only by runtime behaviour
        paths = app.openapi()["paths"]
        assert "404" not in paths["/issuers/{issuer_id}"]["get"]["responses"]
        assert "409" not in paths["/issuers"]["post"]["responses"]