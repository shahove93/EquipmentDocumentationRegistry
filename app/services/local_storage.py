from pathlib import Path, PurePosixPath
from typing import BinaryIO

from app.services.storage import (
    FileAlreadyExistsError,
    StorageBackend,
    StorageKeyError,
    StoredFileNotFoundError,
)

CHUNK_SIZE = 64 * 1024


class LocalStorageBackend(StorageBackend):
    """Store binary blobs on the local filesystem under a single root directory."""

    def __init__(self, root_path: str | Path = "storage") -> None:
        self._root = Path(root_path).resolve()

    @property
    def root_path(self) -> Path:
        return self._root

    @staticmethod
    def _looks_like_windows_path(key: str) -> bool:
        return "\\" in key or ":" in key

    def _resolve(self, storage_key: str) -> Path:
        if not isinstance(storage_key, str) or not storage_key.strip():
            raise StorageKeyError("storage_key must be a non-empty string")

        key = storage_key.strip()
        if "\x00" in key:
            raise StorageKeyError("storage_key must not contain null bytes")

        candidate = PurePosixPath(key)
        if key.startswith(("/", "\\")) or candidate.is_absolute():
            raise StorageKeyError(f"storage_key must be relative: {storage_key!r}")
        if self._looks_like_windows_path(key):
            raise StorageKeyError(
                f"storage_key must use POSIX separators and no drive letters: {storage_key!r}"
            )
        if any(part == ".." for part in candidate.parts):
            raise StorageKeyError(
                f"storage_key must not escape the storage root: {storage_key!r}"
            )
        if not candidate.parts or candidate.name in ("", ".", ".."):
            raise StorageKeyError(f"storage_key must point to a file: {storage_key!r}")

        target = (self._root / Path(*candidate.parts)).resolve()
        if target != self._root and self._root not in target.parents:
            raise StorageKeyError(
                f"storage_key escapes the storage root: {storage_key!r}"
            )
        return target

    def save(self, storage_key: str, source: BinaryIO) -> None:
        target = self._resolve(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            handle = target.open("xb")
        except FileExistsError as error:
            raise FileAlreadyExistsError(
                f"storage_key already exists: {storage_key!r}"
            ) from error

        try:
            with handle:
                while chunk := source.read(CHUNK_SIZE):
                    handle.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def open(self, storage_key: str) -> BinaryIO:
        target = self._resolve(storage_key)
        if not target.is_file():
            raise StoredFileNotFoundError(
                f"no stored file for storage_key: {storage_key!r}"
            )
        return target.open("rb")

    def exists(self, storage_key: str) -> bool:
        return self._resolve(storage_key).is_file()

    def delete(self, storage_key: str) -> None:
        self._resolve(storage_key).unlink(missing_ok=True)