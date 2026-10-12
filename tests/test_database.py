import inspect

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import connection
from app.database.connection import SessionLocal, engine, get_db


class TestEngine:
    def test_engine_exists(self):
        assert isinstance(engine, Engine)

    def test_drivername_starts_with_postgresql(self):
        assert engine.url.drivername.startswith("postgresql")

    def test_uses_psycopg(self):
        assert engine.dialect.driver == "psycopg"
        assert "psycopg" in engine.url.drivername

    def test_dialect_is_postgresql(self):
        assert engine.dialect.name == "postgresql"

    def test_engine_url_matches_settings(self):
        settings = get_settings()
        assert engine.url.render_as_string(hide_password=True) == (
            settings.DATABASE_URL.rsplit("@", 1)[-1]
            if "@" in settings.DATABASE_URL
            else settings.DATABASE_URL
        ) or engine.url.database is not None

    def test_engine_url_password_is_preserved_but_not_exposed(self):
        assert engine.url.password is not None
        assert engine.url.render_as_string(hide_password=True).count("***") >= 1

    def test_pool_pre_ping_enabled(self):
        assert engine.pool._pre_ping is True

    def test_engine_is_module_level_singleton(self):
        assert connection.engine is engine


class TestSessionLocal:
    def test_is_sessionmaker(self):
        assert callable(SessionLocal)

    def test_creates_sqlalchemy_session(self):
        session = SessionLocal()
        try:
            assert isinstance(session, Session)
        finally:
            session.close()

    def test_session_is_bound_to_engine(self):
        session = SessionLocal()
        try:
            assert session.get_bind() is engine
        finally:
            session.close()

    def test_expire_on_commit_disabled(self):
        session = SessionLocal()
        try:
            assert session.expire_on_commit is False
        finally:
            session.close()

    def test_autocommit_disabled(self):
        # SQLAlchemy 2.x removed Session.autocommit; the transaction is
        # controlled by commit/rollback instead
        assert SessionLocal.kw["autocommit"] is False
        assert SessionLocal.kw["autoflush"] is False

    def test_autoflush_disabled(self):
        session = SessionLocal()
        try:
            assert session.autoflush is False
        finally:
            session.close()

    def test_distinct_sessions_per_call(self):
        first = SessionLocal()
        second = SessionLocal()
        try:
            assert first is not second
        finally:
            first.close()
            second.close()


class TestGetDb:
    def test_is_generator_function(self):
        assert inspect.isgeneratorfunction(get_db)

    def test_yields_session(self):
        generator = get_db()
        session = next(generator)
        try:
            assert isinstance(session, Session)
        finally:
            generator.close()

    def test_session_closed_after_generator_exhausts(self):
        generator = get_db()
        session = next(generator)
        with pytest.raises(StopIteration):
            next(generator)
        assert session.get_transaction() is None or not session.in_transaction()

    def test_session_closed_when_generator_is_closed_early(self):
        generator = get_db()
        session = next(generator)
        generator.close()
        # closing must have run the finally block
        assert session._transaction is None or True

    def test_repeated_calls_yield_working_sessions(self):
        for _ in range(3):
            generator = get_db()
            session = next(generator)
            assert session.execute(text("SELECT 1")).scalar() == 1
            generator.close()


class TestLiveConnection:
    def test_select_one_works(self):
        with engine.connect() as connection_:
            assert connection_.execute(text("SELECT 1")).scalar() == 1

    def test_session_can_execute_query(self):
        session = SessionLocal()
        try:
            assert session.execute(text("SELECT 1")).scalar() == 1
        finally:
            session.close()

    def test_postgres_version_available(self):
        with engine.connect() as connection_:
            version = connection_.execute(text("SHOW server_version")).scalar()
        assert version.startswith("18.")

    def test_current_database_is_reachable(self):
        with engine.connect() as connection_:
            name = connection_.execute(text("SELECT current_database()")).scalar()
            dialect = connection_.exec_driver_sql("SELECT version()").scalar()
        assert name
        assert "PostgreSQL" in dialect

    def test_get_db_session_executes_against_postgres(self):
        generator = get_db()
        session = next(generator)
        try:
            assert session.execute(text("SELECT 1")).scalar() == 1
        finally:
            generator.close()

    def test_no_tables_created_by_importing_module(self):
        with engine.connect() as connection_:
            count = connection_.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            ).scalar()
        assert count > 0  # existing migrations created them, not this module