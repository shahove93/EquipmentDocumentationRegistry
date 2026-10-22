import errno
import os
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from app.services.storage import (
    FileAlreadyExistsError,
    StorageBackend,
    StorageError,
    StorageKeyError,
    StoredFileNotFoundError,
)

CHUNK_SIZE = 64 * 1024

_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class StorageInventoryError(StorageError):
    """The storage tree could not be inventoried safely.

    `code` is a fixed machine-readable reason. The message is for developers
    only and is never copied into an external report: it may contain paths.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class StoredFileInfo:
    """Metadata of one regular file found by `iter_files`."""

    storage_key: str
    size_bytes: int
    modified_at: datetime


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

    def iter_files(self, prefix: str) -> Iterator[StoredFileInfo]:
        """Yield metadata for every regular file below a logical prefix.

        The walk is confined to `prefix` under the resolved storage root.
        Symbolic links are never followed and never yielded; directories,
        FIFOs, sockets and device nodes are not yielded either. File contents
        are not opened: only `lstat`-style metadata is read.

        A missing prefix yields nothing, which lets an empty storage or a
        storage without the `documents` namespace be a normal result. A
        missing, unreadable or replaced root is an error, as is a prefix that
        is not a real directory, so that a partial or redirected walk cannot
        be mistaken for an empty one.
        """
        parts = self._prefix_parts(prefix)
        directory_fd = self._open_root()

        try:
            for part in parts:
                child_fd = self._open_prefix_directory(directory_fd, part)
                if child_fd is None:
                    return
                os.close(directory_fd)
                directory_fd = child_fd

            yield from self._walk_directory(directory_fd, parts)
        finally:
            os.close(directory_fd)

    @staticmethod
    def _prefix_parts(prefix: str) -> tuple[str, ...]:
        if not isinstance(prefix, str):
            raise StorageInventoryError(
                "storage_prefix_invalid", "storage prefix must be a string"
            )

        key = prefix.rstrip("/")
        if not key or "\x00" in key or key != key.strip():
            raise StorageInventoryError(
                "storage_prefix_invalid", "storage prefix must be a non-empty key"
            )
        if key.startswith(("/", "\\")) or "\\" in key or ":" in key:
            raise StorageInventoryError(
                "storage_prefix_invalid", "storage prefix must be a relative POSIX key"
            )

        candidate = PurePosixPath(key)
        if (
            candidate.is_absolute()
            or not candidate.parts
            or str(candidate) != key
            or any(part in ("", ".", "..") for part in candidate.parts)
        ):
            raise StorageInventoryError(
                "storage_prefix_invalid", "storage prefix must be a plain relative key"
            )
        return candidate.parts

    def _open_root(self) -> int:
        try:
            root_stat = os.stat(self._root, follow_symlinks=False)
        except FileNotFoundError:
            raise StorageInventoryError(
                "storage_root_missing", "storage root does not exist"
            ) from None
        except PermissionError:
            raise StorageInventoryError(
                "storage_unreadable", "storage root is not readable"
            ) from None
        except OSError:
            raise StorageInventoryError(
                "storage_root_unreadable", "storage root cannot be inspected"
            ) from None

        if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
            raise StorageInventoryError(
                "storage_root_not_directory",
                "storage root is not a real directory",
            )

        try:
            return os.open(self._root, _DIRECTORY_FLAGS | _NOFOLLOW)
        except FileNotFoundError:
            raise StorageInventoryError(
                "storage_root_missing", "storage root does not exist"
            ) from None
        except PermissionError:
            raise StorageInventoryError(
                "storage_unreadable", "storage root is not readable"
            ) from None
        except OSError:
            raise StorageInventoryError(
                "storage_root_unreadable", "storage root cannot be opened"
            ) from None

    def _open_prefix_directory(self, parent_fd: int, name: str) -> int | None:
        """Open one prefix component; `None` means the prefix does not exist."""
        try:
            entry_stat = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        except PermissionError:
            raise StorageInventoryError(
                "storage_unreadable", "storage prefix is not readable"
            ) from None
        except OSError:
            raise StorageInventoryError(
                "storage_stat_failed", "storage prefix cannot be inspected"
            ) from None

        if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISDIR(entry_stat.st_mode):
            raise StorageInventoryError(
                "storage_namespace_not_directory",
                "storage prefix is not a real directory",
            )

        try:
            return os.open(name, _DIRECTORY_FLAGS | _NOFOLLOW, dir_fd=parent_fd)
        except FileNotFoundError:
            raise StorageInventoryError(
                "storage_entry_vanished", "storage prefix disappeared"
            ) from None
        except PermissionError:
            raise StorageInventoryError(
                "storage_unreadable", "storage prefix is not readable"
            ) from None
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise StorageInventoryError(
                    "storage_namespace_not_directory",
                    "storage prefix is not a real directory",
                ) from None
            raise StorageInventoryError(
                "storage_unreadable", "storage prefix cannot be opened"
            ) from None

    def _walk_directory(
        self, directory_fd: int, prefix_parts: tuple[str, ...]
    ) -> Iterator[StoredFileInfo]:
        try:
            names = sorted(os.listdir(directory_fd))
        except PermissionError:
            raise StorageInventoryError(
                "storage_unreadable", "a storage directory is not readable"
            ) from None
        except OSError:
            raise StorageInventoryError(
                "storage_walk_failed", "a storage directory cannot be listed"
            ) from None

        prefix = "/".join(prefix_parts)

        for name in names:
            try:
                entry_stat = os.stat(
                    name, dir_fd=directory_fd, follow_symlinks=False
                )
            except FileNotFoundError:
                raise StorageInventoryError(
                    "storage_entry_vanished", "a storage entry disappeared"
                ) from None
            except PermissionError:
                raise StorageInventoryError(
                    "storage_unreadable", "a storage entry is not readable"
                ) from None
            except OSError:
                raise StorageInventoryError(
                    "storage_stat_failed", "a storage entry cannot be inspected"
                ) from None

            mode = entry_stat.st_mode
            if stat.S_ISLNK(mode):
                continue

            storage_key = f"{prefix}/{name}"

            if stat.S_ISDIR(mode):
                child_fd = self._open_nested_directory(directory_fd, name)
                try:
                    yield from self._walk_directory(
                        child_fd, (*prefix_parts, name)
                    )
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(mode):
                yield StoredFileInfo(
                    storage_key=storage_key,
                    size_bytes=entry_stat.st_size,
                    modified_at=datetime.fromtimestamp(
                        entry_stat.st_mtime, tz=timezone.utc
                    ),
                )

    @staticmethod
    def _open_nested_directory(parent_fd: int, name: str) -> int:
        try:
            return os.open(name, _DIRECTORY_FLAGS | _NOFOLLOW, dir_fd=parent_fd)
        except FileNotFoundError:
            raise StorageInventoryError(
                "storage_entry_vanished", "a storage directory disappeared"
            ) from None
        except PermissionError:
            raise StorageInventoryError(
                "storage_unreadable", "a storage directory is not readable"
            ) from None
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise StorageInventoryError(
                    "storage_not_directory",
                    "a storage entry is no longer a real directory",
                ) from None
            raise StorageInventoryError(
                "storage_unreadable", "a storage directory cannot be opened"
            ) from None