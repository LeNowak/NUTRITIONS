from __future__ import annotations

import re

from flask import Request
from sqlmodel import Session, select

from app.models import User


TOKEN_PATTERN = re.compile(r"^[A-Z0-9]{8}$")


class APIError(Exception):
    def __init__(self, status_code: int, detail: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}


def _unauthorized(detail: str) -> APIError:
    return APIError(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(request: Request, session: Session) -> User:
    auth_header = request.headers.get("Authorization", "").strip()
    if not auth_header:
        raise _unauthorized("Missing or invalid Authorization header.")

    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise _unauthorized("Missing or invalid Authorization header.")

    token = parts[1].strip()

    if not TOKEN_PATTERN.fullmatch(token):
        raise _unauthorized("Invalid token format. Expected 8 chars [A-Z0-9].")

    user = session.exec(select(User).where(User.token == token)).first()
    if not user:
        raise _unauthorized("Invalid token.")

    return user
