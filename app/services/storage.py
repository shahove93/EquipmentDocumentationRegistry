from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageError(Exception):
    """Base error for storage backend operations."""


class StorageKeyError(StorageError):
    """Storage key is empty, malformed or attempts to escape the storage root."""


class FileAlreadyExistsError(StorageError):
    """A file with the given storage key is already present in storage."""


class StoredFileNotFoundError(StorageError):
    """No file exists for the given storage key."""


class StorageBackend(ABC):
    """Logical key-addressed storage interface.

    The backend knows nothing about documents, database rows or file metadata:
    it only maps a logical string key to a stored binary blob.
    """

    @abstractmethod
    def save(self, storage_key: str, source: BinaryIO) -> None:
        """Stream `source` into storage under `storage_key`.

        Raises FileAlreadyExistsError if the key is already taken.
        """

    @abstractmethod
    def open(self, storage_key: str) -> BinaryIO:
        """Return a readable binary stream for an existing key.

        Raises StoredFileNotFoundError if the key is unknown.
        """

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """Return whether a file is stored under `storage_key`."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Remove the stored file; missing files are ignored."""