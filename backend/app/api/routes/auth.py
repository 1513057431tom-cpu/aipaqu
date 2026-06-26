from fastapi import APIRouter, Cookie, Depends, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import (
    clear_session_cookie,
    get_bootstrap_user,
    get_current_user,
    session_store,
    set_session_cookie,
)
from app.core.errors import api_error

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class PublicUser(BaseModel):
    id: str
    email: EmailStr
    role: str
    workspaceId: str


class UserEnvelope(BaseModel):
    user: PublicUser


@router.post("/login", response_model=UserEnvelope)
def login(payload: LoginRequest, response: Response) -> UserEnvelope:
    user = get_bootstrap_user(payload.email, payload.password)
    if not user:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_CREDENTIALS",
            "Email or password is incorrect.",
        )

    session_id = session_store.create(user)
    set_session_cookie(response, session_id)
    return UserEnvelope(user=PublicUser(**user.to_public_dict()))


@router.get("/me", response_model=UserEnvelope)
def me(user=Depends(get_current_user)) -> UserEnvelope:
    return UserEnvelope(user=PublicUser(**user.to_public_dict()))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    aipaqu_session: str | None = Cookie(default=None),
) -> None:
    session_store.delete(aipaqu_session)
    clear_session_cookie(response)
    return None
