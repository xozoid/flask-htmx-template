"""Authentication JSON controllers."""

from __future__ import annotations

from typing import TypedDict

import flask

from flask_htmx_template.controllers import base
from flask_htmx_template.controllers.auth import bearer, ctx


class LoginContext(TypedDict):
    """Provisioned bearer identity returned by the JSON login endpoint."""

    username: str
    items_read: bool
    items_write: bool


@ctx.login_exempt
def json_login() -> LoginContext | base.JSONResponse:
    """POST a bearer token to provision its user for the JSON API.

    Clients must call this endpoint before using a bearer token on other JSON
    API endpoints. The bearer token is supplied in the Authorization header.

    Returns:
        Provisioned user permissions or an authentication error.

    """
    user = bearer.login(flask.request)
    if user is None:
        return {"errors": ["Bearer token required"]}, base.HTTP_CODE_UNAUTHORIZED
    return {
        "username": user.username,
        "items_read": user.item_read,
        "items_write": user.item_write,
    }


ROUTE_PREFIX = "auth"
ROUTES: base.Routes = {"/j/auth/login": (json_login, ["POST"])}
