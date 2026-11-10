"""Accounts, passwords and tokens.

Owns registration, argon2 password hashing, login checks and the HS256 JWTs that last 60 minutes.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User

ACCESS_TOKEN_LIFETIME = timedelta(minutes=60)
JWT_ALGORITHM = "HS256"
password_hasher = PasswordHasher()
# Checked when the email is unknown, so that login takes as long as for a wrong password
UNKNOWN_USER_HASH = password_hasher.hash(secrets.token_urlsafe(16))


class EmailTaken(Exception):
    """The email is already registered."""

    pass


def register_user(db: Session, email: str, password: str) -> User:
    """Create and return a user with the email in lower case and the password hashed.

    Raises EmailTaken when the email is already registered in any case.
    """
    user = User(email=email.lower(), password_hash=password_hasher.hash(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise EmailTaken from error
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the user for this email and password, or None if either is wrong.

    An unknown email is still checked against a throwaway hash, so it takes as long as a wrong
    password and does not reveal which emails have accounts.
    """
    user = db.scalar(select(User).where(User.email == email.lower()))
    try:
        password_hasher.verify(user.password_hash if user else UNKNOWN_USER_HASH, password)
    except VerifyMismatchError:
        return None
    return user


def create_access_token(user_id: uuid.UUID) -> str:
    """Return a signed JWT for the user that expires after 60 minutes."""
    claims = {"sub": str(user_id), "exp": datetime.now(UTC) + ACCESS_TOKEN_LIFETIME}
    return jwt.encode(claims, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def user_from_token(db: Session, token: str) -> User | None:
    """Return the user a token belongs to, or None if the token is not valid.

    Expired, forged and malformed tokens, and tokens without exp or sub, all give None.
    """
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        user_id = uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None
    return db.get(User, user_id)
