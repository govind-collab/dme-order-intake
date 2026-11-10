from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, status

from app.db import DbSession
from app.schemas import Token, UserCreate, UserRead
from app.services.auth import EmailTaken, authenticate, create_access_token, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, db: DbSession) -> UserRead:
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
    user = authenticate(db, username, password)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))
