"""Migration and database tests for `ix_files_document_id_id`.

Every Alembic run here happens in a unique throwaway PostgreSQL schema through a
child process whose `DATABASE_URL` and `PGOPTIONS` point at that schema. Nothing
is applied to `public`: the checks read its Alembic version and file count
before and after, and the teardown drops only the schema this module created.

The migration is exercised in both directions — upgrade to the previous head,
seed data, upgrade to head, downgrade, upgrade again — and the live catalog,
the list query, the cascade and the access plan are checked against the real
index rather than the model alone.
"""

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from app.models import Base

REVISION = "e4b8c2d16a70"
PREVIOUS = "a3f1c72d5b90"
INDEX_NAME = "ix_files_document_id_id"
REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"

INDEX_CATALOG = text(
    """
    SELECT
        i.indisunique,
        i.indisvalid,
        i.indpred IS NULL AS no_predicate,
        i.indexprs IS NULL AS no_expressions,
        am.amname,
        pg_get_indexdef(i.indexrelid) AS definition
    FROM pg_index AS i
    JOIN pg_class AS c ON c.oid = i.indexrelid
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    JOIN pg_am AS am ON am.oid = c.relam
    WHERE n.nspname = :schema AND c.relname = :index_name
    """
)

INDEX_COLUMNS = text(
    """
    SELECT a.attname
    FROM pg_index AS i
    JOIN pg_class AS c ON c.oid = i.indexrelid
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    JOIN unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
    JOIN pg_attribute AS a
      ON a.attrelid = i.indrelid AND a.attnum = k.attnum
    WHERE n.nspname = :schema AND c.relname = :index_name
    ORDER BY k.ord
    """
)


def _database_url() -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    return os.environ.get("DATABASE_URL") or TEST_DATABASE_URL


def _redact(value: str, url: str) -> str:
    """Remove the database URL from text that may end up in a failure message."""
    redacted = value.replace(url, "<database-url>")
    if "://" in redacted and "@" in redacted:
        scheme, rest = redacted.split("://", 1)
        if "@" in rest:
            redacted = f"{scheme}://<credentials>@{rest.rsplit('@', 1)[1]}"
    return redacted


def run_alembic(schema: str, url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = url
    environment["PGOPTIONS"] = f"-csearch_path={schema}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(arguments)} failed in {schema}: "
        f"{_redact(result.stderr, url)}"
    )


def schema_engine(schema: str, url: str) -> Engine:
    return create_engine(
        url,
        poolclass=NullPool,
        connect_args={"options": f"-csearch_path={schema}"},
    )


def alembic_version(connection) -> str | None:
    return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()


def index_row(connection, schema: str):
    return connection.execute(
        INDEX_CATALOG, {"schema": schema, "index_name": INDEX_NAME}
    ).one_or_none()


def index_columns(connection, schema: str) -> list[str]:
    return list(
        connection.execute(
            INDEX_COLUMNS, {"schema": schema, "index_name": INDEX_NAME}
        ).scalars()
    )


def indexes_on_files(connection, schema: str) -> list[str]:
    return list(
        connection.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = :schema AND tablename = 'files' "
                "ORDER BY indexname"
            ),
            {"schema": schema},
        ).scalars()
    )


def constraints_on_files(connection, schema: str) -> dict[str, str]:
    rows = connection.execute(
        text(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = to_regclass(:relation)"
        ),
        {"relation": f"{schema}.files"},
    )
    return {name: definition for name, definition in rows}


def public_snapshot(url: str) -> tuple[str | None, int | None]:
    admin = create_engine(url, poolclass=NullPool)
    try:
        with admin.connect() as connection:
            version = None
            if connection.execute(
                text("SELECT to_regclass('public.alembic_version')")
            ).scalar() is not None:
                version = connection.execute(
                    text("SELECT version_num FROM public.alembic_version")
                ).scalar()
            files = None
            if connection.execute(
                text("SELECT to_regclass('public.files')")
            ).scalar() is not None:
                files = connection.execute(
                    text("SELECT count(*) FROM public.files")
                ).scalar()
            return version, files
    finally:
        admin.dispose()


def seed(connection) -> tuple[int, int, list[int]]:
    target_type = connection.execute(
        text(
            "INSERT INTO document_types (name) VALUES (:name) RETURNING id"
        ),
        {"name": "Type MVP-03"},
    ).scalar_one()
    target_document = connection.execute(
        text(
            "INSERT INTO documents (document_type_id, number) "
            "VALUES (:type_id, :number) RETURNING id"
        ),
        {"type_id": target_type, "number": "MVP-03-A"},
    ).scalar_one()
    neighbour_document = connection.execute(
        text(
            "INSERT INTO documents (document_type_id, number) "
            "VALUES (:type_id, :number) RETURNING id"
        ),
        {"type_id": target_type, "number": "MVP-03-B"},
    ).scalar_one()
    uploaded_at = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    rows = [
        (target_document, "a.pdf", "documents/mvp03/a", 10),
        (target_document, "b.pdf", "documents/mvp03/b", 20),
        (neighbour_document, "c.pdf", "documents/mvp03/c", 30),
    ]
    file_ids = []
    for document_id, filename, key, size in rows:
        file_ids.append(
            connection.execute(
                text(
                    "INSERT INTO files (document_id, original_filename, "
                    "storage_key, mime_type, size_bytes, sha256, uploaded_at) "
                    "VALUES (:document_id, :filename, :key, 'application/pdf', "
                    ":size, :sha256, :uploaded_at) RETURNING id"
                ),
                {
                    "document_id": document_id,
                    "filename": filename,
                    "key": key,
                    "size": size,
                    "sha256": "a" * 64,
                    "uploaded_at": uploaded_at,
                },
            ).scalar_one()
        )
    return target_document, neighbour_document, file_ids


