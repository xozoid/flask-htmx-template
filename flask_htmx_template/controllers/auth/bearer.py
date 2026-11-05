"""Opaque and provider-issued JWT bearer authentication."""

from __future__ import annotations

import logging
import os
import secrets
import threading
from typing import Any, cast, NamedTuple, TYPE_CHECKING

import flask
import jwt
import requests

from flask_htmx_template import web
from flask_htmx_template.controllers.auth import base
from flask_htmx_template.models.config import Config, ConfigKey

if TYPE_CHECKING:
    from collections.abc import Mapping

_LOGGER = logging.getLogger(__name__)
_DISCOVERY_TIMEOUT = 0.5
_JWKS_LIFESPAN = 300
_AUTHORIZATION_PARTS = 2
_AUTHORITY_KEYS = ("AUTH_AUTHORITY",)
_AUDIENCE_KEYS = ("AUTH_AUDIENCE",)
_SCOPE_KEYS = ("AUTH_SCOPE",)
_READ_ROLE_KEYS = ("AUTH_ROLE_READ",)
_WRITE_ROLE_KEYS = ("AUTH_ROLE_WRITE",)
# NOTE: The prefix prevents a delegated identity such as "web" from loading
# the password-login user before it has completed bearer provisioning.
_DELEGATED_USER_PREFIX = "jwt:"


class _AuthorityConfig(NamedTuple):
    client: jwt.PyJWKClient
    issuer: str


class _Identity(NamedTuple):
    """Verified bearer identity and its item permissions."""

    username: str
    items_read: bool
    items_write: bool


_AUTHORITY_CONFIGS: dict[str, _AuthorityConfig] = {}
_AUTHORITY_LOCK = threading.Lock()


class BearerAuth(base.Auth):
    """Provider for opaque and provider-issued bearer tokens."""

    @staticmethod
    def login_url(next_url: str | None) -> str:
        """Return the regular login page for browser requests.

        Returns:
            The URL for the browser login page.

        """
        return flask.url_for("auth.page_login", next=next_url)

    @staticmethod
    def logout_url(next_url: str | None) -> str:
        """Return the regular logout page for browser requests.

        Returns:
            The URL for the browser logout page.

        """
        return flask.url_for("auth.logout", next=next_url)

    @classmethod
    def endpoints(cls) -> list[base.AuthEndpoint]:
        """Return no browser login endpoint for bearer authentication.

        Returns:
            An empty endpoint list.

        """
        return []

    @staticmethod
    def load_user(request: flask.Request) -> base.WebUser | None:
        """Load a user from the request's bearer token.

        Returns:
            The authenticated user, or ``None`` when no token is accepted.

        """
        return load_user(request)


def _setting(keys: tuple[str, ...], *, default: str | None = None) -> str | None:
    """Read an auth setting from Flask config, then the process environment.

    Returns:
        The first configured value, or the default.

    """
    for key in keys:
        value = flask.current_app.config.get(key) if flask.has_app_context() else None
        if isinstance(value, str) and value:
            return value
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default


def _authority() -> str | None:
    """Return the configured JWT authority without a trailing slash.

    Returns:
        The normalized authority URL, or ``None``.

    """
    authority = _setting(_AUTHORITY_KEYS)
    return authority.rstrip("/") if authority else None


def _audience() -> str | None:
    """Return the configured JWT audience.

    Returns:
        The configured audience, or ``None``.

    """
    return _setting(_AUDIENCE_KEYS)


def _authority_config(authority: str) -> _AuthorityConfig:
    """Discover and cache OpenID metadata for an authority.

    Returns:
        The cached discovery metadata and signing-key client.

    Raises:
        TypeError: If the discovery response lacks required fields.

    """
    config = _AUTHORITY_CONFIGS.get(authority)
    if config is not None:
        return config
    with _AUTHORITY_LOCK:
        config = _AUTHORITY_CONFIGS.get(authority)
        if config is not None:
            return config
        # NOTE: The v2.0 discovery document has the issuer format expected by
        # v2 tokens; the authority root otherwise commonly returns v1 metadata.
        response = requests.get(
            f"{authority}/v2.0/.well-known/openid-configuration",
            timeout=_DISCOVERY_TIMEOUT,
        )
        response.raise_for_status()
        discovery = cast("Mapping[str, object]", response.json())
        jwks_uri = discovery.get("jwks_uri")
        issuer = discovery.get("issuer")
        if not isinstance(jwks_uri, str) or not isinstance(issuer, str):
            msg = "OpenID discovery response is missing issuer or jwks_uri"
            raise TypeError(msg)
        config = _AuthorityConfig(
            client=jwt.PyJWKClient(
                jwks_uri,
                cache_keys=True,
                lifespan=_JWKS_LIFESPAN,
                timeout=1,
            ),
            issuer=issuer,
        )
        _AUTHORITY_CONFIGS[authority] = config
        return config


