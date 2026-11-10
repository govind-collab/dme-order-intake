"""FastAPI dependencies shared by the routers.

Owns bearer-token authentication (CurrentUser) and the extractor dependency that tests replace with
a fake.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.db import DbSession
from app.extractor import Extractor, extract_with_claude
from app.models import User
from app.services.auth import user_from_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def current_user(db: DbSession, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    """Return the user the bearer token belongs to.

    Raises a 401 with a WWW-Authenticate header when the token is missing, expired or forged, or
    its user no longer exists.
    """
    user = user_from_token(db, token)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_extractor() -> Extractor:
    """Return the function that reads order fields from a PDF.

    It is a dependency so tests can override it and never call the Claude API.
    """
    return extract_with_claude


CurrentUser = Annotated[User, Depends(current_user)]
