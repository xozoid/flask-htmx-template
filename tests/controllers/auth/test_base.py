from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from flask_htmx_template import exceptions as exc
from flask_htmx_template import web
from flask_htmx_template.controllers.auth import base, top
from flask_htmx_template.controllers.auth.debug import DebugAuth
from flask_htmx_template.controllers.auth.password import PasswordAuth
from flask_htmx_template.models.user import User

if TYPE_CHECKING:
    import flask
    from sqlalchemy import orm

    from tests.controllers.conftest import WebClient


def test_provider_login_sets_htmx_redirect(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flask_app,
        "_auth_PasswordAuth",
        PasswordAuth(flask_app),
        raising=False,
    )

    with flask_app.test_request_context("/?next=%2Fitems"):
        response = PasswordAuth.login()

    assert response.headers["HX-Redirect"] == "/login?next=/items"


def test_provider_login_rejects_unregistered_provider(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flask_app, "_auth_PasswordAuth", object(), raising=False)

    with flask_app.test_request_context(), pytest.raises(TypeError):
        PasswordAuth.login()


def test_password_provider_urls_and_endpoints(flask_app: flask.Flask) -> None:
    with flask_app.test_request_context("/?next=%2Fitems"):
        login_url = PasswordAuth.login_url("/items")
        logout_url = PasswordAuth.logout_url("/items")

    assert login_url == "/login?next=/items"
    assert logout_url == "/h/logout?next=/items"
    assert PasswordAuth.endpoints() == []


def test_provider_rejects_unregistered_type(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flask_app, "_auth_PasswordAuth", object(), raising=False)

    with pytest.raises(TypeError, match="Provider PasswordAuth is not registered"):
        top.provider(flask_app, PasswordAuth)


def test_provider_returns_registered_instance(flask_app: flask.Flask) -> None:
    provider = top.provider(flask_app, DebugAuth)

    assert isinstance(provider, DebugAuth)


def test_upsert_user_rejects_blank_username(web_client: WebClient) -> None:
    with pytest.raises(exc.InvalidORMValueError, match="Username must not be blank"):
        base.Auth.upsert_user("  ")


@pytest.mark.parametrize(
    ("read_only", "expected_write"),
    [(True, False), (False, True)],
)
def test_upsert_user_applies_read_only_compatibility(
    web_client: WebClient,
    read_only: bool,
    expected_write: bool,
) -> None:
    user = base.Auth.upsert_user("compatibility-user", read_only=read_only)

    assert user.item_read
    assert user.item_write is expected_write


def test_upsert_existing_user_applies_new_permissions(
    web_client: WebClient,
    session: orm.Session,
) -> None:
    User.create(username="existing-user", items_read=True, items_write=True)
    session.commit()

    user = base.Auth.upsert_user(
        "existing-user",
        items_read=True,
        items_write=False,
    )

    assert user.item_read
    assert not user.item_write


def test_upsert_user_recovers_from_concurrent_insert(
    web_client: WebClient,
    session: orm.Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    User.create(username="racing-user")
    session.commit()
    query_calls = 0
    original_query = User.query

    class EmptyQuery:
        def where(self, *_: object) -> EmptyQuery:
            return self

        @staticmethod
        def first() -> None:
            return None

    def query(cls: type[User]) -> object:
        nonlocal query_calls
        query_calls += 1
        return EmptyQuery() if query_calls == 1 else original_query()

    def fail_create(**_: object) -> None:
        statement = "insert"
        raise exc.IntegrityError(statement, {}, RuntimeError("duplicate"))

    monkeypatch.setattr(User, "query", classmethod(query))
    monkeypatch.setattr(User, "create", fail_create)

    user = base.Auth.upsert_user("racing-user", items_write=True)

    assert user.item_write


def test_before_permissions_allows_missing_view(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flask_app.testing = False
    monkeypatch.setattr(base, "_view", lambda: None)

    with flask_app.test_request_context("/"):
        result = base.before_req_permissions_required()

    assert result is None


def test_write_route_allows_get_for_read_only_user(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flask_app.testing = False

    def view() -> None:
        return None

    view.__dict__["item_permission"] = "write"
    monkeypatch.setattr(base, "_view", lambda: view)
    monkeypatch.setattr(
        base.flask_login,
        "current_user",
        base.WebUser(username="read-only", items_read=True, items_write=False),
    )

    with flask_app.test_request_context("/", method="GET"):
        result = base.before_req_permissions_required()

    assert result is None


def test_database_returns_web_extension_database() -> None:
    assert base.database() is web.db


def test_get_user_returns_legacy_password_identity(web_client: WebClient) -> None:
    user = base.get_user(base.WebUser.ID)

    assert isinstance(user, base.WebUser)
    assert user.item_read
    assert user.item_write


def test_get_user_returns_anonymous_for_unknown_username(web_client: WebClient) -> None:
    user = base.get_user("missing-user")

    assert not user.is_authenticated
