from __future__ import annotations

from types import SimpleNamespace
from typing import cast, TYPE_CHECKING

import flask
import jwt
import pytest

from flask_htmx_template.controllers.auth import bearer

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

_TEST_ISSUER = "https://issuer.example"  # flask-htmx-template: ignore[url]
_INCOMPLETE_AUTHORITY = "https://incomplete.example"  # flask-htmx-template: ignore[url]
_RACING_AUTHORITY = "https://racing.example"  # flask-htmx-template: ignore[url]
_TEST_KEYS_URL = "https://keys.example"  # flask-htmx-template: ignore[url]


def _claims_for(
    claims: Mapping[str, object],
) -> Callable[..., dict[str, object]]:
    def return_claims(*_: object) -> dict[str, object]:
        return dict(claims)

    return return_claims


def _configured_authority_config(_: str) -> bearer._AuthorityConfig:
    return bearer._AuthorityConfig(
        client=jwt.PyJWKClient(_TEST_KEYS_URL),
        issuer=_TEST_ISSUER,
    )


def _configure_jwt(flask_app: flask.Flask) -> None:
    flask_app.config["AUTH_AUTHORITY"] = "issuer.example"
    flask_app.config["AUTH_AUDIENCE"] = "template-api"


def _reject_legacy_token(_: str) -> None:
    return None


def test_bearer_provider_urls_and_endpoints(flask_app: flask.Flask) -> None:
    with flask_app.test_request_context("/?next=%2Fitems"):
        login_url = bearer.BearerAuth.login_url("/items")
        logout_url = bearer.BearerAuth.logout_url("/items")

    assert login_url == "/login?next=/items"
    assert logout_url == "/h/logout?next=/items"
    assert bearer.BearerAuth.endpoints() == []


def test_setting_uses_environment_when_app_config_is_empty(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flask_app.config["AUTH_AUDIENCE"] = ""
    monkeypatch.setenv("AUTH_AUDIENCE", "environment-audience")

    with flask_app.app_context():
        audience = bearer._audience()

    assert audience == "environment-audience"


def test_setting_uses_environment_without_app_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_AUDIENCE", "environment-audience")

    audience = bearer._audience()

    assert audience == "environment-audience"


def test_authority_config_discovers_and_caches_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _TEST_ISSUER
    bearer._AUTHORITY_CONFIGS.pop(authority, None)
    calls: list[str] = []

    def get_discovery(url: str, *, timeout: float) -> SimpleNamespace:
        calls.append(url)
        assert timeout == bearer._DISCOVERY_TIMEOUT
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "jwks_uri": f"{_TEST_ISSUER}/keys",
                "issuer": f"{_TEST_ISSUER}/{{tenantid}}/v2.0",
            },
        )

    monkeypatch.setattr(bearer.requests, "get", get_discovery)

    config = bearer._authority_config(authority)
    cached_config = bearer._authority_config(authority)

    assert cached_config is config
    assert config.issuer == f"{_TEST_ISSUER}/{{tenantid}}/v2.0"
    assert calls == [f"{authority}/v2.0/.well-known/openid-configuration"]


def test_authority_config_rejects_incomplete_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _INCOMPLETE_AUTHORITY
    bearer._AUTHORITY_CONFIGS.pop(authority, None)
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"issuer": _INCOMPLETE_AUTHORITY},
    )

    def get_discovery(url: str, *, timeout: float) -> SimpleNamespace:
        _ = (url, timeout)
        return response

    monkeypatch.setattr(bearer.requests, "get", get_discovery)

    with pytest.raises(TypeError, match="issuer or jwks_uri"):
        bearer._authority_config(authority)


def test_authority_config_uses_value_populated_while_waiting_for_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _RACING_AUTHORITY
    config = bearer._AuthorityConfig(
        client=jwt.PyJWKClient(_TEST_KEYS_URL),
        issuer="issuer",
    )
    bearer._AUTHORITY_CONFIGS.pop(authority, None)

    class PopulateCacheLock:
        def __enter__(self) -> None:
            bearer._AUTHORITY_CONFIGS[authority] = config

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(bearer, "_AUTHORITY_LOCK", PopulateCacheLock())

    cached_config = bearer._authority_config(authority)

    assert cached_config is config


def test_claims_requires_audience(flask_app: flask.Flask) -> None:
    with flask_app.app_context(), pytest.raises(ValueError, match="audience"):
        bearer._claims(
            "sample-credential",
            bearer._AuthorityConfig(
                client=jwt.PyJWKClient(_TEST_KEYS_URL),
                issuer="issuer",
            ),
        )


