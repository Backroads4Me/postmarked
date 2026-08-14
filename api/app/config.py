import os
import secrets
import sys

APP_ENV = os.getenv("APP_ENV", "dev").lower()
_PLACEHOLDERS = frozenset({"changeme", "change-me", ""})
_MIN_SECRET_LENGTH = 32


def _is_placeholder(v: str | None) -> bool:
    return not v or v.strip().lower() in _PLACEHOLDERS


def _is_weak_secret(v: str | None) -> bool:
    """Stricter than _is_placeholder, for values that sign tokens.

    Applied only to SECRET_KEY. Identifiers such as OIDC_CLIENT_ID are public
    by design and carry no entropy requirement.
    """
    if _is_placeholder(v):
        return True
    stripped = v.strip()
    return len(stripped) < _MIN_SECRET_LENGTH or len(set(stripped)) < 8


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

    if _is_weak_secret(os.getenv("SECRET_KEY")):
        errors.append(
            "SECRET_KEY is missing, a placeholder, or too weak — "
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

    from app.auth.oidc import load_oidc_settings, validate_oidc_settings

    oidc_errors = validate_oidc_settings(load_oidc_settings())
    errors.extend(oidc_errors)

    if errors:
        print("\n[postmarked] FATAL: Production configuration is incomplete:\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("\n  Set APP_ENV=dev to skip these checks during local development.\n", file=sys.stderr)
        sys.exit(1)


_raw_secret = os.getenv("SECRET_KEY")
# Generated per process rather than a shared constant: a dev instance that ends
# up reachable must not sign session cookies, reset tokens, and OIDC state with
# a value anybody can read out of the source. The cost is that sessions do not
# survive a restart without a real SECRET_KEY, which is the intended nudge.
SECRET: str = (
    _raw_secret if not _is_weak_secret(_raw_secret) else secrets.token_urlsafe(64)
)
