import os
import uuid
import logging
from html import escape
from urllib.parse import quote
from typing import Optional
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from sqlalchemy import select

from app.db import get_async_session
from app.models.enums import ApprovalState, NotificationFrequency, UserRole
from app.models.system import PreApprovedEmail, SiteConfig
from app.models.user import NotificationPreference, User
from app.schemas.user import PUBLIC_NOTIFICATION_FREQUENCIES
from app.services.mailer import send_email

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

    async def create(self, user_create, safe: bool = False, request: Optional[Request] = None):
        frequency = getattr(user_create, "notification_frequency", None) or NotificationFrequency.NONE
        if frequency not in PUBLIC_NOTIFICATION_FREQUENCIES:
            frequency = NotificationFrequency.NONE

        user = await super().create(user_create, safe=safe, request=request)
        self.user_db.session.add(NotificationPreference(user_id=user.id, frequency=frequency))

        session = self.user_db.session
        email_lower = user_create.email.lower().strip()

        pre_approved = (await session.execute(
            select(PreApprovedEmail).where(PreApprovedEmail.email == email_lower)
        )).scalar_one_or_none()

        if pre_approved:
            user.approval_state = ApprovalState.APPROVED
        else:
            config = (await session.execute(select(SiteConfig).limit(1))).scalar_one_or_none()
            if config is not None and not config.require_user_approval:
                user.approval_state = ApprovalState.APPROVED
            else:
                user.is_active = False

        await self.user_db.session.commit()
        await self.user_db.session.refresh(user)
        return user

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info("User %s has registered.", user.id)
        base_url = os.getenv("APP_BASE_URL", "http://localhost:4321").rstrip("/")
        approval_url = f"{base_url}/admin/users"
        pending = user.approval_state == ApprovalState.PENDING
        name = user.display_name or "(no name)"
        status_text = "is pending your approval" if pending else "was automatically approved"
        subject = f"New registration: {name}"
        text = (
            f"{name} ({user.email}) has registered on Postmarked and {status_text}.\n\n"
            f"Manage users: {approval_url}\n"
        )
        html = (
            f"<p><strong>{escape(name)}</strong> ({escape(user.email)}) has registered on Postmarked "
            f"and <strong>{escape(status_text)}</strong>.</p>"
            f'<p><a href="{approval_url}">Manage users</a></p>'
        )
        session = self.user_db.session
        admins = (await session.execute(
            select(User).where(User.role == UserRole.ADMIN, User.is_active == True)
        )).scalars().all()
        for admin in admins:
            send_email(admin.email, subject, text, html)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info("Password reset requested for user %s.", user.id)
        base_url = os.getenv("APP_BASE_URL", "http://localhost:4321").rstrip("/")
        reset_url = f"{base_url}/auth/reset-password?token={quote(token)}"
        send_email(
            user.email,
            "Reset your Postmarked password",
            (
                "A password reset was requested for your Postmarked account.\n\n"
                f"Reset your password here: {reset_url}\n\n"
                "If you did not request this, you can ignore this email."
            ),
            (
                "<p>A password reset was requested for your Postmarked account.</p>"
                f'<p><a href="{reset_url}">Reset your password</a></p>'
                "<p>If you did not request this, you can ignore this email.</p>"
            ),
        )

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
