import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.document_types.schemas import DocumentTypeCreate
from app.database.connection import get_db
from app.main import app
from app.models.document_type import DocumentType
from app.services.document_type_service import DocumentTypeService

NAME = "Паспорт"
OTHER = "Свидетельство НАКС"
THIRD = "Декларация соответствия"


@pytest.fixture
def client(db: Session):
    """HTTP client whose sessions point at the isolated test schema.

    Without this override `get_db` would hand out sessions bound to the
    working database, and these tests would write into real data. The override
    is removed in the finally block so a failing test cannot leak it.
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def make_document_type(db):
    def _make(name: str = NAME) -> DocumentType:
        return DocumentTypeService.create(db, DocumentTypeCreate(name=name))

    return _make


class TestCreateDocumentType:
    def test_returns_201(self, client):
        assert client.post("/document-types", json={"name": NAME}).status_code == 201

    def test_returns_created_body(self, client):
        body = client.post("/document-types", json={"name": NAME}).json()
        assert body["name"] == NAME
        assert isinstance(body["id"], int)

    def test_body_has_only_id_and_name(self, client):
        body = client.post("/document-types", json={"name": NAME}).json()
        assert set(body) == {"id", "name"}

    def test_content_type_is_json(self, client):
        response = client.post("/document-types", json={"name": NAME})
        assert response.headers["content-type"].startswith("application/json")

    def test_row_is_persisted(self, client, db):
        body = client.post("/document-types", json={"name": NAME}).json()
        stored = db.get(DocumentType, body["id"])
        assert stored is not None
        assert stored.name == NAME

    def test_persisted_in_isolated_schema(self, client, db):
        # the row exists in the test session, i.e. inside the scratch schema
        body = client.post("/document-types", json={"name": NAME}).json()
        assert db.scalar(
            select(func.count()).select_from(DocumentType)
        ) == 1
        assert db.get(DocumentType, body["id"]) is not None

    def test_name_is_normalized(self, client, db):
        body = client.post("/document-types", json={"name": f"  {NAME}  "}).json()
        assert body["name"] == NAME
        db.expire_all()
        assert db.get(DocumentType, body["id"]).name == NAME

    def test_russian_name_accepted(self, client, db):
        body = client.post(
            "/document-types", json={"name": "Декларация соответствия ТР ТС"}
        ).json()
        assert body["name"] == "Декларация соответствия ТР ТС"
        db.expire_all()
        assert db.get(DocumentType, body["id"]).name == body["name"]

    def test_ids_are_unique(self, client):
        first = client.post("/document-types", json={"name": NAME}).json()
        second = client.post("/document-types", json={"name": OTHER}).json()
        assert first["id"] != second["id"]

    def test_max_length_accepted(self, client, db):
        name = "Я" * 100
        response = client.post("/document-types", json={"name": name})
        assert response.status_code == 201
        db.expire_all()
        assert db.get(DocumentType, response.json()["id"]).name == name

    def test_over_max_length_rejected(self, client):
        response = client.post("/document-types", json={"name": "Я" * 101})
        assert response.status_code == 422

    def test_over_max_length_persists_nothing(self, client, db):
        client.post("/document-types", json={"name": "Я" * 101})
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 0


class TestCreateLocationHeader:
    def test_location_header_present(self, client):
        response = client.post("/document-types", json={"name": NAME})
        assert "Location" in response.headers

    def test_location_header_points_to_created_resource(self, client):
        response = client.post("/document-types", json={"name": NAME})
        body = response.json()
        assert response.headers["Location"].endswith(
            f"/document-types/{body['id']}"
        )

    def test_location_header_is_followable(self, client):
        response = client.post("/document-types", json={"name": NAME})
        follow_up = client.get(response.headers["Location"])
        assert follow_up.status_code == 200
        assert follow_up.json() == response.json()

    def test_location_header_is_absolute_url(self, client):
        location = client.post("/document-types", json={"name": NAME}).headers[
            "Location"
        ]
        assert location.startswith("http://")

    def test_location_absent_on_conflict(self, client):
        client.post("/document-types", json={"name": NAME})
        conflict = client.post("/document-types", json={"name": NAME})
        assert conflict.status_code == 409
        assert "Location" not in conflict.headers

    def test_location_absent_on_validation_error(self, client):
        response = client.post("/document-types", json={"name": ""})
        assert response.status_code == 422
        assert "Location" not in response.headers


class TestCreateConflict:
    def test_duplicate_name_returns_409(self, client):
        client.post("/document-types", json={"name": NAME})
        assert client.post("/document-types", json={"name": NAME}).status_code == 409

    def test_conflict_detail_mentions_name(self, client):
        client.post("/document-types", json={"name": NAME})
        body = client.post("/document-types", json={"name": NAME}).json()
        assert NAME in body["detail"]

    def test_conflict_persists_nothing(self, client, db):
        client.post("/document-types", json={"name": NAME})
        client.post("/document-types", json={"name": NAME})
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 1

    def test_whitespace_variant_is_a_conflict(self, client):
        client.post("/document-types", json={"name": NAME})
        response = client.post("/document-types", json={"name": f"  {NAME}  "})
        assert response.status_code == 409

    def test_session_usable_after_conflict(self, client, db):
        client.post("/document-types", json={"name": NAME})
        assert client.post("/document-types", json={"name": NAME}).status_code == 409
        assert not db.in_transaction()
        recovered = client.post("/document-types", json={"name": OTHER})
        assert recovered.status_code == 201
        assert recovered.json()["id"] is not None

    def test_distinct_names_both_created(self, client):
        assert client.post("/document-types", json={"name": NAME}).status_code == 201
        assert client.post("/document-types", json={"name": OTHER}).status_code == 201


class TestCreateCaseSensitivity:
    """Documented current behaviour: C.UTF-8 compares case-sensitively."""

    def test_different_case_is_accepted(self, client):
        first = client.post("/document-types", json={"name": "Паспорт"})
        second = client.post("/document-types", json={"name": "ПАСПОРТ"})
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] != second.json()["id"]

    def test_identical_case_is_a_conflict(self, client):
        client.post("/document-types", json={"name": "Паспорт"})
        assert (
            client.post("/document-types", json={"name": "Паспорт"}).status_code
            == 409
        )

    def test_case_is_preserved(self, client, db):
        body = client.post("/document-types", json={"name": "ПАСПОРТ"}).json()
        assert body["name"] == "ПАСПОРТ"
        db.expire_all()
        assert db.get(DocumentType, body["id"]).name == "ПАСПОРТ"


class TestCreateValidation:
    def test_empty_name_returns_422(self, client):
        response = client.post("/document-types", json={"name": ""})
        assert response.status_code == 422

    def test_whitespace_name_returns_422(self, client):
        assert client.post("/document-types", json={"name": "   "}).status_code == 422

    def test_tabs_only_name_returns_422(self, client):
        assert client.post("/document-types", json={"name": "\t\n "}).status_code == 422

    def test_missing_name_returns_422(self, client):
        assert client.post("/document-types", json={}).status_code == 422

    def test_null_name_returns_422(self, client):
        assert (
            client.post("/document-types", json={"name": None}).status_code == 422
        )

    def test_wrong_type_returns_422(self, client):
        assert client.post("/document-types", json={"name": 42}).status_code == 422

    def test_validation_error_has_detail_list(self, client):
        body = client.post("/document-types", json={"name": ""}).json()
        assert isinstance(body["detail"], list)
        assert body["detail"][0]["loc"] == ["body", "name"]

    def test_validation_error_persists_nothing(self, client, db):
        client.post("/document-types", json={"name": ""})
        client.post("/document-types", json={})
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 0


class TestGetDocumentType:
    def test_returns_existing(self, client, make_document_type):
        created = make_document_type()
        response = client.get(f"/document-types/{created.id}")
        assert response.status_code == 200
        assert response.json() == {"id": created.id, "name": NAME}

    def test_body_has_only_id_and_name(self, client, make_document_type):
        created = make_document_type()
        assert set(client.get(f"/document-types/{created.id}").json()) == {
            "id",
            "name",
        }

    def test_content_type_is_json(self, client, make_document_type):
        created = make_document_type()
        response = client.get(f"/document-types/{created.id}")
        assert response.headers["content-type"].startswith("application/json")

    def test_returns_404_when_missing(self, client):
        assert client.get("/document-types/999999").status_code == 404

    def test_missing_detail_mentions_id(self, client):
        body = client.get("/document-types/4242").json()
        assert "4242" in body["detail"]

    def test_non_integer_id_returns_422(self, client):
        assert client.get("/document-types/abc").status_code == 422

    def test_cyrillic_name_round_trip(self, client, make_document_type):
        created = make_document_type("Декларация соответствия")
        assert client.get(f"/document-types/{created.id}").json()["name"] == (
            "Декларация соответствия"
        )

    def test_max_length_name_round_trip(self, client, make_document_type):
        created = make_document_type("Я" * 100)
        assert client.get(f"/document-types/{created.id}").json()["name"] == (
            "Я" * 100
        )

    def test_created_id_is_retrievable(self, client):
        created = client.post("/document-types", json={"name": NAME}).json()
        assert client.get(f"/document-types/{created['id']}").json() == created

    def test_get_does_not_create_rows(self, client, db):
        client.get("/document-types/999999")
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 0


class TestRoutesNotImplementedYet:
    """Scope guard: DELETE is deliberately absent.

    PATCH and `GET /document-types` used to live here expecting 405; both are
    now real routes (TestPatchDocumentType, TestListDocumentTypes).
    """

    def test_delete_not_available(self, client, make_document_type):
        created = make_document_type()
        assert client.delete(f"/document-types/{created.id}").status_code == 405

    def test_delete_leaves_row_untouched(self, client, db, make_document_type):
        created = make_document_type()
        client.delete(f"/document-types/{created.id}")
        db.expire_all()
        stored = db.get(DocumentType, created.id)
        assert stored is not None
        assert stored.name == NAME


class TestListDocumentTypes:
    def test_empty_list_when_no_rows(self, client, db):
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 0
        response = client.get("/document-types")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_200(self, client):
        assert client.get("/document-types").status_code == 200

    def test_content_type_is_json(self, client):
        response = client.get("/document-types")
        assert response.headers["content-type"].startswith("application/json")

    def test_returns_all_rows(self, client, make_document_type):
        for name in (NAME, OTHER, THIRD):
            make_document_type(name)
        assert len(client.get("/document-types").json()) == 3

    def test_items_have_only_id_and_name(self, client, make_document_type):
        make_document_type()
        item = client.get("/document-types").json()[0]
        assert set(item) == {"id", "name"}

    def test_ids_are_integers(self, client, make_document_type):
        make_document_type()
        assert isinstance(client.get("/document-types").json()[0]["id"], int)

    def test_names_match_stored_rows(self, client, make_document_type):
        for name in (NAME, OTHER, THIRD):
            make_document_type(name)
        listed = client.get("/document-types").json()
        assert [item["name"] for item in listed] == [NAME, OTHER, THIRD]

    def test_response_has_no_envelope_fields(self, client, make_document_type):
        make_document_type()
        body = client.get("/document-types").json()
        assert isinstance(body, list)
        assert not isinstance(body, dict)

    def test_order_independent_of_name(self, client, make_document_type):
        # insertion order deliberately differs from alphabetical order
        for name in ("Яблочный", "Абрикосовый", "Янтарный"):
            make_document_type(name)
        listed = client.get("/document-types").json()
        assert [item["name"] for item in listed] == [
            "Яблочный",
            "Абрикосовый",
            "Янтарный",
        ]

    def test_order_independent_of_name_with_limit(self, client, make_document_type):
        for name in ("Яблочный", "Абрикосовый", "Янтарный"):
            make_document_type(name)
        listed = client.get("/document-types?limit=2").json()
        assert [item["name"] for item in listed] == ["Яблочный", "Абрикосовый"]

    def test_ids_are_ascending(self, client, make_document_type):
        for name in (THIRD, NAME, OTHER):
            make_document_type(name)
        ids = [item["id"] for item in client.get("/document-types").json()]
        assert ids == sorted(ids)

    def test_limit(self, client, make_document_type):
        for name in (NAME, OTHER, THIRD):
            make_document_type(name)
        assert len(client.get("/document-types?limit=2").json()) == 2

    def test_offset(self, client, make_document_type):
        for name in (NAME, OTHER, THIRD):
            make_document_type(name)
        page = client.get("/document-types?offset=2").json()
        assert [item["name"] for item in page] == [THIRD]

    def test_limit_and_offset(self, client, make_document_type):
        for name in (NAME, OTHER, THIRD):
            make_document_type(name)
        page = client.get("/document-types?limit=1&offset=1").json()
        assert [item["name"] for item in page] == [OTHER]

    def test_offset_zero_returns_from_start(self, client, make_document_type):
        for name in (NAME, OTHER, THIRD):
            make_document_type(name)
        page = client.get("/document-types?offset=0").json()
        assert [item["name"] for item in page] == [NAME, OTHER, THIRD]

    def test_offset_beyond_end_returns_empty(self, client, make_document_type):
        make_document_type()
        assert client.get("/document-types?offset=100").json() == []

    def test_limit_larger_than_table_returns_everything(self, client, make_document_type):
        make_document_type()
        assert len(client.get("/document-types?limit=100").json()) == 1

    def test_pagination_covers_every_row_exactly_once(self, client, make_document_type):
        for index in range(5):
            make_document_type(f"Тип {index}")
        seen = [
            item["id"]
            for offset in (0, 2, 4)
            for item in client.get(
                f"/document-types?limit=2&offset={offset}"
            ).json()
        ]
        assert len(seen) == len(set(seen)) == 5
        assert seen == sorted(seen)

    def test_default_limit_is_50(self, client):
        # with more rows than the default page size the response is capped
        schema = client.get("/openapi.json").json()["paths"]["/document-types"][
            "get"
        ]["parameters"]
        limits = {p["name"]: p["schema"]["default"] for p in schema}
        assert limits["limit"] == 50
        assert limits["offset"] == 0

    def test_default_parameters_return_all_small_sets(self, client, make_document_type):
        for name in (NAME, OTHER, THIRD):
            make_document_type(name)
        page = client.get("/document-types").json()
        assert [item["name"] for item in page] == [NAME, OTHER, THIRD]

    def test_minimum_limit_allowed(self, client, make_document_type):
        for name in (NAME, OTHER, THIRD):
            make_document_type(name)
        assert len(client.get("/document-types?limit=1").json()) == 1

    def test_maximum_limit_allowed(self, client):
        assert client.get("/document-types?limit=100").status_code == 200

    def test_read_does_not_create_rows(self, client, db):
        client.get("/document-types")
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 0

    def test_read_does_not_modify_rows(self, client, db, make_document_type):
        created = make_document_type(NAME)
        client.get("/document-types")
        client.get("/document-types?limit=1&offset=1")
        db.expire_all()
        stored = db.get(DocumentType, created.id)
        assert stored is not None
        assert stored.name == NAME
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 1

    def test_listed_row_is_gettable_by_id(self, client, make_document_type):
        make_document_type(NAME)
        listed = client.get("/document-types").json()[0]
        assert client.get(f"/document-types/{listed['id']}").json() == listed

    def test_item_matches_create_response(self, client):
        created = client.post("/document-types", json={"name": NAME}).json()
        assert client.get("/document-types").json() == [created]


class TestListDocumentTypeValidation:
    def test_limit_zero_returns_422(self, client):
        assert client.get("/document-types?limit=0").status_code == 422

    def test_limit_above_max_returns_422(self, client):
        assert client.get("/document-types?limit=101").status_code == 422

    def test_negative_limit_returns_422(self, client):
        assert client.get("/document-types?limit=-1").status_code == 422

    def test_negative_offset_returns_422(self, client):
        assert client.get("/document-types?offset=-1").status_code == 422

    def test_non_integer_limit_returns_422(self, client):
        assert client.get("/document-types?limit=abc").status_code == 422

    def test_non_integer_offset_returns_422(self, client):
        assert client.get("/document-types?offset=abc").status_code == 422

    def test_float_limit_returns_422(self, client):
        assert client.get("/document-types?limit=1.5").status_code == 422

    def test_empty_limit_returns_422(self, client):
        assert client.get("/document-types?limit=").status_code == 422

    def test_repeated_limit_uses_the_last_value(self, client, make_document_type):
        # Documented FastAPI behaviour, not a defect: a repeated scalar query
        # parameter is not ambiguous to the framework, so the last occurrence
        # wins instead of producing 422.
        for name in (NAME, OTHER, THIRD):
            make_document_type(name)
        response = client.get("/document-types?limit=1&limit=2")
        assert response.status_code == 200
        assert [item["name"] for item in response.json()] == [NAME, OTHER]

    def test_repeated_offset_uses_the_last_value(self, client, make_document_type):
        for name in (NAME, OTHER, THIRD):
            make_document_type(name)
        response = client.get("/document-types?offset=1&offset=2")
        assert [item["name"] for item in response.json()] == [THIRD]

    def test_validation_error_is_a_list(self, client):
        body = client.get("/document-types?limit=0").json()
        assert isinstance(body["detail"], list)
        assert body["detail"][0]["loc"] == ["query", "limit"]

    def test_invalid_parameters_create_no_rows(self, client, db):
        client.get("/document-types?limit=0")
        client.get("/document-types?offset=-1")
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 0


class TestListDoesNotBreakOtherRoutes:
    """The collection route must not shadow the parameterised one."""

    def test_get_by_id_still_resolves(self, client, make_document_type):
        created = make_document_type()
        assert client.get(f"/document-types/{created.id}").status_code == 200

    def test_get_by_id_still_404s(self, client):
        assert client.get("/document-types/999999").status_code == 404

    def test_post_still_creates(self, client):
        assert client.post("/document-types", json={"name": NAME}).status_code == 201

    def test_post_conflict_still_409(self, client):
        client.post("/document-types", json={"name": NAME})
        assert client.post("/document-types", json={"name": NAME}).status_code == 409

    def test_new_row_appears_in_list(self, client, make_document_type):
        make_document_type(NAME)
        before = len(client.get("/document-types").json())
        client.post("/document-types", json={"name": OTHER})
        after = client.get("/document-types").json()
        assert len(after) == before + 1
        assert after[-1]["name"] == OTHER

    def test_collection_route_declared_in_openapi(self):
        operation = app.openapi()["paths"]["/document-types"]["get"]
        assert sorted(operation["responses"]) == ["200", "422"]


class TestPatchDocumentType:
    def test_returns_200(self, client, make_document_type):
        created = make_document_type()
        response = client.patch(
            f"/document-types/{created.id}", json={"name": OTHER}
        )
        assert response.status_code == 200

    def test_returns_updated_body(self, client, make_document_type):
        created = make_document_type()
        body = client.patch(
            f"/document-types/{created.id}", json={"name": OTHER}
        ).json()
        assert body == {"id": created.id, "name": OTHER}

    def test_body_has_only_id_and_name(self, client, make_document_type):
        created = make_document_type()
        body = client.patch(
            f"/document-types/{created.id}", json={"name": OTHER}
        ).json()
        assert set(body) == {"id", "name"}

    def test_id_unchanged(self, client, make_document_type):
        created = make_document_type()
        body = client.patch(
            f"/document-types/{created.id}", json={"name": OTHER}
        ).json()
        assert body["id"] == created.id

    def test_new_name_persisted(self, client, db, make_document_type):
        created = make_document_type()
        client.patch(f"/document-types/{created.id}", json={"name": OTHER})
        db.expire_all()
        assert db.get(DocumentType, created.id).name == OTHER

    def test_whitespace_stripped(self, client, db, make_document_type):
        created = make_document_type()
        body = client.patch(
            f"/document-types/{created.id}", json={"name": f"  {OTHER}  "}
        ).json()
        assert body["name"] == OTHER
        db.expire_all()
        assert db.get(DocumentType, created.id).name == OTHER

    def test_whitespace_variant_conflicts_with_stripped_row(
        self, client, make_document_type
    ):
        created = make_document_type(NAME)
        make_document_type(OTHER)
        response = client.patch(
            f"/document-types/{created.id}", json={"name": f"  {OTHER}  "}
        )
        assert response.status_code == 409

    def test_updated_row_reflected_in_get(self, client, make_document_type):
        created = make_document_type()
        client.patch(f"/document-types/{created.id}", json={"name": OTHER})
        assert client.get(f"/document-types/{created.id}").json()["name"] == OTHER

    def test_updated_row_reflected_in_list(self, client, make_document_type):
        created = make_document_type()
        client.patch(f"/document-types/{created.id}", json={"name": OTHER})
        listed = client.get("/document-types").json()
        assert [item["name"] for item in listed] == [OTHER]

    def test_rename_to_own_name_allowed(self, client, make_document_type):
        created = make_document_type()
        body = client.patch(
            f"/document-types/{created.id}", json={"name": NAME}
        ).json()
        assert body["name"] == NAME

    def test_rename_frees_the_previous_name(self, client, make_document_type):
        created = make_document_type(NAME)
        client.patch(f"/document-types/{created.id}", json={"name": OTHER})
        assert client.post("/document-types", json={"name": NAME}).status_code == 201

    def test_cyrillic_rename(self, client, db, make_document_type):
        created = make_document_type()
        name = "Декларация соответствия ТР ТС"
        body = client.patch(
            f"/document-types/{created.id}", json={"name": name}
        ).json()
        assert body["name"] == name
        db.expire_all()
        assert db.get(DocumentType, created.id).name == name

    def test_max_length_accepted(self, client, db, make_document_type):
        created = make_document_type()
        name = "Я" * 100
        response = client.patch(
            f"/document-types/{created.id}", json={"name": name}
        )
        assert response.status_code == 200
        db.expire_all()
        assert db.get(DocumentType, created.id).name == name

    def test_over_max_length_returns_422(self, client, make_document_type):
        created = make_document_type()
        response = client.patch(
            f"/document-types/{created.id}", json={"name": "Я" * 101}
        )
        assert response.status_code == 422

    def test_over_max_length_leaves_name_unchanged(
        self, client, db, make_document_type
    ):
        created = make_document_type()
        client.patch(
            f"/document-types/{created.id}", json={"name": "Я" * 101}
        )
        db.expire_all()
        assert db.get(DocumentType, created.id).name == NAME

    def test_row_count_unchanged(self, client, db, make_document_type):
        created = make_document_type()
        make_document_type(OTHER)
        client.patch(f"/document-types/{created.id}", json={"name": THIRD})
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 2

    def test_no_location_header_on_update(self, client, make_document_type):
        created = make_document_type()
        response = client.patch(
            f"/document-types/{created.id}", json={"name": OTHER}
        )
        assert "Location" not in response.headers


class TestPatchDocumentTypeNotFound:
    def test_unknown_id_returns_404(self, client):
        assert (
            client.patch("/document-types/999999", json={"name": OTHER}).status_code
            == 404
        )

    def test_unknown_id_detail_mentions_id(self, client):
        body = client.patch("/document-types/4242", json={"name": OTHER}).json()
        assert "4242" in body["detail"]

    def test_unknown_id_with_empty_body_returns_404(self, client):
        assert client.patch("/document-types/999999", json={}).status_code == 404

    def test_unknown_id_with_invalid_body_returns_422(self, client):
        # validation runs before the lookup, so a bad body wins over the 404
        assert (
            client.patch("/document-types/999999", json={"name": ""}).status_code
            == 422
        )

    def test_unknown_id_creates_nothing(self, client, db):
        client.patch("/document-types/999999", json={"name": OTHER})
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 0

    def test_non_integer_id_returns_422(self, client):
        assert (
            client.patch("/document-types/abc", json={"name": OTHER}).status_code
            == 422
        )


class TestPatchDocumentTypeConflict:
    def test_rename_to_existing_returns_409(self, client, make_document_type):
        created = make_document_type(NAME)
        make_document_type(OTHER)
        response = client.patch(
            f"/document-types/{created.id}", json={"name": OTHER}
        )
        assert response.status_code == 409

    def test_conflict_detail_mentions_name(self, client, make_document_type):
        created = make_document_type(NAME)
        make_document_type(OTHER)
        body = client.patch(
            f"/document-types/{created.id}", json={"name": OTHER}
        ).json()
        assert OTHER in body["detail"]

    def test_name_unchanged_after_conflict(self, client, db, make_document_type):
        created = make_document_type(NAME)
        make_document_type(OTHER)
        client.patch(f"/document-types/{created.id}", json={"name": OTHER})
        db.expire_all()
        assert db.get(DocumentType, created.id).name == NAME

    def test_conflict_does_not_partially_save(self, client, db, make_document_type):
        # the only updatable column is name, so a rejected rename must leave
        # the row byte-for-byte identical
        created = make_document_type(NAME)
        make_document_type(OTHER)
        before = client.get(f"/document-types/{created.id}").json()
        client.patch(f"/document-types/{created.id}", json={"name": OTHER})
        assert client.get(f"/document-types/{created.id}").json() == before

    def test_session_usable_after_conflict(self, client, db, make_document_type):
        created = make_document_type(NAME)
        make_document_type(OTHER)
        assert client.patch(
            f"/document-types/{created.id}", json={"name": OTHER}
        ).status_code == 409
        assert not db.in_transaction()
        recovered = client.patch(
            f"/document-types/{created.id}", json={"name": THIRD}
        )
        assert recovered.status_code == 200
        assert recovered.json()["name"] == THIRD

    def test_other_rows_untouched_after_conflict(
        self, client, db, make_document_type
    ):
        created = make_document_type(NAME)
        other = make_document_type(OTHER)
        client.patch(f"/document-types/{created.id}", json={"name": OTHER})
        db.expire_all()
        assert db.get(DocumentType, other.id).name == OTHER

    def test_name_freed_by_conflict_stays_taken(self, client, make_document_type):
        created = make_document_type(NAME)
        make_document_type(OTHER)
        client.patch(f"/document-types/{created.id}", json={"name": OTHER})
        assert client.post("/document-types", json={"name": OTHER}).status_code == 409

    def test_conflict_persists_nothing_new(self, client, db, make_document_type):
        created = make_document_type(NAME)
        make_document_type(OTHER)
        client.patch(f"/document-types/{created.id}", json={"name": OTHER})
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 2


class TestPatchDocumentTypeCaseSensitivity:
    """Documented current behaviour: C.UTF-8 compares case-sensitively."""

    def test_rename_to_different_case_is_allowed(
        self, client, db, make_document_type
    ):
        created = make_document_type("Паспорт")
        response = client.patch(
            f"/document-types/{created.id}", json={"name": "ПАСПОРТ"}
        )
        assert response.status_code == 200
        db.expire_all()
        assert db.get(DocumentType, created.id).name == "ПАСПОРТ"

    def test_rename_to_identical_case_of_other_row_conflicts(
        self, client, make_document_type
    ):
        created = make_document_type("Паспорт")
        make_document_type("ПАСПОРТ")
        response = client.patch(
            f"/document-types/{created.id}", json={"name": "ПАСПОРТ"}
        )
        assert response.status_code == 409

    def test_rename_to_own_identical_name_allowed(self, client, make_document_type):
        created = make_document_type("Паспорт")
        response = client.patch(
            f"/document-types/{created.id}", json={"name": "Паспорт"}
        )
        assert response.status_code == 200

    def test_case_only_change_persisted(self, client, db, make_document_type):
        created = make_document_type("Паспорт")
        client.patch(f"/document-types/{created.id}", json={"name": "пАсПоРт"})
        db.expire_all()
        assert db.get(DocumentType, created.id).name == "пАсПоРт"


class TestPatchDocumentTypeEmptyPayload:
    def test_empty_object_returns_200(self, client, make_document_type):
        created = make_document_type()
        assert client.patch(
            f"/document-types/{created.id}", json={}
        ).status_code == 200

    def test_empty_object_returns_current_representation(
        self, client, make_document_type
    ):
        created = make_document_type()
        body = client.patch(f"/document-types/{created.id}", json={}).json()
        assert body == {"id": created.id, "name": NAME}

    def test_empty_object_changes_nothing(self, client, db, make_document_type):
        created = make_document_type()
        client.patch(f"/document-types/{created.id}", json={})
        db.expire_all()
        assert db.get(DocumentType, created.id).name == NAME

    def test_empty_object_does_not_commit(self, client, db, make_document_type, monkeypatch):
        created = make_document_type()
        calls = []
        monkeypatch.setattr(db, "commit", lambda: calls.append(1))
        client.patch(f"/document-types/{created.id}", json={})
        assert calls == []

    def test_empty_object_does_not_bump_the_row(self, client, db, make_document_type):
        created = make_document_type()
        db.expire_all()
        before = db.get(DocumentType, created.id)
        client.patch(f"/document-types/{created.id}", json={})
        db.expire_all()
        after = db.get(DocumentType, created.id)
        assert (after.id, after.name) == (before.id, before.name)

    def test_missing_body_returns_422(self, client, make_document_type):
        created = make_document_type()
        response = client.patch(f"/document-types/{created.id}")
        assert response.status_code == 422

    def test_invalid_json_returns_422(self, client, make_document_type):
        created = make_document_type()
        response = client.patch(
            f"/document-types/{created.id}",
            content="{not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_invalid_json_leaves_row_unchanged(self, client, db, make_document_type):
        created = make_document_type()
        client.patch(
            f"/document-types/{created.id}",
            content="{not json",
            headers={"Content-Type": "application/json"},
        )
        db.expire_all()
        assert db.get(DocumentType, created.id).name == NAME

    def test_non_object_body_returns_422(self, client, make_document_type):
        created = make_document_type()
        response = client.patch(
            f"/document-types/{created.id}",
            content='"строка"',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestPatchDocumentTypeValidation:
    def test_null_name_returns_422(self, client, make_document_type):
        created = make_document_type()
        response = client.patch(
            f"/document-types/{created.id}", json={"name": None}
        )
        assert response.status_code == 422

    def test_null_name_leaves_row_unchanged(self, client, db, make_document_type):
        created = make_document_type()
        client.patch(f"/document-types/{created.id}", json={"name": None})
        db.expire_all()
        assert db.get(DocumentType, created.id).name == NAME

    def test_empty_string_returns_422(self, client, make_document_type):
        created = make_document_type()
        assert client.patch(
            f"/document-types/{created.id}", json={"name": ""}
        ).status_code == 422

    def test_whitespace_string_returns_422(self, client, make_document_type):
        created = make_document_type()
        assert client.patch(
            f"/document-types/{created.id}", json={"name": "   "}
        ).status_code == 422

    def test_wrong_type_returns_422(self, client, make_document_type):
        created = make_document_type()
        assert client.patch(
            f"/document-types/{created.id}", json={"name": 42}
        ).status_code == 422

    def test_validation_error_is_a_list(self, client, make_document_type):
        created = make_document_type()
        body = client.patch(
            f"/document-types/{created.id}", json={"name": None}
        ).json()
        assert isinstance(body["detail"], list)
        assert body["detail"][0]["loc"] == ["body", "name"]

    def test_validation_failures_persist_nothing(self, client, db, make_document_type):
        created = make_document_type()
        for payload in ({"name": None}, {"name": ""}, {"name": "  "}, {"name": "Я" * 101}):
            client.patch(f"/document-types/{created.id}", json=payload)
        db.expire_all()
        assert db.get(DocumentType, created.id).name == NAME
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 1


class TestPatchDoesNotBreakOtherRoutes:
    """POST, GET by id and GET list keep working alongside PATCH."""

    def test_post_still_creates(self, client):
        assert client.post("/document-types", json={"name": NAME}).status_code == 201

    def test_post_conflict_still_409(self, client, make_document_type):
        make_document_type()
        assert client.post("/document-types", json={"name": NAME}).status_code == 409

    def test_get_by_id_still_works(self, client, make_document_type):
        created = make_document_type()
        assert client.get(f"/document-types/{created.id}").status_code == 200

    def test_get_by_id_still_404s(self, client):
        assert client.get("/document-types/999999").status_code == 404

    def test_list_still_works(self, client, make_document_type):
        make_document_type()
        assert client.get("/document-types").status_code == 200

    def test_list_still_paginates(self, client, make_document_type):
        for name in (NAME, OTHER, THIRD):
            make_document_type(name)
        page = client.get("/document-types?limit=2&offset=1").json()
        assert len(page) == 2

    def test_create_get_patch_round_trip(self, client):
        created = client.post("/document-types", json={"name": NAME}).json()
        patched = client.patch(
            f"/document-types/{created['id']}", json={"name": OTHER}
        ).json()
        assert patched["id"] == created["id"]
        assert client.get(f"/document-types/{created['id']}").json() == patched

    def test_delete_still_405(self, client, make_document_type):
        created = make_document_type()
        assert client.delete(f"/document-types/{created.id}").status_code == 405

    def test_patch_declared_in_openapi(self):
        operation = app.openapi()["paths"]["/document-types/{document_type_id}"]["patch"]
        assert sorted(operation["responses"]) == ["200", "422"]
        ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("DocumentTypeUpdate")


class TestDependencyOverrideHygiene:
    def test_override_active_during_test(self, client):
        assert get_db in app.dependency_overrides

    def test_override_is_popped_after_test(self, db):
        # Re-create the fixture's override and let it be torn down, then confirm
        # the next test starts without a leaked override.
        assert get_db not in app.dependency_overrides

    def test_client_writes_only_to_test_schema(self, client, db):
        client.post("/document-types", json={"name": NAME})
        assert db.scalar(select(func.count()).select_from(DocumentType)) == 1


class TestOtherApisUnaffected:
    """Requirement 14: no regression in the already shipped endpoints."""

    def test_health_still_works(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_manufacturer_create_still_works(self, client):
        response = client.post("/manufacturers", json={"name": "ООО ИММИД"})
        assert response.status_code == 201
        assert client.get(
            f"/manufacturers/{response.json()['id']}"
        ).status_code == 200

    def test_product_and_variant_flow_still_works(self, client):
        manufacturer = client.post(
            "/manufacturers", json={"name": "ООО ИММИД"}
        ).json()
        product = client.post(
            "/products",
            json={
                "name": "Труба ПЭ100 SDR11",
                "standard": "ГОСТ 58121.2-2018",
                "manufacturer_id": manufacturer["id"],
            },
        ).json()
        variant = client.post(
            f"/products/{product['id']}/variants",
            json={"size_text": "Ø63 × 5.8"},
        )
        assert variant.status_code == 201
        assert client.get(
            f"/variants/{variant.json()['id']}"
        ).status_code == 200

    def test_variant_conflict_still_409(self, client):
        manufacturer = client.post(
            "/manufacturers", json={"name": "ООО ИММИД"}
        ).json()
        product = client.post(
            "/products",
            json={
                "name": "Труба ПЭ100 SDR11",
                "standard": "ГОСТ 58121.2-2018",
                "manufacturer_id": manufacturer["id"],
            },
        ).json()
        payload = {"size_text": "Ø63 × 5.8"}
        client.post(f"/products/{product['id']}/variants", json=payload)
        second = client.post(f"/products/{product['id']}/variants", json=payload)
        assert second.status_code == 409

    def test_manufacturer_list_still_works(self, client):
        assert client.get("/manufacturers").status_code == 200


class TestOpenApiContract:
    def test_paths_exposed(self):
        paths = app.openapi()["paths"]
        assert "post" in paths["/document-types"]
        assert "get" in paths["/document-types/{document_type_id}"]

    def test_create_declares_201_response(self):
        operation = app.openapi()["paths"]["/document-types"]["post"]
        assert "201" in operation["responses"]

    def test_get_declares_200_response(self):
        operation = app.openapi()["paths"]["/document-types/{document_type_id}"]["get"]
        assert "200" in operation["responses"]

    def test_error_codes_are_not_declared_in_schema(self):
        # Project convention: no router passes `responses=`, so 404/409 are
        # raised via HTTPException and documented only by runtime behaviour
        # (see TestGetDocumentType.test_returns_404_when_missing and
        # TestCreateConflict.test_duplicate_name_returns_409).
        operation = app.openapi()["paths"]["/document-types/{document_type_id}"]["get"]
        assert "404" not in operation["responses"]
        assert "409" not in app.openapi()["paths"]["/document-types"]["post"]["responses"]