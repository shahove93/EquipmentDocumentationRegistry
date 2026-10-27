"""Production browser surface for the single-computer distribution.

Kept separate from app.main so the development API and its OpenAPI stay intact.
"""
import re
from pathlib import Path

from starlette.responses import FileResponse, PlainTextResponse
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class LocalWeb:
    def __init__(self, api, ui: Path, port: int):
        if not (ui / "index.html").is_file():
            raise RuntimeError("Production frontend is missing")
        self.api = api
        self.ui = ui
        self.origin = f"http://127.0.0.1:{port}"
        self.host = f"127.0.0.1:{port}"
        self.assets = StaticFiles(directory=ui / "assets")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.api(scope, receive, send)
        headers = dict(scope["headers"])
        # Also prevent DNS rebinding and cross-origin form POSTs to an anonymous API.
        if (headers.get(b"host", b"").decode() != self.host
                or headers.get(b"origin", self.origin.encode()).decode() != self.origin
                or headers.get(b"sec-fetch-site") == b"cross-site"):
            return await PlainTextResponse("Local requests only", 403)(scope, receive, send)
        path = scope["path"]
        html = b"text/html" in headers.get(b"accept", b"")
        spa = path in {"/", "/materials", "/batches", "/documents/new"} or re.fullmatch(
            r"/documents/[^/]+/?", path
        )
        if scope["method"] == "GET" and html and spa:
            response = FileResponse(self.ui / "index.html", headers={"Cache-Control": "no-cache"})
            return await response(scope, receive, send)
        if path.startswith("/assets/"):
            asset_scope = dict(scope, path=path[len("/assets"):], root_path="")
            try:
                return await self.assets(asset_scope, receive, send)
            except HTTPException as error:
                return await PlainTextResponse("Asset unavailable", error.status_code)(scope, receive, send)
        return await self.api(scope, receive, send)
