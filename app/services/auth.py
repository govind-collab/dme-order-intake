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
    pass


def register_user(db: Session, email: str, password: str) -> User:
    user = User(email=email.lower(), password_hash=password_hasher.hash(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise EmailTaken from error
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    try:
        password_hasher.verify(user.password_hash if user else UNKNOWN_USER_HASH, password)
    except VerifyMismatchError:
        return None
    return user


def create_access_token(user_id: uuid.UUID) -> str:
    claims = {"sub": str(user_id), "exp": datetime.now(UTC) + ACCESS_TOKEN_LIFETIME}
    return jwt.encode(claims, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def user_from_token(db: Session, token: str) -> User | None:
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
