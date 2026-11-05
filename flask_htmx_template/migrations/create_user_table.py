"""Create the database-backed user table."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from flask_htmx_template.migrations.base import Migrator
from flask_htmx_template.models.base import Base
from flask_htmx_template.models.user import User

if TYPE_CHECKING:
    from flask_htmx_template.database import Database


class CreateUserTable(Migrator):
    """Create the user table used by authentication providers."""

    @override
    def migrate(self, d: Database) -> list[str]:
        """Create the user table.

        Args:
            d: Database to migrate.

        Returns:
            Migration comments.

        """
        with d.begin_session() as session:
            Base.metadata.create_all(session.get_bind(), [User.sql_table()])
        return ["Created User table"]
