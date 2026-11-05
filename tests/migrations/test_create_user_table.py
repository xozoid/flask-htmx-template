from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import sqlalchemy

from flask_htmx_template.database import SQLiteDatabase
from flask_htmx_template.migrations.create_user_table import CreateUserTable
from flask_htmx_template.models.user import User

if TYPE_CHECKING:
    from pathlib import Path


def test_migrate(tmp_path: Path, data_path: Path) -> None:
    path_original = data_path / "old_versions" / "v0.2.0.db"
    path_db = tmp_path / "database.new.db"
    shutil.copyfile(path_original, path_db)
    database = SQLiteDatabase(path_db, check_migration=False)

    result = CreateUserTable().migrate(database)

    assert result == ["Created User table"]
    with database.begin_session() as session:
        assert (
            User.sql_table().name
            in sqlalchemy.inspect(
                session.get_bind(),
            ).get_table_names()
        )
