"""Command-line entry point for the report-only storage reconciliation.

Run from the repository root as `python -m app.reconcile_storage`. The command
prints one JSON object to stdout and uses the existing Settings values for the
database, the storage root and the journal path. It never deletes anything,
never changes the database or the journal and never starts a scheduler.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import create_engine

from app.config import Settings
from app.services.local_storage import LocalStorageBackend
from app.services.storage_reconciliation import (
    failure_report,
    reconcile_storage,
)


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m app.reconcile_storage",
        description=(
            "Report-only reconciliation of blobs under STORAGE_ROOT/documents "
            "against files.storage_key. Deletes nothing and changes nothing."
        ),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(report: dict, exit_code: int) -> int:
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()

    if report.get("status") == "failed":
        error = report.get("error") or {}
        sys.stderr.write(
            "reconciliation failed: "
            f"{error.get('code', 'internal_error')} "
            f"({error.get('stage', 'report')})\n"
        )
        sys.stderr.flush()

    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    try:
        parser.parse_args(argv)
    except SystemExit as exit_error:
        return int(exit_error.code or 0)

    started_at = _utc_now()
    engine = None

    try:
        settings = Settings()
        engine = create_engine(settings.DATABASE_URL, future=True)
        storage = LocalStorageBackend(root_path=settings.STORAGE_ROOT)
        report = reconcile_storage(engine, storage, log_file=settings.LOG_FILE)
    except Exception as error:  # noqa: BLE001 - safe failure report only
        report = failure_report(
            started_at=started_at,
            finished_at=_utc_now(),
            code="configuration_error",
            stage="configuration",
            error_type=type(error).__name__,
        )
    finally:
        if engine is not None:
            engine.dispose()

    exit_code = 1 if report.get("status") == "failed" else 0
    return _emit(report, exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
