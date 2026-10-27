"""Validate the completed A2 browser CRUD trace against captured wire strings."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
events = json.loads((ROOT / "TASK-MVP-05-A2-api-log.json").read_text(encoding="utf-8"))


def find(method, path, after=0):
    for event in events:
        if event["ordinal"] > after and event["method"] == method and event["path_query"] == path:
            return event
    raise AssertionError(f"missing {method} {path} after ordinal {after}")


def body(event, field):
    wire = event[field]
    return json.loads(wire) if wire is not None else None


list_initial = find("GET", "/batches?limit=26&offset=0")
detail_initial = find("GET", "/batches/1", list_initial["ordinal"])
create = find("POST", "/batches", detail_initial["ordinal"])
created = body(create, "response_wire")
assert create["status"] == 201
assert body(create, "request_wire") == {
    "variant_id": 7,
    "batch_number": "A2-BROWSER-001",
    "manufacture_date": "2027-02-03",
    "quantity": "12345.67",
    "quantity_unit": "kg",
}
assert created == {"id": 29, "variant_id": 7, "batch_number": "A2-BROWSER-001",
                   "manufacture_date": "2027-02-03", "quantity": "12345.67", "quantity_unit": "kg"}

read_created = find("GET", "/batches/29", create["ordinal"])
assert read_created["status"] == 200 and body(read_created, "response_wire") == created
edit = find("PATCH", "/batches/29", read_created["ordinal"])
assert edit["status"] == 200 and body(edit, "request_wire") == {"batch_number": "A2-BROWSER-001-EDITED"}
edited = body(edit, "response_wire")
assert edited["manufacture_date"] == "2027-02-03" and edited["quantity"] == "12345.67" and edited["quantity_unit"] == "kg"
clear = find("PATCH", "/batches/29", edit["ordinal"])
assert clear["status"] == 200 and body(clear, "request_wire") == {"manufacture_date": None}
cleared = body(clear, "response_wire")
assert cleared == {"id": 29, "variant_id": 7, "batch_number": "A2-BROWSER-001-EDITED",
                   "manufacture_date": None, "quantity": "12345.67", "quantity_unit": "kg"}
final_get = find("GET", "/batches/29", clear["ordinal"])
assert final_get["status"] == 200 and body(final_get, "response_wire") == cleared

# These earlier response snapshots remain the exact serialized wire strings after later edits.
assert json.loads(create["response_wire"]) == created
assert json.loads(read_created["response_wire"]) == created
assert "A2-BROWSER-001\"" in create["response_wire"] and "2027-02-03" in create["response_wire"]
assert "A2-BROWSER-001-EDITED" not in create["response_wire"] and "\"manufacture_date\":null" not in create["response_wire"]

steps = [list_initial, detail_initial, create, read_created, edit, clear, final_get]
report = {
    "kind": "verified browser CRUD trace against isolated MOCK; no DB/storage writes",
    "record_id": 29,
    "trace_ordinals": [event["ordinal"] for event in steps],
    "trace": [{"ordinal": event["ordinal"], "method": event["method"], "path_query": event["path_query"],
               "status": event["status"], "request_wire": event["request_wire"],
               "response_wire": event["response_wire"]} for event in steps],
    "create_snapshot_unchanged_after_edit_and_clear": True,
    "created_read_snapshot_unchanged_after_edit_and_clear": True,
    "quantity_exact_string": created["quantity"] == "12345.67",
    "clear_preserved_variant_number_quantity_unit": all(
        cleared[key] == edited[key] for key in ("variant_id", "batch_number", "quantity", "quantity_unit")
    ),
    "final_detail_get_after_clear": final_get["ordinal"] > clear["ordinal"] and body(final_get, "response_wire") == cleared,
}
(ROOT / "TASK-MVP-05-A2-crud-trace.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"A2 trace verified: record 29; ordinals {report['trace_ordinals']}; immutable POST/GET response strings retained after edit and clear")
