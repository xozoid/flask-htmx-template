"""Authentication provider registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask_htmx_template.controllers.auth import base, bearer
from flask_htmx_template.controllers.auth.debug import DebugAuth
from flask_htmx_template.controllers.auth.password import PasswordAuth

if TYPE_CHECKING:
    import flask


_AUTH_PROVIDERS: list[type[base.Auth]] = [PasswordAuth, DebugAuth, bearer.BearerAuth]


def setup(app: flask.Flask) -> None:
    """Register configured authentication providers on the app."""
    base.setup(app, _AUTH_PROVIDERS)


def provider(app: flask.Flask, provider_type: type[base.Auth]) -> base.Auth:
    """Return a registered provider instance.

    Args:
        app: Flask application containing the provider
        provider_type: Provider class to retrieve

    Returns:
        Registered provider instance

    Raises:
        TypeError: If the requested provider is not registered.

    """
    provider_instance = getattr(app, f"_auth_{provider_type.__name__}", None)
    if not isinstance(provider_instance, provider_type):
        msg = f"Provider {provider_type.__name__} is not registered"
        raise TypeError(msg)
    return provider_instance