def file_rows(connection, schema: str) -> list[tuple]:
    return [
        tuple(row)
        for row in connection.execute(
            text(
                "SELECT id, document_id, original_filename, storage_key, "
                "mime_type, size_bytes, sha256, uploaded_at "
                f'FROM "{schema}".files ORDER BY id'
            )
        )
    ]


def plan_nodes(plan: dict):
    node = plan["Plan"]
    yield node
    for child in node.get("Plans", []):
        yield from plan_nodes({"Plan": child})


def load_plan(connection, document_id: int) -> dict:
    connection.execute(text("ANALYZE files"))
    raw = connection.execute(
        text(
            "EXPLAIN (FORMAT JSON) "
            "SELECT id FROM files WHERE document_id = :document_id ORDER BY id"
        ),
        {"document_id": document_id},
    ).scalar()
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    return parsed[0] if isinstance(parsed, list) else parsed


@pytest.fixture
def migration_schema():
    url = _database_url()
    schema = f"test_mvp03_{uuid.uuid4().hex[:12]}"
    admin = create_engine(url, poolclass=NullPool)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield schema, url
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def test_upgrade_downgrade_up_creates_only_the_index(migration_schema):
    schema, url = migration_schema
    public_before = public_snapshot(url)

    run_alembic(schema, url, "upgrade", PREVIOUS)
    engine = schema_engine(schema, url)
    try:
        with engine.begin() as connection:
            assert alembic_version(connection) == PREVIOUS
            before = file_rows(connection, schema)
            assert before == []
            target_document, neighbour_document, file_ids = seed(connection)
            expected_rows = file_rows(connection, schema)
            assert len(expected_rows) == 3
            constraints_before = constraints_on_files(connection, schema)
            indexes_before = indexes_on_files(connection, schema)
            assert INDEX_NAME not in indexes_before

        run_alembic(schema, url, "upgrade", "head")
        with engine.begin() as connection:
            assert alembic_version(connection) == REVISION
            assert file_rows(connection, schema) == expected_rows
            assert constraints_on_files(connection, schema) == constraints_before
            row = index_row(connection, schema)
            assert row is not None
            unique, valid, no_predicate, no_expressions, method, definition = row
            assert unique is False
            assert valid is True
            assert no_predicate is True
            assert no_expressions is True
            assert method == "btree"
            assert "USING btree (document_id, id)" in definition
            assert "UNIQUE" not in definition
            assert index_columns(connection, schema) == ["document_id", "id"]
            assert indexes_on_files(connection, schema) == sorted(
                [*indexes_before, INDEX_NAME]
            )

        run_alembic(schema, url, "downgrade", PREVIOUS)
        with engine.begin() as connection:
            assert alembic_version(connection) == PREVIOUS
            assert file_rows(connection, schema) == expected_rows
            assert constraints_on_files(connection, schema) == constraints_before
            assert index_row(connection, schema) is None
            assert indexes_on_files(connection, schema) == indexes_before

        run_alembic(schema, url, "upgrade", "head")
        with engine.begin() as connection:
            assert alembic_version(connection) == REVISION
            assert file_rows(connection, schema) == expected_rows
            assert index_row(connection, schema) is not None

            files_table = Base.metadata.tables["files"]
            listed = connection.execute(
                select(files_table)
                .where(files_table.c.document_id == target_document)
                .order_by(files_table.c.id)
            ).all()
            listed_documents = {row.document_id for row in listed}
            assert listed_documents == {target_document}
            assert [row.id for row in listed] == [file_ids[0], file_ids[1]]
            assert neighbour_document not in listed_documents

            connection.execute(
                text("SET LOCAL enable_seqscan = off")
            )
            connection.execute(
                text("SET LOCAL enable_bitmapscan = off")
            )
            plan = load_plan(connection, target_document)
            nodes = list(plan_nodes(plan))
            kinds = [node["Node Type"] for node in nodes]
            assert "Sort" not in kinds
            index_scans = [
                node
                for node in nodes
                if node["Node Type"] in {"Index Scan", "Index Only Scan"}
            ]
            assert index_scans
            assert index_scans[0]["Index Name"] == INDEX_NAME

            connection.execute(
                text("DELETE FROM documents WHERE id = :document_id"),
                {"document_id": target_document},
            )
            assert file_rows(connection, schema) == [
                row for row in expected_rows
                if row[1] == neighbour_document
            ]
            remaining = connection.execute(
                text("SELECT count(*) FROM files WHERE document_id = :id"),
                {"id": neighbour_document},
            ).scalar()
            assert remaining == 1
    finally:
        engine.dispose()

    assert public_snapshot(url) == public_before


def test_create_all_creates_one_valid_nonunique_btree(engine):
    with engine.connect() as connection:
        schema = connection.execute(text("SELECT current_schema()")).scalar()
    inspector = inspect(engine)
    indexes = {index["name"]: index for index in inspector.get_indexes("files")}
    index = indexes[INDEX_NAME]
    assert index["column_names"] == ["document_id", "id"]
    assert index["unique"] is False

    with engine.connect() as connection:
        row = index_row(connection, schema)
        assert row is not None
        unique, valid, no_predicate, no_expressions, method, _ = row
        assert unique is False
        assert valid is True
        assert no_predicate is True
        assert no_expressions is True
        assert method == "btree"
        assert index_columns(connection, schema) == ["document_id", "id"]
