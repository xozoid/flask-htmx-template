from __future__ import annotations

import flask
import jwt
import pytest

from flask_htmx_template.controllers.auth import bearer


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic token", "Bearer", "Bearer one two"],
)
def test_load_user_rejects_malformed_authorization(
    flask_app: flask.Flask,
    authorization: str | None,
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    with flask_app.test_request_context(headers=headers):
        user = bearer.load_user(flask.request)

    assert user is None


def test_login_accepts_delegated_jwt(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flask_app.config.update(
        AUTH_AUTHORITY="issuer.example",
        AUTH_AUDIENCE="template-api",
    )
    claims = {
        "preferred_username": "Alice@example.com",
        "scp": "Api.Connect",
        "roles": ["Items.Read.All", "Items.Write.All"],
    }
    monkeypatch.setattr(bearer, "_authority_config", lambda _: object())
    monkeypatch.setattr(bearer, "_claims", lambda *_: claims)

    with flask_app.test_request_context(
        headers={"Authorization": "Bearer delegated-token"},
    ):
        user = bearer.login(flask.request)

    assert user is not None
    assert user.username == "jwt:alice@example.com"
    assert user.item_read
    assert user.item_write


def test_login_accepts_application_jwt(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flask_app.config.update(
        AUTH_AUTHORITY="issuer.example",
        AUTH_AUDIENCE="template-api",
    )
    claims = {
        "sub": "application-subject",
        "azp": "application-id",
        "roles": ["Items.Read.All"],
    }
    monkeypatch.setattr(bearer, "_authority_config", lambda _: object())
    monkeypatch.setattr(bearer, "_claims", lambda *_: claims)

    with flask_app.test_request_context(
        headers={"Authorization": "Bearer application-token"},
    ):
        user = bearer.login(flask.request)

    assert user is not None
    assert user.username == "app:application-id"
    assert user.item_read
    assert not user.item_write


@pytest.mark.parametrize(
    "error",
    [jwt.ExpiredSignatureError("expired"), jwt.InvalidAudienceError("audience")],
)
def test_load_user_rejects_invalid_jwt(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    flask_app.config.update(
        AUTH_AUTHORITY="issuer.example",
        AUTH_AUDIENCE="template-api",
    )
    monkeypatch.setattr(bearer, "_authority_config", lambda _: object())

    def reject(*_: object) -> dict[str, object]:
        raise error

    monkeypatch.setattr(bearer, "_claims", reject)

    with flask_app.test_request_context(
        headers={"Authorization": "Bearer invalid-token"},
    ):
        user = bearer.load_user(flask.request)

    assert user is None


def test_load_user_rejects_missing_role(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flask_app.config.update(
        AUTH_AUTHORITY="issuer.example",
        AUTH_AUDIENCE="template-api",
    )
    claims = {
        "sub": "application-subject",
        "azp": "application-id",
        "roles": ["Items.Unrelated"],
    }
    monkeypatch.setattr(bearer, "_authority_config", lambda _: object())
    monkeypatch.setattr(bearer, "_claims", lambda *_: claims)

    with flask_app.test_request_context(
        headers={"Authorization": "Bearer role-less-token"},
    ):
        user = bearer.load_user(flask.request)

    assert user is None


def test_load_user_requires_provisioned_user(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flask_app.config.update(
        AUTH_AUTHORITY="issuer.example",
        AUTH_AUDIENCE="template-api",
    )
    claims = {
        "preferred_username": "Alice@example.com",
        "scp": "Api.Connect",
        "roles": ["Items.Read.All"],
    }
    monkeypatch.setattr(bearer, "_authority_config", lambda _: object())
    monkeypatch.setattr(bearer, "_claims", lambda *_: claims)

    with flask_app.test_request_context(
        headers={"Authorization": "Bearer delegated-token"},
    ):
        assert bearer.load_user(flask.request) is None
        assert bearer.login(flask.request) is not None
        user = bearer.load_user(flask.request)

    assert user is not None
    assert user.username == "jwt:alice@example.com"


def test_load_user_uses_current_jwt_permissions(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flask_app.config.update(
        AUTH_AUTHORITY="issuer.example",
        AUTH_AUDIENCE="template-api",
    )
    claims = {
        "preferred_username": "Alice@example.com",
        "scp": "Api.Connect",
        "roles": ["Items.Read.All", "Items.Write.All"],
    }
    monkeypatch.setattr(bearer, "_authority_config", lambda _: object())
    monkeypatch.setattr(bearer, "_claims", lambda *_: claims)

    with flask_app.test_request_context(
        headers={"Authorization": "Bearer delegated-token"},
    ):
        provisioned_user = bearer.login(flask.request)
        claims["roles"] = ["Items.Read.All"]
        user = bearer.load_user(flask.request)

    assert provisioned_user is not None
    assert provisioned_user.item_write
    assert user is not None
    assert user.item_read
    assert not user.item_write
