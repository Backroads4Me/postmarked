import asyncio
import os
import sys

from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from app.config import APP_ENV
from app.db import async_session_maker
from app.models.enums import ApprovalState, UserRole
from app.models.user import User

_PLACEHOLDERS = frozenset({"changeme", "change-me", ""})


def _is_placeholder(v: str | None) -> bool:
    return not v or v.strip().lower() in _PLACEHOLDERS


async def seed():
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD")
    admin_display_name = os.getenv("ADMIN_DISPLAY_NAME")

    if not admin_email:
        raise RuntimeError("ADMIN_EMAIL must be set in .env")
    if not admin_password:
        raise RuntimeError("ADMIN_PASSWORD must be set in .env")
    if not admin_display_name:
        raise RuntimeError("ADMIN_DISPLAY_NAME must be set in .env")

    if APP_ENV == "prod" and _is_placeholder(admin_password):
        print("[seed] ERROR: ADMIN_PASSWORD is a placeholder. Set a real password before deploying.", file=sys.stderr)
        sys.exit(1)

    password_helper = PasswordHelper()

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == admin_email))
        existing = result.scalars().first()

        if existing:
            if APP_ENV == "dev":
                existing.hashed_password = password_helper.hash(admin_password)
                existing.role = UserRole.ADMIN
                existing.approval_state = ApprovalState.APPROVED
                existing.is_active = True
                existing.is_superuser = True
                existing.is_verified = True
                print(f"Admin user {admin_email} updated (dev mode).")
            else:
                existing.role = UserRole.ADMIN
                existing.approval_state = ApprovalState.APPROVED
                existing.is_active = True
                existing.is_superuser = True
                existing.is_verified = True
                print(f"Admin user {admin_email} verified (password not changed in prod).")
                print("  To reset the password, temporarily set APP_ENV=dev and restart.")
        else:
            session.add(User(
                email=admin_email,
                hashed_password=password_helper.hash(admin_password),
                display_name=admin_display_name,
                role=UserRole.ADMIN,
                approval_state=ApprovalState.APPROVED,
                is_active=True,
                is_superuser=True,
                is_verified=True,
            ))
            print(f"Admin user {admin_email} created.")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
