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
from fastapi_users.exceptions import UserNotExists
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.models.enums import ApprovalState, NotificationFrequency, UserRole
from app.models.oauth_account import OAuthAccount
from app.models.system import PreApprovedEmail, SiteConfig
from app.models.user import NotificationPreference, User
from app.schemas.user import PUBLIC_NOTIFICATION_FREQUENCIES
from app.services.mailer import send_email

logger = logging.getLogger(__name__)

from app.config import APP_ENV, SECRET  # noqa: E402

# Cookie security flags. Secure=True requires HTTPS; in local dev we serve HTTP so we relax it.
_COOKIE_SECURE = APP_ENV != "dev"


async def apply_new_user_policies(
    session: AsyncSession,
    user: User,
    email_lower: str,
    *,
    email_opted_in: bool = False,
    frequency: NotificationFrequency = NotificationFrequency.ALL_UPDATES,
) -> None:
    if frequency not in PUBLIC_NOTIFICATION_FREQUENCIES:
        frequency = NotificationFrequency.ALL_UPDATES

    session.add(NotificationPreference(
        user_id=user.id,
        email_opted_in=email_opted_in,
        frequency=frequency,
    ))

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


def backfill_notification_preference(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    email_opted_in: bool = False,
    frequency: NotificationFrequency = NotificationFrequency.ALL_UPDATES,
) -> None:
    if frequency not in PUBLIC_NOTIFICATION_FREQUENCIES:
        frequency = NotificationFrequency.ALL_UPDATES
    session.add(NotificationPreference(
        user_id=user_id,
        email_opted_in=email_opted_in,
        frequency=frequency,
    ))


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def create(self, user_create, safe: bool = False, request: Optional[Request] = None):
        email_opted_in = bool(getattr(user_create, "email_opted_in", False))
        frequency = getattr(user_create, "notification_frequency", None) or NotificationFrequency.ALL_UPDATES

        user = await super().create(user_create, safe=safe, request=request)
        session = self.user_db.session
        email_lower = user_create.email.lower().strip()
        await apply_new_user_policies(
            session,
            user,
            email_lower,
            email_opted_in=email_opted_in,
            frequency=frequency,
        )
        await session.commit()
        await session.refresh(user)
        return user

    async def oauth_callback(
        self,
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: int | None = None,
        refresh_token: str | None = None,
        request: Request | None = None,
        *,
        associate_by_email: bool = False,
        is_verified_by_default: bool = False,
        display_name: str | None = None,
    ) -> User:
        existing_user: User | None = None
        try:
            existing_user = await self.get_by_oauth_account(oauth_name, account_id)
        except UserNotExists:
            if associate_by_email:
                try:
                    existing_user = await self.get_by_email(account_email)
                except UserNotExists:
                    pass

        user = await super().oauth_callback(
            oauth_name,
            access_token,
            account_id,
            account_email,
            expires_at,
            refresh_token,
            request,
            associate_by_email=associate_by_email,
            is_verified_by_default=is_verified_by_default,
        )
        session = self.user_db.session
        preference = (
            await session.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == user.id)
            )
        ).scalar_one_or_none()
        dirty = False
        if preference is None:
            if existing_user is None:
                email_lower = account_email.lower().strip()
                await apply_new_user_policies(session, user, email_lower)
            else:
                backfill_notification_preference(session, user.id)
            dirty = True
        if display_name and not user.display_name:
            user.display_name = display_name
            dirty = True
        if dirty:
            await session.commit()
            await session.refresh(user)
        return user

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info("User %s has registered.", user.id)
        base_url = os.getenv("APP_BASE_URL", "http://localhost:4321").rstrip("/")
        approval_url = f"{base_url}/admin/users"

        # approval_state may not be persisted yet (set after super().create() returns),
        # so determine pending status by querying config directly
        session = self.user_db.session
        email_lower = user.email.lower().strip()
        pre_approved = (await session.execute(
            select(PreApprovedEmail).where(PreApprovedEmail.email == email_lower)
        )).scalar_one_or_none()
        if pre_approved:
            pending = False
        else:
            config = (await session.execute(select(SiteConfig).limit(1))).scalar_one_or_none()
            pending = config is None or config.require_user_approval

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
        admins = (await session.execute(
            select(User).where(User.role == UserRole.ADMIN, User.is_active == True)
        )).unique().scalars().all()
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
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

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
