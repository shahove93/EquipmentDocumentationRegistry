"""Helpers for streaming a stored attachment to the client.

Three concerns belong here rather than in the router: turning a filename the
client chose at upload time into a header value that cannot break the response,
copying a blob into a verified snapshot before any status code is committed to,
and walking that snapshot in bounded chunks so the body never has to be held in
memory.
"""

import hashlib
import logging
import tempfile
from collections.abc import Iterator, Mapping
from typing import BinaryIO
from urllib.parse import quote

from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

logger = logging.getLogger(__name__)

# What the client sees when nothing usable is left of the stored name. Uploads
# refuse empty names, so this only covers a row written by something other than
# FileService.
DEFAULT_FILENAME = "download"

# The same chunk size the upload path uses, so a download moves a comparable
# amount of data per read.
CHUNK_SIZE = 64 * 1024

# Fixed text: the message describes the category of failure and nothing about
# the row, the digest or the storage key, so it is safe as an error `__cause__`
# and as the logger's fixed message.
DOWNLOAD_INTEGRITY_MESSAGE = "stored file content does not match its recorded digest"


class DownloadIntegrityError(Exception):
    """A blob's bytes do not match the SHA-256 recorded for its row.

    The failure is a server-side integrity problem, not a client error. It is
    raised before the response is constructed, while a status code can still be
    chosen, so the router can answer with the same safe `500` it uses for an
    unavailable store.
    """

    def __init__(self) -> None:
        super().__init__(DOWNLOAD_INTEGRITY_MESSAGE)


def prepare_verified_download(source: BinaryIO, expected_sha256: str) -> BinaryIO:
    """Copy `source` to a temporary file and return the verified copy.

    The helper takes ownership of `source` immediately: it closes the stream on
    success and on every failure, so the caller must not use it afterwards.

    The copy is made in `CHUNK_SIZE` pieces while the same pieces are fed to a
    SHA-256 digest. The digest is compared with `expected_sha256` after the
    whole stream has been read and before the copy is rewound for sending. A
    mismatch raises `DownloadIntegrityError`; any other read, write, flush or
    rewind failure propagates unchanged. In every failure case the temporary
    file is closed as well, and on success ownership of the copy passes to the
    caller.

    Copying first is what makes the served bytes the checked bytes: the inode
    may be replaced or truncated after the check, but the response reads the
    private snapshot rather than the storage file.
    """
    snapshot: BinaryIO | None = None
    try:
        digest = hashlib.sha256()
        snapshot = tempfile.TemporaryFile(mode="w+b")
        while chunk := source.read(CHUNK_SIZE):
            digest.update(chunk)
            snapshot.write(chunk)
        snapshot.flush()
        if digest.hexdigest() != expected_sha256:
            raise DownloadIntegrityError()
        snapshot.seek(0)
        return snapshot
    except BaseException:
        if snapshot is not None:
            snapshot.close()
        raise
    finally:
        source.close()


def content_disposition(filename: str) -> str:
    """Build a safe `Content-Disposition` value for `filename`.

    RFC 6266 gives the header two names. `filename` is the ASCII form any client
    can read; `filename*` carries the real name in RFC 5987 form. A Cyrillic
    name therefore degrades to `????????.pdf` in the first and arrives intact in
    the second, instead of arriving broken in both.

    A header is injected through a control character and in no other way, so
    control characters are removed before either form is built. Both forms are
    pure ASCII, which is also what Starlette needs: it encodes header values as
    latin-1, and a Cyrillic character there would raise instead of answering.

    Path separators are separators, not part of the name, so `../../etc/passwd`
    becomes `passwd`. Quotes and spaces are legitimate inside a quoted-string:
    the quotes are backslash-escaped in `filename` and percent-encoded in
    `filename*`, so both forms stay valid.
    """
    name = _safe_basename(filename)
    ascii_name = name.encode("ascii", "replace").decode("ascii")
    quoted = ascii_name.replace("\\", "\\\\").replace('"', '\\"')
    encoded = quote(name, safe="")
    return f"attachment; filename=\"{quoted}\"; filename*=UTF-8''{encoded}"


