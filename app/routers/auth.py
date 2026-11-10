"""Routes for creating an account and logging in.

Owns POST /auth/register and POST /auth/token.
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, status

from app.db import DbSession
from app.schemas import Token, UserCreate, UserRead
from app.services.auth import EmailTaken, authenticate, create_access_token, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, db: DbSession) -> UserRead:
    """Create an account and return it without the password.

    The email is stored in lower case, so the same address in another case gets a 409. Passwords
    need 8 to 128 characters.
    """
    try:
        user = register_user(db, body.email, body.password)
    except EmailTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
    return UserRead.model_validate(user)


@router.post("/token")
def issue_token(
    db: DbSession,
    username: Annotated[str, Form(max_length=254)],
    password: Annotated[str, Form(max_length=128)],
) -> Token:
    """Log in with email and password and return a bearer token valid for 60 minutes.

    Takes a form body, with the email in `username`, so the Authorize button in /docs works. A
    wrong password and an unknown email get the same 401 and take about the same time.
    """
    user = authenticate(db, username, password)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))
