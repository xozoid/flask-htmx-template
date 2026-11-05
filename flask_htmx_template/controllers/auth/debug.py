"""Debug-only authentication endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flask
import flask_login

from flask_htmx_template import exceptions as exc
from flask_htmx_template.controllers import base as controller_base
from flask_htmx_template.controllers.auth import ctx
from flask_htmx_template.controllers.auth.base import Auth, AUTH_PROVIDER, AuthEndpoint

if TYPE_CHECKING:
    from werkzeug.wrappers import Response

    from flask_htmx_template.controllers import base


class DebugAuth(Auth):
    """Provider for the debug-only username and role login."""

    @staticmethod
    def login_url(next_url: str | None) -> str:
        """Return the debug login page.

        Returns:
            Login page URL.

        """
        return flask.url_for("auth.page_login", next=next_url)

    @staticmethod
    def logout_url(next_url: str | None) -> str:
        """Return the shared logout endpoint.

        Returns:
            Logout URL.

        """
        return flask.url_for("auth.logout", next=next_url)

    @classmethod
    def endpoints(cls) -> list[AuthEndpoint]:
        """Return the debug provider endpoints.

        Returns:
            Empty endpoint list because debug login is a development-only
            action on the shared login page.

        """
        return []


@ctx.login_exempt
def debug_login() -> str | Response:
    """POST a debug login without credentials.

    Returns:
        Redirect to the requested page.

    Raises:
        Unauthorized: If Flask debug mode is disabled.

    """
    if not flask.current_app.debug:
        raise exc.http.Unauthorized
    username = flask.request.form.get("username") or "debug"
    if not username.strip():
        return controller_base.error("Username must not be blank")
    selected_roles = {value.lower() for value in flask.request.form.getlist("roles")}
    items_read = (
        bool(
            flask.request.form.get("items_read") or flask.request.form.get("item_read"),
        )
        or "items_read" in selected_roles
    )
    items_write = (
        bool(
            flask.request.form.get("items_write")
            or flask.request.form.get("item_write"),
        )
        or "items_write" in selected_roles
    )
    web_user = DebugAuth.upsert_user(
        username,
        items_read=items_read,
        items_write=items_write,
    )
    flask_login.login_user(web_user, remember=True)
    flask.session[AUTH_PROVIDER] = DebugAuth.__name__
    return flask.redirect(
        flask.request.form.get("next")
        or flask.request.args.get("next")
        or flask.url_for("common.page_dashboard"),
    )


ROUTE_PREFIX = "auth"
ROUTES: base.Routes = {
    "/d/auth/login": (debug_login, ["POST"]),
}
