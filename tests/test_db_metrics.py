from __future__ import annotations

from pathlib import Path
from typing import NoReturn, TYPE_CHECKING

import prometheus_client

from flask_htmx_template import db_metrics
from flask_htmx_template.database import (
    Database,
    DEFAULT_DATABASE_PATH,
    SQLiteDatabase,
)
from flask_htmx_template.models.applied_migration import AppliedMigration

if TYPE_CHECKING:
    import pytest


def test_create_app_uses_shared_default_database_path(
    monkeypatch: pytest.MonkeyPatch,
    empty_database: SQLiteDatabase,
) -> None:
    monkeypatch.delenv("DB_PATH", raising=False)
    database_path: list[Path] = []

    def use_empty_database(
        path: str | Path,
        *,
        check_migration: bool = True,
    ) -> SQLiteDatabase:
        database_path.append(Path(path))
        return empty_database

    monkeypatch.setattr(db_metrics, "SQLiteDatabase", use_empty_database)

    app = db_metrics.create_app()

    assert database_path == [Path(DEFAULT_DATABASE_PATH).expanduser().absolute()]
    assert any(rule.rule == "/metrics" for rule in app.url_map.iter_rules())


def test_create_app_uses_postgres_database(
    monkeypatch: pytest.MonkeyPatch,
    empty_database: SQLiteDatabase,
) -> None:
    monkeypatch.setenv("DB_PATH", "postgresql://user:pass@localhost/database")
    database_path: list[str] = []

    def use_empty_database(path: str, *, check_migration: bool = True) -> Database:
        database_path.append(path)
        return empty_database

    monkeypatch.setattr(db_metrics, "PostgresDatabase", use_empty_database)

    db_metrics.create_app()

    assert database_path == ["postgresql://user:pass@localhost/database"]


def test_metrics_endpoint_reports_database_state(
    monkeypatch: pytest.MonkeyPatch,
    empty_database: SQLiteDatabase,
) -> None:
    monkeypatch.setenv("DB_PATH", str(empty_database.path))
    app = db_metrics.create_app()

    response = app.test_client().get("/metrics")

    assert response.status_code == 200
    assert b"flask_htmx_template_database_up 1.0" in response.data
    assert b"flask_htmx_template_database_applied_migrations 4.0" in response.data
    assert b"flask_htmx_template_database_migration_required 0.0" in response.data
    metrics = app.extensions["flask_htmx_template_db_metrics"]
    assert metrics.registry is not prometheus_client.REGISTRY


def test_metrics_endpoint_reports_pending_migrations(
    monkeypatch: pytest.MonkeyPatch,
    empty_database: SQLiteDatabase,
) -> None:
    class MissingMigration:
        """Migration name used to exercise pending migration reporting."""

    monkeypatch.setenv("DB_PATH", str(empty_database.path))
    monkeypatch.setattr(db_metrics, "_MIGRATORS", [MissingMigration])
    app = db_metrics.create_app()

    response = app.test_client().get("/metrics")

    assert b"flask_htmx_template_database_migration_required 1.0" in response.data


def test_metrics_endpoint_reports_database_query_failure(
    monkeypatch: pytest.MonkeyPatch,
    empty_database: SQLiteDatabase,
) -> None:
    def fail_query(cls: type[AppliedMigration]) -> NoReturn:
        message = "query failed"
        raise RuntimeError(message)

    monkeypatch.setenv("DB_PATH", str(empty_database.path))
    monkeypatch.setattr(AppliedMigration, "all", classmethod(fail_query))
    app = db_metrics.create_app()

    response = app.test_client().get("/metrics")

    assert b"flask_htmx_template_database_up 0.0" in response.data
    assert b"flask_htmx_template_database_applied_migrations 0.0" in response.data
    assert b"flask_htmx_template_database_migration_required 0.0" in response.data
