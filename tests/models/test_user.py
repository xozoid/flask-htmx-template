from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from flask_htmx_template import exceptions as exc
from flask_htmx_template.models.user import User

if TYPE_CHECKING:
    from sqlalchemy import orm


def test_create_normalizes_username(session: orm.Session) -> None:
    user = User.create(username="  Alice ", items_read=True)

    assert user.username == "alice"
    assert user.items_read
    assert not user.items_write


def test_write_permission_is_independent(session: orm.Session) -> None:
    user = User.create(username="writer", items_write=True)

    assert user.item_read
    assert user.item_write


def test_short_username_is_rejected(session: orm.Session) -> None:
    with pytest.raises(exc.InvalidORMValueError):
        User.create(username="a")
