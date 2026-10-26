import pytest

from app.main import app


@pytest.fixture
def specification():
    # openapi() does not start lifespan or open a database connection.
    return app.openapi()


class TestBatchesOpenApi:
    def test_exact_routes_and_existing_slices(self, specification):
        paths = specification["paths"]
        batch_paths = {key: set(value) for key, value in paths.items() if "batches" in key}
        assert batch_paths == {"/batches": {"post", "get"}, "/batches/{batch_id}": {"get", "patch"}}
        assert "/issuers" in paths and "/issuers/{issuer_id}" in paths
        assert "/variants/{variant_id}" in paths and "/products/{product_id}/variants" in paths
        assert "/documents/{document_id}/variants" in paths
        assert not any("/batches" in key and key.startswith("/documents") for key in paths)
        assert len(paths) == 21
        assert sum(len(value) for value in paths.values()) == 38

    @pytest.mark.parametrize("path,method,code,request_schema", [
        ("/batches", "post", "201", "BatchCreate"),
        ("/batches", "get", "200", None),
        ("/batches/{batch_id}", "get", "200", None),
        ("/batches/{batch_id}", "patch", "200", "BatchUpdate"),
    ])
    def test_operations(self, specification, path, method, code, request_schema):
        operation = specification["paths"][path][method]
        assert operation["tags"] == ["batches"]
        assert operation["summary"]
        assert operation["operationId"]
        assert set(operation["responses"]) == {code, "422"}
        schema = operation["responses"][code]["content"]["application/json"]["schema"]
        if path == "/batches" and method == "get":
            assert schema["type"] == "array"
            schema = schema["items"]
        assert schema == {"$ref": "#/components/schemas/BatchRead"}
        if request_schema:
            assert operation["requestBody"]["required"] is True
            assert operation["requestBody"]["content"]["application/json"]["schema"] == {"$ref": f"#/components/schemas/{request_schema}"}
        else:
            assert "requestBody" not in operation
        if "{batch_id}" in path:
            parameter = next(p for p in operation["parameters"] if p["name"] == "batch_id")
            assert parameter["in"] == "path" and parameter["required"] is True
            assert parameter["schema"]["type"] == "integer"

    def test_unique_operation_ids(self, specification):
        ids = [operation["operationId"] for path in specification["paths"].values() for operation in path.values()]
        assert len(ids) == len(set(ids))

    def test_list_parameters(self, specification):
        parameters = {item["name"]: item for item in specification["paths"]["/batches"]["get"]["parameters"]}
        assert set(parameters) == {"limit", "offset"}
        assert all(p["in"] == "query" and not p["required"] for p in parameters.values())
        assert parameters["limit"]["schema"] == {"type": "integer", "minimum": 1, "maximum": 100, "default": 50, "title": "Limit"}
        assert parameters["offset"]["schema"] == {"type": "integer", "minimum": 0, "default": 0, "title": "Offset"}

    @pytest.mark.parametrize("name", ["BatchCreate", "BatchUpdate", "BatchRead"])
    def test_schema_fields_nullable_date_decimal(self, specification, name):
        schema = specification["components"]["schemas"][name]
        properties = schema["properties"]
        fields = {"variant_id", "batch_number", "manufacture_date", "quantity", "quantity_unit"}
        assert set(properties) == fields | ({"id"} if name == "BatchRead" else set())
        if name != "BatchRead":
            assert schema["additionalProperties"] is False
            assert schema.get("required", []) == (["variant_id"] if name == "BatchCreate" else [])
            for field, maximum in [("batch_number", 100), ("quantity_unit", 30)]:
                item = next(p for p in properties[field]["anyOf"] if p["type"] == "string")
                assert item["minLength"] == 1 and item["maxLength"] == maximum
        else:
            assert set(schema["required"]) == {"id", "variant_id"}
        for field in ["batch_number", "manufacture_date", "quantity", "quantity_unit"]:
            assert {"type": "null"} in properties[field]["anyOf"]
        date_schema = next(p for p in properties["manufacture_date"]["anyOf"] if p["type"] == "string")
        assert date_schema["format"] == "date"
        quantity_types = {p["type"] for p in properties["quantity"]["anyOf"]}
        assert quantity_types == ({"string", "null"} if name == "BatchRead" else {"number", "string", "null"})
