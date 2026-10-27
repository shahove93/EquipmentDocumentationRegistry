"""Bounded schema-backed HTTP probes for A2's isolated MOCK fixture."""
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8002"
OUT = Path(__file__).with_name("TASK-MVP-05-A2-validation.json")


def get(path):
    with urlopen(BASE + path) as response:
        return response.status, response.read().decode("utf-8")


def send(method, path, body):
    request_wire = json.dumps(body, separators=(",", ":"))
    request = Request(BASE + path, data=request_wire.encode(), method=method,
                      headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urlopen(request) as response:
            return {"method": method, "path": path, "request_wire": request_wire,
                    "status": response.status, "response_wire": response.read().decode()}
    except HTTPError as response:
        return {"method": method, "path": path, "request_wire": request_wire,
                "status": response.code, "response_wire": response.read().decode()}


before_status, before_wire = get("/_state")
probes = [
    send("POST", "/batches", {"variant_id": 7, "batch_number": "INVALID-SCALE",
                                "manufacture_date": "2027-02-03", "quantity": "12345.678",
                                "quantity_unit": "kg"}),
    send("PATCH", "/batches/1", {"quantity": "0"}),
    send("PATCH", "/batches/1", {"quantity": "12345.678"}),
]
after_status, after_wire = get("/_state")
assert before_status == after_status == 200
assert [probe["status"] for probe in probes] == [422, 422, 422], probes
assert before_wire == after_wire, "rejected POST/PATCH changed the in-memory records"

OUT.write_text(json.dumps({
    "kind": "isolated MOCK validation smoke; no DB/storage writes",
    "validator_source": "app/api/batches/schemas.py BatchCreate/BatchUpdate importing app/api/variants/schemas.py Measurement",
    "quantity_contract": "finite positive Decimal <= 99999999.99, scale <= 2; null allowed; exact JSON string",
    "state_before_wire": before_wire,
    "probes": probes,
    "state_after_wire": after_wire,
    "state_unchanged": True,
}, indent=2) + "\n", encoding="utf-8")
print(f"A2 validator probe passed: {len(probes)} invalid requests returned 422; state unchanged; {OUT}")
