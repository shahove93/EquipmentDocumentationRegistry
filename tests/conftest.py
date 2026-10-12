import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.models.base import Base
from app.services.local_storage import LocalStorageBackend

TEST_DATABASE_URL = os.environ.get(
    "EDR_TEST_DATABASE_URL",
    "postgresql+psycopg://edr@127.0.0.1:5432/postgres",
)


def _database_url() -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv(".env")
    except ImportError:
        pass
    return os.environ.get("DATABASE_URL") or TEST_DATABASE_URL


@pytest.fixture
def engine():
    """Throwaway engine against a scratch schema; nothing persists."""
    url = _database_url()
    schema = "test_file_service"

    # Preparation engine is short-lived: NullPool closes each connection as soon
    # as it is returned, and the try/finally guarantees release even on error.
    preparation_engine = create_engine(url, poolclass=NullPool, future=True)
    try:
        with preparation_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    finally:
        preparation_engine.dispose()

    test_engine = create_engine(
        url, poolclass=NullPool, future=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        Base.metadata.create_all(test_engine)

        yield test_engine
    finally:
        test_engine.dispose()
        cleanup = create_engine(url, poolclass=NullPool, future=True)
        try:
            with cleanup.begin() as connection:
                connection.exec_driver_sql(
                    f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'
                )
        finally:
            cleanup.dispose()


@pytest.fixture
def db(engine) -> Session:
    session = Session(engine, future=True)
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def storage(tmp_path):
    return LocalStorageBackend(root_path=tmp_path / "storage")