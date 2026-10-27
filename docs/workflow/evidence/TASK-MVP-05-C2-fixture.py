"""C2 temporary in-memory mock API for browser evidence; no DB/storage writes."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
from urllib.parse import urlparse, parse_qs

rows = [
    {"id": 1, "variant_id": 7, "batch_number": "DELAY-A", "manufacture_date": "2026-01-01", "quantity": "1.00", "quantity_unit": "kg"},
    {"id": 2, "variant_id": 7, "batch_number": "SELECT-B", "manufacture_date": None, "quantity": "2.00", "quantity_unit": "kg"},
]
# Enough in-memory rows to exercise a second page and its disabled end control.
rows.extend(
    {"id": row_id, "variant_id": 7, "batch_number": f"PAGE-{row_id:02d}", "manufacture_date": None, "quantity": "3.00", "quantity_unit": "kg"}
    for row_id in range(3, 29)
)
next_id = 29
requests = []

class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data).encode()
        if self.path != '/_requests' and requests:
            requests[-1]['status'] = status
            requests[-1]['response_body'] = data
            requests[-1]['response_headers'] = {'Content-Type': 'application/json'}
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/_requests': return self.reply(200, requests.copy())
        entry = {'method': 'GET', 'path': self.path, 'request_body': None}
        requests.append(entry)
        if path == '/products': return self.reply(200, [{'id': 1, 'name': 'Mock product', 'standard': 'MOCK', 'manufacturer_id': 1, 'designation': None, 'product_type': None}])
        if path == '/products/1/variants': return self.reply(200, [{'id': 7, 'product_id': 1, 'size_text': '63 mm', 'diameter': '63.00', 'nominal_diameter': None, 'wall_thickness': None}])
        if path == '/batches':
            query = parse_qs(urlparse(self.path).query)
            offset, limit = int(query.get('offset', ['0'])[0]), int(query.get('limit', ['25'])[0])
            return self.reply(200, rows[offset:offset + limit])
        if path.startswith('/batches/'):
            try: wanted = int(path.rsplit('/', 1)[1])
            except ValueError: wanted = -1
            found = next((row for row in rows if row['id'] == wanted), None)
            return self.reply(200, found) if found else self.reply(404, {'detail': 'mock missing'})
        return self.reply(404, {'detail': 'mock missing'})

    def do_POST(self):
        global next_id
        data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        requests.append({'method': 'POST', 'path': self.path, 'request_body': data})
        if not isinstance(data.get('variant_id'), int) or data['variant_id'] <= 0:
            return self.reply(422, {'detail': 'invalid mock payload'})
        row = {'id': next_id, **data}; next_id += 1; rows.append(row)
        return self.reply(201, row)

    def do_PATCH(self):
        data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        requests.append({'method': 'PATCH', 'path': self.path, 'request_body': data})
        try: wanted = int(urlparse(self.path).path.rsplit('/', 1)[1])
        except ValueError: wanted = -1
        row = next((item for item in rows if item['id'] == wanted), None)
        if not row: return self.reply(404, {'detail': 'mock missing'})
        if data.get('batch_number') == 'MOCK-422': return self.reply(422, {'detail': 'bounded mock validation error'})
        if wanted == 1: time.sleep(2.0)  # exercise late completion against selection B
        row.update(data)
        return self.reply(200, row)

    def log_message(self, fmt, *args): pass

print('MOCK ONLY: in-memory C2 fixture at 127.0.0.1:8000; seeded rows 1-28; no DB/storage writes', flush=True)
HTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
