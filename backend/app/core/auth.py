from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from secrets import token_urlsafe

from fastapi import Cookie, Response

from app.core.config import get_settings
from app.core.errors import api_error, unauthenticated

SESSION_COOKIE_NAME = "aipaqu_session"


class Role(str, Enum):
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"


@dataclass(frozen=True)
class User:
    id: str
    email: str
    role: Role
    workspace_id: str

    def to_public_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "workspaceId": self.workspace_id,
        }


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, User] = {}

    def create(self, user: User) -> str:
        session_id = token_urlsafe(32)
        self._sessions[session_id] = user
        return session_id

    def get(self, session_id: str | None) -> User | None:
        if not session_id:
            return None
        return self._sessions.get(session_id)

    def delete(self, session_id: str | None) -> None:
        if session_id:
            self._sessions.pop(session_id, None)


session_store = InMemorySessionStore()


def get_bootstrap_user(email: str, password: str) -> User | None:
    settings = get_settings()
    if email != settings.dev_admin_email or password != settings.dev_admin_password:
        return None
    return User(
        id="dev-admin",
        email=settings.dev_admin_email,
        role=Role.ADMIN,
        workspace_id="default",
    )


def set_session_cookie(response: Response, session_id: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def get_current_user(aipaqu_session: str | None = Cookie(default=None)) -> User:
    user = session_store.get(aipaqu_session)
    if not user:
        raise unauthenticated()
    return user


def require_role(user: User, allowed_roles: set[Role]) -> None:
    if user.role not in allowed_roles:
        raise api_error(
            403,
            "FORBIDDEN",
            "You do not have permission to access this resource.",
        )
