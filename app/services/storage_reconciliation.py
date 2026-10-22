"""Report-only reconciliation of document blobs against the `files` table.

The scan is deliberately one-way: it reads file metadata and database keys,
then reports blob keys that have no `files.storage_key` row. It never deletes,
renames, truncates or rewrites anything, and it never reads blob contents.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from os import PathLike
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, select

from app.models.file import File
from app.services.local_storage import (
    LocalStorageBackend,
    StorageInventoryError,
    StoredFileInfo,
)

SCHEMA_VERSION = 1
MODE = "report_only"
SCOPE = "documents"

CANONICAL_BLOB_PATTERN = re.compile(
    r"documents/(?:0|[1-9][0-9]*)/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"\.(?:pdf|jpg|png)"
)

_ERROR_FOR_PHASE = {
    "configuration": ("configuration_error", "configuration"),
    "inventory": ("storage_walk_failed", "inventory"),
    "database": ("database_error", "database"),
    "report": ("internal_error", "report"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_canonical_storage_key(storage_key: str) -> bool:
    """Whether `storage_key` is exactly one canonical document blob key."""
    return isinstance(storage_key, str) and (
        CANONICAL_BLOB_PATTERN.fullmatch(storage_key) is not None
    )


def failure_report(
    *,
    started_at: str,
    finished_at: str,
    code: str,
    stage: str,
    error_type: str,
) -> dict[str, Any]:
    """Build the fixed failure shape without copying exception text."""
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "scope": SCOPE,
        "status": "failed",
        "complete": False,
        "started_at": started_at,
        "finished_at": finished_at,
        "summary": None,
        "orphans": None,
        "error": {
            "code": code,
            "stage": stage,
            "type": error_type,
        },
    }


def reconcile_storage(
    engine: Engine,
    storage: LocalStorageBackend,
    *,
    log_file: str | PathLike[str],
) -> dict[str, Any]:
    """Scan document blobs and return a report about unmatched ones.

    The filesystem inventory is completed before the database is contacted.
    The database is then read once, in its own connection, with a single
    `SELECT files.storage_key`; no row is changed and no lock is taken.
    """
    started_at = _utc_now()
    phase = "configuration"

    try:
        log_path = Path(log_file).expanduser().resolve()
        phase = "inventory"
        inventory = _collect_inventory(storage, log_path)
        phase = "database"
        stored_keys = _read_stored_keys(engine)
        phase = "report"
        return _success_report(started_at, inventory, stored_keys)
    except StorageInventoryError as error:
        return failure_report(
            started_at=started_at,
            finished_at=_utc_now(),
            code=error.code,
            stage="inventory",
            error_type=type(error).__name__,
        )
    except Exception as error:  # noqa: BLE001 - the report owns safe failures
        code, stage = _ERROR_FOR_PHASE[phase]
        return failure_report(
            started_at=started_at,
            finished_at=_utc_now(),
            code=code,
            stage=stage,
            error_type=type(error).__name__,
        )


def _collect_inventory(
    storage: LocalStorageBackend, log_path: Path
) -> list[StoredFileInfo]:
    inventory: list[StoredFileInfo] = []

    for info in storage.iter_files(SCOPE):
        candidate = storage.root_path.joinpath(*info.storage_key.split("/"))
        if candidate == log_path:
            continue
        inventory.append(info)

    return inventory


def _read_stored_keys(engine: Engine) -> set[str]:
    with engine.connect() as connection:
        result = connection.execute(select(File.storage_key))
        return {row[0] for row in result}


def _success_report(
    started_at: str,
    inventory: list[StoredFileInfo],
    stored_keys: set[str],
) -> dict[str, Any]:
    matched_blobs = 0
    ignored_regular_files = 0
    orphans: list[dict[str, Any]] = []

    for info in inventory:
        if not is_canonical_storage_key(info.storage_key):
            ignored_regular_files += 1
            continue

        if info.storage_key in stored_keys:
            matched_blobs += 1
            continue

        orphans.append(
            {
                "storage_key": info.storage_key,
                "size_bytes": info.size_bytes,
                "modified_at": info.modified_at.isoformat(),
            }
        )

    orphans.sort(key=lambda orphan: orphan["storage_key"])

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "scope": SCOPE,
        "status": "ok",
        "complete": True,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "summary": {
            "scanned_blobs": matched_blobs + len(orphans),
            "matched_blobs": matched_blobs,
            "orphan_count": len(orphans),
            "orphan_bytes": sum(orphan["size_bytes"] for orphan in orphans),
            "ignored_regular_files": ignored_regular_files,
        },
        "orphans": orphans,
    }
