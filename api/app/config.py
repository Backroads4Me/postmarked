import os
import sys

APP_ENV = os.getenv("APP_ENV", "dev").lower()
_DEV_SECRET_FALLBACK = "dev-only-change-me-not-for-production-use"
_PLACEHOLDERS = frozenset({"changeme", "change-me", ""})


def _is_placeholder(v: str | None) -> bool:
    return not v or v.strip().lower() in _PLACEHOLDERS


def validate_env() -> None:
    """Validate required env vars. Prints all errors and exits on failure."""
    if APP_ENV not in ("dev", "prod"):
        print(f"[postmarked] ERROR: APP_ENV must be 'dev' or 'prod', got {APP_ENV!r}", file=sys.stderr)
        sys.exit(1)

    if APP_ENV == "dev":
        print(
            "\n"
            "[postmarked] *** DEVELOPMENT MODE — not safe for public use ***\n"
            "             Set APP_ENV=prod before deploying.\n",
            file=sys.stderr,
        )
        return

    errors: list[str] = []

    if _is_placeholder(os.getenv("SECRET_KEY")):
        errors.append(
            "SECRET_KEY is missing or a placeholder — "
            "generate: python3 -c 'import secrets; print(secrets.token_urlsafe(64))'"
        )

    base_url = os.getenv("APP_BASE_URL", "")
    if not base_url.startswith("https://"):
        errors.append(f"APP_BASE_URL must start with https:// in production (got: {base_url!r})")

    if _is_placeholder(os.getenv("ADMIN_PASSWORD")):
        errors.append("ADMIN_PASSWORD is missing or a placeholder")

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url or "changeme" in db_url:
        errors.append("DATABASE_URL is missing or contains a placeholder password")

    if errors:
        print("\n[postmarked] FATAL: Production configuration is incomplete:\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("\n  Set APP_ENV=dev to skip these checks during local development.\n", file=sys.stderr)
        sys.exit(1)


_raw_secret = os.getenv("SECRET_KEY")
SECRET: str = (
    _raw_secret if (_raw_secret and not _is_placeholder(_raw_secret)) else _DEV_SECRET_FALLBACK
)
