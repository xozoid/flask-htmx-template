"""Database-backed users and item permissions."""

from __future__ import annotations

from sqlalchemy import orm

from flask_htmx_template.models.base import (
    Base,
    ORMBool,
    ORMStr,
    string_column_args,
)


class User(Base):
    """User identified by a provider username.

    Attributes:
        username: Provider username or debug-login username.
        items_read: Whether the user may read items.
        items_write: Whether the user may create, update, or delete items.

    """

    __tablename__ = "user"
    __table_id__ = None

    username: ORMStr = orm.mapped_column(unique=True)
    items_read: ORMBool = orm.mapped_column(default=False)
    items_write: ORMBool = orm.mapped_column(default=False)

    __table_args__ = (*string_column_args("username"),)

    @orm.validates("username")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validate the username.

        Args:
            key: Field being updated.
            field: Updated value.

        Returns:
            Cleaned username.

        """
        if field is not None:
            field = field.lower()
        return self.clean_strings(key, field)

    @property
    def item_read(self) -> bool:
        """Whether the user may read items."""
        return self.items_read or self.items_write

    @item_read.setter
    def item_read(self, value: bool) -> None:
        self.items_read = value

    @property
    def item_write(self) -> bool:
        """Whether the user may write items."""
        return self.items_write

    @item_write.setter
    def item_write(self, value: bool) -> None:
        self.items_write = value
