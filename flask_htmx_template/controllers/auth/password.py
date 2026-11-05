"""Password authentication endpoint."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import flask

from flask_htmx_template import web
from flask_htmx_template.controllers import base
from flask_htmx_template.controllers.auth import ctx
from flask_htmx_template.controllers.auth.base import Auth, AuthEndpoint
from flask_htmx_template.models.config import Config, ConfigKey

if TYPE_CHECKING:
    import werkzeug


class PasswordAuth(Auth):
    """Provider for the existing shared password login."""

    @staticmethod
    def login_url(next_url: str | None) -> str:
        """Return the password login page.

        Returns:
            Login page URL.

        """
        return flask.url_for("auth.page_login", next=next_url)

    @staticmethod
    def logout_url(next_url: str | None) -> str:
        """Return the password logout endpoint.

        Returns:
            Logout URL.

        """
        return flask.url_for("auth.logout", next=next_url)

    @classmethod
    def endpoints(cls) -> list[AuthEndpoint]:
        """Return the password provider endpoints.

        Returns:
            Empty endpoint list because password login uses the shared page.

        """
        return []


@ctx.login_exempt
def login() -> str | werkzeug.Response:
    """POST password credentials.

    Returns:
        Validation error or dashboard redirect.

    """
    password = flask.request.form.get("password")
    if not password:
        return base.error("Password must not be blank")
    with web.db.begin_session():
        expected = Config.fetch(ConfigKey.WEB_KEY)
    if not secrets.compare_digest(password, expected):
        return base.error("Bad password")
    PasswordAuth.login_user("web", items_read=True, items_write=True)
    return flask.redirect(
        flask.request.form.get("next") or flask.url_for("common.page_dashboard"),
    )
