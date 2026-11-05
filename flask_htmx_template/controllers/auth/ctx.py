"""Authentication request context helpers."""

from __future__ import annotations

from flask_htmx_template.controllers.auth.base import (
    AUTH_PROVIDER,
    before_req_check_login,
    before_req_permissions_required,
    default_login_required,
    get_persisted_user,
    get_user,
    item_read_required,
    item_write_required,
    login_exempt,
    WebUser,
    write_permissions_required,
)

__all__ = [
    "AUTH_PROVIDER",
    "WebUser",
    "before_req_check_login",
    "before_req_permissions_required",
    "default_login_required",
    "get_persisted_user",
    "get_user",
    "item_read_required",
    "item_write_required",
    "login_exempt",
    "write_permissions_required",
]