def test_claims_expands_tenant_and_verifies_token(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decoded: list[dict[str, object]] = []

    def decode(credential: str, **kwargs: object) -> dict[str, object]:
        assert credential == "sample-credential"
        decoded.append(kwargs)
        if kwargs.get("options") == {"verify_signature": False}:
            return {"tid": "tenant-id"}
        return {"sub": "subject"}

    monkeypatch.setattr(bearer.jwt, "decode", decode)

    def get_signing_key(credential: str) -> SimpleNamespace:
        _ = credential
        return SimpleNamespace(key="key")

    client = SimpleNamespace(get_signing_key_from_jwt=get_signing_key)
    config = bearer._AuthorityConfig(
        issuer=f"{_TEST_ISSUER}/{{tenantid}}",
        client=cast("jwt.PyJWKClient", client),
    )

    with flask_app.app_context():
        claims = bearer._claims("sample-credential", config, "audience")

    assert claims == {"sub": "subject"}
    assert decoded[1]["issuer"] == f"{_TEST_ISSUER}/tenant-id"
    assert decoded[1]["algorithms"] == ["RS256"]


@pytest.mark.parametrize(
    ("claims", "expected"),
    [
        ({"roles": "Items.Read.All Items.Write.All"}, (True, True)),
        ({"roles": ["Items.Read.All", 42]}, (True, False)),
        ({"roles": None}, (False, False)),
    ],
)
def test_role_permissions_maps_supported_role_claims(
    flask_app: flask.Flask,
    claims: dict[str, object],
    expected: tuple[bool, bool],
) -> None:
    with flask_app.app_context():
        permissions = bearer._role_permissions(claims)

    assert permissions == expected


@pytest.mark.parametrize(
    ("claims", "expected"),
    [
        ({"scp": "Api.Connect", "roles": ["Items.Read.All"]}, None),
        (
            {
                "preferred_username": "user@example.com",
                "scp": "Other",
                "roles": ["Items.Read.All"],
            },
            None,
        ),
        (
            {
                "preferred_username": "user@example.com",
                "scp": "Api.Connect",
                "roles": ["Other"],
            },
            None,
        ),
    ],
)
def test_delegated_identity_rejects_claims_without_access(
    flask_app: flask.Flask,
    claims: dict[str, object],
    expected: object,
) -> None:
    with flask_app.app_context():
        identity = bearer._delegated_identity(claims)

    assert identity is expected


@pytest.mark.parametrize(
    "claims",
    [{"roles": ["Items.Read.All"]}, {"azp": "", "roles": ["Items.Read.All"]}],
)
def test_application_identity_requires_client_id(
    flask_app: flask.Flask,
    claims: dict[str, object],
) -> None:
    with flask_app.app_context():
        identity = bearer._application_identity(claims)

    assert identity is None


def test_identity_rejects_jwt_when_authority_is_unconfigured(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flask_app.config["AUTH_AUDIENCE"] = "audience"
    flask_app.config["AUTH_AUTHORITY"] = ""
    monkeypatch.setattr(bearer, "_legacy_identity", _reject_legacy_token)

    with flask_app.test_request_context(
        headers={"Authorization": "Bearer sample-credential"},
    ):
        identity = bearer._identity(flask.request)

    assert identity is None


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
    _configure_jwt(flask_app)
    claims = {
        "preferred_username": "Alice@example.com",
        "scp": "Api.Connect",
        "roles": ["Items.Read.All", "Items.Write.All"],
    }
    monkeypatch.setattr(bearer, "_authority_config", _configured_authority_config)
    monkeypatch.setattr(bearer, "_claims", _claims_for(claims))

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
    _configure_jwt(flask_app)
    claims = {
        "sub": "application-subject",
        "azp": "application-id",
        "roles": ["Items.Read.All"],
    }
    monkeypatch.setattr(bearer, "_authority_config", _configured_authority_config)
    monkeypatch.setattr(bearer, "_claims", _claims_for(claims))

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
    _configure_jwt(flask_app)
    monkeypatch.setattr(bearer, "_authority_config", _configured_authority_config)

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
    _configure_jwt(flask_app)
    claims = {
        "sub": "application-subject",
        "azp": "application-id",
        "roles": ["Items.Unrelated"],
    }
    monkeypatch.setattr(bearer, "_authority_config", _configured_authority_config)
    monkeypatch.setattr(bearer, "_claims", _claims_for(claims))

    with flask_app.test_request_context(
        headers={"Authorization": "Bearer role-less-token"},
    ):
        user = bearer.load_user(flask.request)

    assert user is None


def test_load_user_requires_provisioned_user(
    flask_app: flask.Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_jwt(flask_app)
    claims = {
        "preferred_username": "Alice@example.com",
        "scp": "Api.Connect",
        "roles": ["Items.Read.All"],
    }
    monkeypatch.setattr(bearer, "_authority_config", _configured_authority_config)
    monkeypatch.setattr(bearer, "_claims", _claims_for(claims))

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
    _configure_jwt(flask_app)
    claims = {
        "preferred_username": "Alice@example.com",
        "scp": "Api.Connect",
        "roles": ["Items.Read.All", "Items.Write.All"],
    }
    monkeypatch.setattr(bearer, "_authority_config", _configured_authority_config)
    monkeypatch.setattr(bearer, "_claims", _claims_for(claims))

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