def _claims(
    token: str,
    config: _AuthorityConfig,
    audience: str | None = None,
) -> dict[str, Any]:
    """Validate a JWT signature and its required registered claims.

    Returns:
        The verified JWT claims.

    Raises:
        ValueError: If no JWT audience is configured.

    """
    audience = audience or _audience()
    if audience is None:
        msg = "JWT audience is not configured"
        raise ValueError(msg)
    unverified = jwt.decode(token, options={"verify_signature": False})
    issuer = config.issuer.replace("{tenantid}", str(unverified.get("tid", "")))
    key = config.client.get_signing_key_from_jwt(token).key
    return jwt.decode(
        token,
        key=key,
        algorithms=["RS256"],
        audience=audience,
        issuer=issuer,
        options={"require": ["exp", "iss", "aud", "sub"]},
    )


def _scopes(claims: Mapping[str, object]) -> set[str]:
    """Extract delegated scopes from a token.

    Returns:
        The space-separated scopes in the token.

    """
    scope = claims.get("scp")
    return set(scope.split()) if isinstance(scope, str) else set()


def _roles(claims: Mapping[str, object]) -> set[str]:
    """Extract application roles from a token.

    Returns:
        The role names in the token.

    """
    roles = claims.get("roles")
    if isinstance(roles, str):
        return set(roles.split())
    if not isinstance(roles, list):
        return set()
    values = cast("list[object]", roles)
    return {value for value in values if isinstance(value, str)}


def _role_permissions(claims: Mapping[str, object]) -> tuple[bool, bool]:
    """Map configured read and write roles to item permissions.

    Returns:
        A pair indicating item-read and item-write permissions.

    """
    roles = _roles(claims)
    read_role = _setting(_READ_ROLE_KEYS, default="Items.Read.All")
    write_role = _setting(_WRITE_ROLE_KEYS, default="Items.Write.All")
    can_read = read_role is not None and read_role in roles
    can_write = write_role is not None and write_role in roles
    return can_read or can_write, can_write


def _delegated_identity(claims: Mapping[str, object]) -> _Identity | None:
    """Map a delegated token to a verified identity.

    Returns:
        The verified identity, or ``None`` when claims lack permission.

    """
    username = next(
        (
            value
            for key in ("preferred_username", "upn", "email")
            if isinstance(value := claims.get(key), str) and value
        ),
        None,
    )
    if username is None:
        return None
    required_scope = _setting(_SCOPE_KEYS, default="Api.Connect")
    if required_scope is not None and required_scope not in _scopes(claims):
        return None
    items_read, items_write = _role_permissions(claims)
    if not items_read:
        return None
    return _Identity(
        f"{_DELEGATED_USER_PREFIX}{username}",
        items_read=items_read,
        items_write=items_write,
    )


def _application_identity(claims: Mapping[str, object]) -> _Identity | None:
    """Map an application token to a verified identity.

    Returns:
        The verified identity, or ``None`` when claims lack permission.

    """
    application_id = (
        claims.get("azp")
        or claims.get("appid")
        or claims.get(
            "client_id",
        )
    )
    if not isinstance(application_id, str) or not application_id:
        return None
    items_read, items_write = _role_permissions(claims)
    if not items_read:
        return None
    return _Identity(
        f"app:{application_id}",
        items_read=items_read,
        items_write=items_write,
    )


_app_identity = _application_identity


def _legacy_identity(token: str) -> _Identity | None:
    """Return the legacy identity for the configured opaque token.

    Returns:
        The legacy identity, or ``None`` when the token does not match.

    """
    with web.db.begin_session():
        expected = Config.fetch(ConfigKey.API_BEARER_TOKEN, no_raise=True)
    if expected is not None and secrets.compare_digest(token, expected):
        return _Identity("api", items_read=True, items_write=True)
    return None


def _identity(request: flask.Request) -> _Identity | None:
    """Authenticate a legacy opaque token or configured JWT.

    Returns:
        The verified identity, or ``None`` when the token is rejected.

    """
    authorization = request.headers.get("Authorization", "")
    parts = authorization.split()
    if len(parts) != _AUTHORIZATION_PARTS or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    legacy_identity = _legacy_identity(token)
    if legacy_identity is not None:
        return legacy_identity
    audience = _audience()
    authority = _authority()
    if audience is None or authority is None:
        return None
    try:
        claims = _claims(token, _authority_config(authority), audience)
        if "scp" in claims:
            return _delegated_identity(claims)
        return _application_identity(claims)
    except Exception:
        _LOGGER.warning("Bearer token validation failed", exc_info=True)
        return None


def login(request: flask.Request) -> base.WebUser | None:
    """Provision a verified bearer identity for subsequent API requests.

    Returns:
        The provisioned user, or ``None`` when the token is rejected.

    """
    identity = _identity(request)
    if identity is None:
        return None
    return base.Auth.upsert_user(
        identity.username,
        items_read=identity.items_read,
        items_write=identity.items_write,
    )


def load_user(request: flask.Request) -> base.WebUser | None:
    """Load an already-provisioned user from a verified bearer token.

    Returns:
        The authenticated user, or ``None`` when not provisioned or rejected.

    """
    identity = _identity(request)
    if identity is None:
        return None
    persisted_user = base.get_persisted_user(identity.username.strip().lower())
    if persisted_user is None:
        return None
    # NOTE: Persistence is a provisioning gate, not an authorization source.
    # A role removed from a newly validated token must take effect immediately.
    return base.WebUser(
        username=persisted_user.username,
        items_read=identity.items_read,
        items_write=identity.items_write,
    )
