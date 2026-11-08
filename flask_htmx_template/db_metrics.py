"""Database metrics exporter."""

from __future__ import annotations

import os
from pathlib import Path

# NOTE: prometheus_client selects its registry mode on first import. Remove the
# Gunicorn multiprocess setting before importing it so this service owns a
# private registry and cannot expose or alter web-worker metrics.
os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)
os.environ.pop("prometheus_multiproc_dir", None)

# isort: split

import flask
import prometheus_client

from flask_htmx_template import sql
from flask_htmx_template.database import (
    DEFAULT_DATABASE_PATH,
    PostgresDatabase,
    SQLiteDatabase,
)
from flask_htmx_template.migrations.top import _MIGRATORS
from flask_htmx_template.models.applied_migration import AppliedMigration

_QUERY_TIMEOUT_MS = 2_000


class DatabaseMetrics:
    """Own the database connection, private registry, and gauges."""

    def __init__(self, database_path: str) -> None:
        """Initialize the metrics exporter.

        Args:
            database_path: SQLite path or PostgreSQL URL

        """
        if sql.is_postgres_url(database_path):
            self.database = PostgresDatabase(database_path, check_migration=False)
        else:
            path = Path(database_path).expanduser().absolute()
            self.database = SQLiteDatabase(path, check_migration=False)

        self.registry = prometheus_client.CollectorRegistry(auto_describe=True)
        self.database_up = prometheus_client.Gauge(
            "flask_htmx_template_database_up",
            "Whether the application database can be queried",
            registry=self.registry,
        )
        self.applied_migrations = prometheus_client.Gauge(
            "flask_htmx_template_database_applied_migrations",
            "Number of application database migrations that have been applied",
            registry=self.registry,
        )
        self.migration_required = prometheus_client.Gauge(
            "flask_htmx_template_database_migration_required",
            "Whether the application database has unapplied migrations",
            registry=self.registry,
        )

    def scrape(self) -> bytes:
        """Refresh database gauges and render Prometheus exposition.

        Returns:
            Prometheus text exposition bytes

        """
        try:
            applied = self._read_applied_migrations()
            self.database_up.set(1)
            self.applied_migrations.set(len(applied))
            self.migration_required.set(
                int(any(migrator.__name__ not in applied for migrator in _MIGRATORS)),
            )
        except Exception:
            flask.current_app.logger.exception("Failed to collect database metrics")
            self.database_up.set(0)
            self.applied_migrations.set(0)
            self.migration_required.set(0)

        return prometheus_client.generate_latest(self.registry)

    def _read_applied_migrations(self) -> set[str]:
        """Read applied migration names under the query time limit.

        Returns:
            Names of migrations recorded in the database

        """
        with (
            self.database.begin_session() as session,
            sql.time_limit(
                session,
                _QUERY_TIMEOUT_MS,
            ),
        ):
            return {migration.name for migration in AppliedMigration.all()}


def create_app() -> flask.Flask:
    """Create the standalone database metrics Flask application.

    Returns:
        Configured Flask app

    """
    app = flask.Flask(__name__)
    metrics = DatabaseMetrics(os.getenv("DB_PATH", DEFAULT_DATABASE_PATH))
    app.extensions["flask_htmx_template_db_metrics"] = metrics

    def page_metrics() -> flask.Response:
        """Render current database metrics.

        Returns:
            Prometheus text exposition response

        """
        return flask.Response(
            metrics.scrape(),
            content_type=prometheus_client.CONTENT_TYPE_LATEST,
        )

    app.add_url_rule("/metrics", view_func=page_metrics)
    return app
