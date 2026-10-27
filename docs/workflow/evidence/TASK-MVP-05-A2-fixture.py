"""A2 isolated MOCK Batch API. Uses the repository's real Batch validators; no DB writes."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from app.api.batches.schemas import BatchCreate, BatchUpdate  # noqa: E402

rows = [
    {"id": 1, "variant_id": 7, "batch_number": "DETAIL-01", "manufacture_date": "2026-01-01", "quantity": "1.00", "quantity_unit": "kg"},
    {"id": 2, "variant_id": 7, "batch_number": "DETAIL-02", "manufacture_date": None, "quantity": "2.00", "quantity_unit": "kg"},
]
rows.extend(
    {"id": i, "variant_id": 7, "batch_number": f"PAGE-{i:02d}", "manufacture_date": None, "quantity": "3.00", "quantity_unit": "kg"}
    for i in range(3, 29)
)
next_id = 29
events: list[dict[str, object]] = []


def json_wire(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def model_row(model: object, row_id: int | None = None) -> dict[str, object]:
    value = model.model_dump(mode="json")  # type: ignore[attr-defined]
    if row_id is not None:
        value = {"id": row_id, **value}
    return value


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, body: object, event: dict[str, object] | None = None) -> None:
        response_wire = json_wire(body)
        if event is not None:
            event["status"] = status
            event["response_wire"] = response_wire
            event["response_content_type"] = "application/json"
        data = response_wire.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def record(self, method: str, request_wire: str | None) -> dict[str, object]:
        event: dict[str, object] = {
            "ordinal": len(events) + 1,
            "method": method,
            "path_query": self.path,
            "request_wire": request_wire,
            "request_content_type": self.headers.get("Content-Type"),
        }
        events.append(event)
        return event

    def request_json(self) -> tuple[str, object]:
        wire = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
        return wire, json.loads(wire)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/_events":
            # Events contain only immutable serialized wire snapshots and scalar metadata.
            return self.send_json(200, deepcopy(events))
        if parsed.path == "/_state":
            return self.send_json(200, deepcopy(rows))
        event = self.record("GET", None)
        if parsed.path == "/products":
            return self.send_json(200, [{"id": 1, "name": "MOCK product", "standard": "MOCK", "manufacturer_id": 1, "designation": None, "product_type": None}], event)
        if parsed.path == "/products/1/variants":
            return self.send_json(200, [{"id": 7, "product_id": 1, "size_text": "63 mm", "diameter": "63.00", "nominal_diameter": None, "wall_thickness": None}], event)
        if parsed.path == "/batches":
            query = parse_qs(parsed.query)
            offset, limit = int(query.get("offset", ["0"])[0]), int(query.get("limit", ["25"])[0])
            return self.send_json(200, rows[offset:offset + limit], event)
        if parsed.path.startswith("/batches/"):
            try:
                wanted = int(parsed.path.rsplit("/", 1)[1])
            except ValueError:
                wanted = -1
            found = next((row for row in rows if row["id"] == wanted), None)
            return self.send_json(200, found, event) if found else self.send_json(404, {"detail": "MOCK record not found"}, event)
        return self.send_json(404, {"detail": "MOCK route not found"}, event)

    def do_POST(self) -> None:
        global next_id
        wire, body = self.request_json()
        event = self.record("POST", wire)
        if self.path != "/batches" or not isinstance(body, dict):
            return self.send_json(404, {"detail": "MOCK route not found"}, event)
        try:
            validated = BatchCreate.model_validate(body)
        except Exception as exc:
            return self.send_json(422, {"detail": "MOCK request rejected by app.api.batches.schemas.BatchCreate"}, event)
        if validated.variant_id != 7:
            return self.send_json(422, {"detail": "MOCK variant 7 is the only existing variant"}, event)
        new_row = model_row(validated, next_id)
        next_id += 1
        rows.append(new_row)
        return self.send_json(201, deepcopy(new_row), event)

    def do_PATCH(self) -> None:
        wire, body = self.request_json()
        event = self.record("PATCH", wire)
        if not isinstance(body, dict):
            return self.send_json(422, {"detail": "MOCK body must be an object"}, event)
        try:
            patch = BatchUpdate.model_validate(body)
        except Exception:
            return self.send_json(422, {"detail": "MOCK request rejected by app.api.batches.schemas.BatchUpdate"}, event)
        if patch.variant_id is not None and patch.variant_id != 7:
            return self.send_json(422, {"detail": "MOCK variant 7 is the only existing variant"}, event)
        try:
            wanted = int(urlparse(self.path).path.rsplit("/", 1)[1])
        except ValueError:
            wanted = -1
        row = next((item for item in rows if item["id"] == wanted), None)
        if row is None:
            return self.send_json(404, {"detail": "MOCK record not found"}, event)
        # Pydantic serializes Decimal as exact JSON strings and dates as ISO strings.
        row.update(patch.model_dump(exclude_unset=True, mode="json"))
        return self.send_json(200, deepcopy(row), event)

    def log_message(self, _fmt: str, *_args: object) -> None:
        pass


print("MOCK ONLY: Batch API at 127.0.0.1:8002; in-memory rows 1-28; real BatchCreate/BatchUpdate validators; no DB/storage writes", flush=True)
HTTPServer(("0.0.0.0", 8002), Handler).serve_forever()
