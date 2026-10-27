"""Temporary in-memory mock API for the TASK-MVP-05 browser smoke only."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import urlparse, parse_qs

rows = []
next_id = 1
requests = []

class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        if self.path != '/_requests' and requests:
            requests[-1]['status'] = status
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/_requests': return self.reply(200, requests.copy())
        requests.append({'method': 'GET', 'path': self.path})
        if path == '/products': return self.reply(200, [{'id': 1, 'name': 'Труба ПЭ100', 'standard': 'ГОСТ mock', 'manufacturer_id': 1, 'designation': None, 'product_type': None}])
        if path == '/products/1/variants': return self.reply(200, [{'id': 7, 'product_id': 1, 'size_text': '63 мм', 'diameter': '63.00', 'nominal_diameter': None, 'wall_thickness': None}])
        if path == '/batches':
            query = parse_qs(urlparse(self.path).query)
            offset, limit = int(query.get('offset', ['0'])[0]), int(query.get('limit', ['25'])[0])
            return self.reply(200, rows[offset:offset + limit])
        if path.startswith('/batches/'):
            found = next((row for row in rows if row['id'] == int(path.rsplit('/', 1)[1])), None)
            return self.reply(200, found) if found else self.reply(404, {'detail': 'mock missing'})
        return self.reply(404, {'detail': 'mock missing'})

    def do_POST(self):
        global next_id
        data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        requests.append({'method': 'POST', 'path': self.path, 'payload': data})
        row = {'id': next_id, **data}; next_id += 1; rows.append(row)
        return self.reply(201, row)

    def do_PATCH(self):
        data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        requests.append({'method': 'PATCH', 'path': self.path, 'payload': data})
        row = next((item for item in rows if item['id'] == int(urlparse(self.path).path.rsplit('/', 1)[1])), None)
        if not row: return self.reply(404, {'detail': 'mock missing'})
        row.update(data)
        return self.reply(200, row)

    def log_message(self, fmt, *args): pass

print('MOCK ONLY: in-memory API fixture on 127.0.0.1:8000; no DB/storage writes', flush=True)
HTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
