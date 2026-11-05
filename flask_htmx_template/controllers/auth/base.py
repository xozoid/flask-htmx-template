"""Provider-neutral authentication policy and database user loading."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Literal, NamedTuple, TYPE_CHECKING

import flask
import flask_login

from flask_htmx_template import exceptions as exc
from flask_htmx_template import sql, web
from flask_htmx_template.controllers import base as controller_base
from flask_htmx_template.models.user import User

if TYPE_CHECKING:
    from flask_htmx_template.database import Database

AUTH_PROVIDER = "_auth_provider"


class AuthEndpoint(NamedTuple):
    """A provider-owned authentication endpoint."""

    label: str
    endpoint: str
    kwargs: dict[str, object]


class WebUser(flask_login.UserMixin):
    """Flask-Login user carrying database-backed item permissions."""

    ID = "web"

    def __init__(
        self,
        user: User | None = None,
        *,
        username: str | None = None,
        items_read: bool = True,
        items_write: bool = True,
    ) -> None:
        """Initialize a web user.

        Args:
            user: Persisted user, if one exists.
            username: Username for a non-persisted user.
            items_read: Whether the user may read items.
            items_write: Whether the user may write items.

        """
        super().__init__()
        if user is not None:
            username = user.username
            items_read = user.items_read
            items_write = user.items_write
        self.id = username or self.ID
        self.username = self.id
        self.items_read = items_read or items_write
        self.items_write = items_write

    @classmethod
    def system(cls) -> WebUser:
        """Return the legacy password-login user with all item permissions.

        Returns:
            A non-persisted user with full item permissions.

        """
        return cls()

    @property
    def item_read(self) -> bool:
        """Whether this user may read items."""
        return self.items_read

    @property
    def item_write(self) -> bool:
        """Whether this user may write items."""
        return self.items_write

    def has_item_permission(self, permission: Literal["read", "write"]) -> bool:
        """Check an item permission by its short name.

        Returns:
            True when the permission is available.

        """
        return self.item_read if permission == "read" else self.item_write


class Auth(ABC):
    """Base class for authentication providers.

    Provider implementations own redirect and endpoint details. User loading,
    role persistence, and Flask-Login session creation stay shared here.
    """

    def __init__(self, app: flask.Flask) -> None:
        """Initialize a provider for an application."""
        self._app = app

    @staticmethod
    @abstractmethod
    def login_url(next_url: str | None) -> str:
        """Return the provider login URL."""

    @staticmethod
    @abstractmethod
    def logout_url(next_url: str | None) -> str:
        """Return the provider logout URL."""

    @classmethod
    @abstractmethod
    def endpoints(cls) -> list[AuthEndpoint]:
        """Return provider-owned login endpoints."""

    @classmethod
    def upsert_user(
        cls,
        username: str,
        name: str | None = None,
        *,
        items_read: bool = True,
        items_write: bool = False,
        read_only: bool | None = None,
    ) -> WebUser:
        """Create or update a provider user and return its web identity.

        Args:
            username: Provider username.
            name: Optional provider display name. The template stores only the
                stable username.
            items_read: Whether the user may read items.
            items_write: Whether the user may write items.
            read_only: Compatibility flag for older provider adapters.

        Returns:
            Detached Flask-Login user snapshot.

        Raises:
            InvalidORMValueError: If the username is blank.

        """
        _ = name
        if read_only is not None:
            items_read = True
            items_write = not read_only
        username = username.strip().lower()
        if not username:
            msg = "Username must not be blank"
            raise exc.InvalidORMValueError(msg)
        items_read = items_read or items_write
        with web.db.begin_session() as session:
            user = User.query().where(User.username == username).first()
            if user is None:
                try:
                    with session.begin_nested():
                        user = User.create(
                            username=username,
                            items_read=items_read,
                            items_write=items_write,
                        )
                except exc.IntegrityError:
                    # NOTE: Two initial logins can race to provision the same
                    # identity. The unique username constraint selects one row.
                    user = sql.one(User.query().where(User.username == username))
                    user.items_read = items_read
                    user.items_write = items_write
            else:
                # NOTE: Provider claims are authoritative so role changes take
                # effect on the next bearer request instead of staying cached.
                with session.begin_nested():
                    user.items_read = items_read
                    user.items_write = items_write
            return WebUser(user)

    @classmethod
    def login_user(
        cls,
        username: str,
        name: str | None = None,
        **options: bool | None,
    ) -> WebUser:
        """Persist and log in a user through Flask-Login.

        Returns:
            The user snapshot passed to Flask-Login.

        Options:
            items_read: Whether the user may read items.
            items_write: Whether the user may write items.
            read_only: Compatibility flag for older provider adapters.
            remember: Whether Flask-Login should persist the session.

        """
        items_read = options.get("items_read", True) is not False
        items_write = options.get("items_write", True) is not False
        read_only = options.get("read_only")
        remember = options.get("remember", True) is not False
        web_user = cls.upsert_user(
            username,
            name,
            items_read=items_read,
            items_write=items_write,
            read_only=read_only,
        )
        flask_login.login_user(web_user, remember=remember)
        flask.session[AUTH_PROVIDER] = cls.__name__
        return web_user

    @classmethod
    def login(cls) -> flask.Response:
        """Return an HTMX redirect to the provider's login URL.

        Returns:
            Empty response containing an HTMX redirect header.

        Raises:
            TypeError: If the provider has not been registered on the app.

        """
        provider = getattr(flask.current_app, f"_auth_{cls.__name__}")
        if not isinstance(provider, Auth):
            msg = f"Provider {cls.__name__} is not registered"
            raise TypeError(msg)
        response = flask.make_response()
        response.headers["HX-Redirect"] = provider.login_url(
            flask.request.args.get("next"),
        )
        return response


def login_exempt[T: Callable[..., Any]](func: T) -> T:
    """Mark a route as exempt from the default login requirement.

    Returns:
        The marked route callable.

    """
    func.__dict__["login_exempt"] = True
    return func


def item_read_required[T: Callable[..., Any]](func: T) -> T:
    """Mark a route as requiring item read permission.

    Returns:
        The marked route callable.

    """
    func.__dict__["item_permission"] = "read"
    return func


def item_write_required[T: Callable[..., Any]](func: T) -> T:
    """Mark a route as requiring item write permission for mutations.

    Returns:
        The marked route callable.

    """
    func.__dict__["item_permission"] = "write"
    return func


def _view() -> Callable[..., Any] | None:
    endpoint = flask.request.endpoint
    if not endpoint or endpoint.rsplit(".", 1)[-1] == "static":
        return None
    return flask.current_app.view_functions[endpoint]


def default_login_required() -> flask.Response | None:
    """Require authentication while preserving JSON bearer responses.

    Returns:
        An authorization response, a browser redirect, or ``None``.

    """
    view = _view()
    if view is None or flask.current_app.testing:
        return None
    if getattr(view, "login_exempt", False):
        return None

    if flask.request.path.startswith("/j/"):
        if flask_login.current_user.is_authenticated:
            before_req_permissions_required()
            return None
        response = flask.jsonify({"errors": ["Bearer token required"]})
        response.status_code = controller_base.HTTP_CODE_UNAUTHORIZED
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    response = flask_login.login_required(lambda: None)()
    if response is None:
        before_req_permissions_required()
    return response


def before_req_permissions_required() -> None:
    """Enforce item permissions declared by the current endpoint.

    Raises:
        Unauthorized: If the current user lacks the declared permission.

    """
    view = _view()
    if view is None or flask.current_app.testing:
        return
    permission = getattr(view, "item_permission", None)
    if permission is None:
        return
    if permission == "write" and flask.request.method in {"GET", "HEAD"}:
        permission = "read"
    user = flask_login.current_user
    if not isinstance(user, WebUser) or not user.has_item_permission(permission):
        msg = "User does not have permission for this operation"
        raise exc.http.Unauthorized(msg)


before_req_check_login = default_login_required
write_permissions_required = item_write_required


def get_persisted_user(username: str) -> WebUser | None:
    """Load a persisted user by username.

    Returns:
        The persisted user, or ``None`` when it does not exist.

    """
    try:
        with web.db.begin_session():
            user = User.query().where(User.username == username).first()
            if user is not None:
                return WebUser(user)
    except (exc.NoResultFound, exc.DatabaseError):  # pragma: no cover
        return None
    return None


def get_user(username: str) -> WebUser | flask_login.AnonymousUserMixin:
    """Load a persisted Flask-Login user by username.

    Returns:
        The persisted user or an anonymous user.

    """
    user = get_persisted_user(username)
    if user is not None:
        return user
    # NOTE: Existing sessions created before the user migration use the
    # password-login identifier without a corresponding row.
    if username == WebUser.ID:
        return WebUser.system()
    return flask_login.AnonymousUserMixin()


def setup(app: flask.Flask, providers: list[type[Auth]]) -> None:
    """Instantiate providers and attach them to the Flask application."""
    for provider_type in providers:
        setattr(app, f"_auth_{provider_type.__name__}", provider_type(app))


def database() -> Database:
    """Return the active database for provider implementations.

    Returns:
        The database attached to the Flask extension.

    """
    return web.db
