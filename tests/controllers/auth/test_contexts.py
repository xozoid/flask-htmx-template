from __future__ import annotations

from typing import TYPE_CHECKING

from flask_htmx_template import web
from flask_htmx_template.models.config import Config, ConfigKey

if TYPE_CHECKING:
    import flask

    from tests.controllers.conftest import WebClient


def test_json_api_allows_valid_bearer_token(
    web_client: WebClient,
    flask_app: flask.Flask,
) -> None:
    with web.db.begin_session():
        token = Config.fetch(ConfigKey.API_BEARER_TOKEN)
    flask_app.testing = False

    try:
        denied, _ = web_client.GET_J(
            "api_docs.json_api",
            headers={"Authorization": f"Bearer {token}", "HX-Request": "true"},
            rc=401,
        )
        login, _ = web_client.POST_J(
            "auth.json_login",
            headers={"Authorization": f"Bearer {token}", "HX-Request": "true"},
        )
        result, _ = web_client.GET_J(
            "api_docs.json_api",
            headers={"Authorization": f"Bearer {token}", "HX-Request": "true"},
        )
    finally:
        flask_app.testing = True

    assert denied == {"errors": ["Bearer token required"]}
    assert login == {"username": "api", "items_read": True, "items_write": True}
    urls = result["urls"]
    assert isinstance(urls, dict)
    assert "/j/items" in urls