def _safe_basename(filename: str) -> str:
    """Reduce `filename` to a printable name with no path separators.

    Both `/` and `\\` count as separators because the name may have come from a
    Windows client, where the second is the ordinary one.

    `str.isprintable()` is the control-character filter: it is false for CR, LF,
    NUL, DEL and the C1 range, so none of them can reach the header in either
    form. It is also false for a few invisible formatting characters, which is
    harmless here.
    """
    if not isinstance(filename, str):
        return DEFAULT_FILENAME
    candidate = filename.replace("\\", "/").rsplit("/", 1)[-1]
    candidate = "".join(
        character for character in candidate if character.isprintable()
    )
    candidate = candidate.strip()
    if not candidate or candidate in {".", ".."}:
        return DEFAULT_FILENAME
    return candidate


class ClosingStreamingResponse(StreamingResponse):
    """A streaming response that closes its source however the response ends.

    Starlette drives a synchronous iterator through `iterate_in_threadpool`,
    which never calls `close()` on it. A full read exhausts the generator and
    `iter_blob` closes the file on the way out, but a disconnect or a cancelled
    request abandons it mid-iteration: the headers are already gone, nobody
    closes the iterator, and the descriptor survives until the garbage collector
    reaches it. That is precisely the case streaming is meant to handle cheaply,
    and it is the case a `TestClient` cannot show, because reading the whole
    response always takes the normal path.

    Starlette offers no hook for it. A `background` task would run on a normal
    finish and on an ASGI 2.0 disconnect, but is skipped when a 2.4 disconnect
    raises `ClientDisconnect`, and the iterator is left suspended on either
    path. Wrapping the ASGI call is therefore the smallest place that sees every
    exit: `finally` runs on a finished response, on an exception from `send`
    and on task cancellation, so release belongs to the request rather than to
    collection.

    The source is closed here and again by `iter_blob` on a normal read; both
    closes are idempotent for a binary stream, and the second one guarantees the
    helper is still correct on its own.
    """

    def __init__(
        self,
        source: BinaryIO,
        *,
        status_code: int = 200,
        media_type: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        # `status_code` is not passed by the router, but FastAPI reads it from
        # `__init__` when it builds the OpenAPI response for a route that does
        # not declare one. Omitting it makes that introspection fail with an
        # unbound name rather than defaulting to 200.
        self._source = source
        try:
            super().__init__(
                iter_blob(source),
                status_code=status_code,
                media_type=media_type,
                headers=headers,
            )
        except BaseException:
            # Starlette encodes the headers inside `__init__`, so a value it
            # cannot encode fails before the response exists. The router has
            # already handed the verified snapshot over; closing it here keeps
            # the failed construction from leaking the descriptor.
            source.close()
            raise

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._source.close()


def iter_blob(source: BinaryIO, chunk_size: int = CHUNK_SIZE) -> Iterator[bytes]:
    """Yield `source` in bounded chunks and close it when iteration ends.

    Reading without a size would pull the whole file into memory, which is what
    streaming exists to avoid. The `finally` closes the descriptor when the loop
    ends and when `read` raises, so a caller cannot leak it by exhausting the
    generator or by hitting a read error.

    A read failure after the response has started can no longer become a status
    code or a JSON body, so it is logged once in a fixed, safe form and
    re-raised. Only the error type is recorded; the message may contain paths
    and is deliberately not written.

    A disconnect abandons the generator instead of exhausting it, and this block
    is not reached until the abandoned generator is collected. That case is
    covered in front of the iterator: `ClosingStreamingResponse` closes the same
    source in the `finally` of the ASGI call, which runs on disconnect and on
    cancellation too.
    """
    try:
        while chunk := source.read(chunk_size):
            yield chunk
    except Exception as error:
        logger.error(
            "a verified download could not be streamed to the client",
            extra={
                "operation": "file.download",
                "failure_category": "content_stream_failed",
                "error_type": type(error).__name__,
            },
        )
        raise
    finally:
        source.close()
