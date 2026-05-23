import asyncio
import os

from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from app.db import async_session_maker
from app.models.enums import ApprovalState, UserRole
from app.models.user import User


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

    password_helper = PasswordHelper()

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == admin_email))
        existing = result.scalars().first()

        if existing:
            existing.hashed_password = password_helper.hash(admin_password)
            existing.role = UserRole.ADMIN
            existing.approval_state = ApprovalState.APPROVED
            existing.is_active = True
            existing.is_superuser = True
            existing.is_verified = True
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

        await session.commit()
        print(f"Admin user {admin_email} ready.")


if __name__ == "__main__":
    asyncio.run(seed())
