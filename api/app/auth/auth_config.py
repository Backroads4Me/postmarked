import os
import uuid
import logging
from typing import Optional
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.db import get_async_session
from app.models.user import User

logger = logging.getLogger(__name__)

APP_ENV = os.getenv("APP_ENV", "dev").lower()
_DEV_SECRET_FALLBACK = "dev-only-change-me-not-for-production-use"

_secret = os.getenv("SECRET_KEY")
if not _secret:
    if APP_ENV == "dev":
        logger.warning(
            "[auth] WARNING: SECRET_KEY not set; using insecure dev fallback. "
            "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(64))'"
        )
        _secret = _DEV_SECRET_FALLBACK
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable is required when APP_ENV is not 'dev'. "
            "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(64))'"
        )

SECRET = _secret

# Cookie security flags. Secure=True requires HTTPS; in local dev we serve HTTP so we relax it.
_COOKIE_SECURE = APP_ENV != "dev"


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info("User %s has registered.", user.id)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info("Password reset requested for user %s.", user.id)

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info("Verification requested for user %s.", user.id)

async def get_user_db(session=Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)

async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)

cookie_transport = CookieTransport(
    cookie_name="postmarked_session",
    cookie_max_age=60 * 60 * 24 * 7,  # 7 days
    cookie_secure=_COOKIE_SECURE,
    cookie_httponly=True,
    cookie_samesite="lax",
)

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=60 * 60 * 24 * 7)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users_app = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users_app.current_user(active=True)
