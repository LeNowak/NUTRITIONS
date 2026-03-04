from __future__ import annotations

import re

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.database import get_session
from app.models import User


TOKEN_PATTERN = re.compile(r"^[A-Z0-9]{8}$")
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Missing or invalid Authorization header.")

    token = credentials.credentials.strip()
    if not TOKEN_PATTERN.fullmatch(token):
        raise _unauthorized("Invalid token format. Expected 8 chars [A-Z0-9].")

    user = session.exec(select(User).where(User.token == token)).first()
    if not user:
        raise _unauthorized("Invalid token.")

    return user
