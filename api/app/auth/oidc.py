import os
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import APP_ENV, _is_placeholder

if TYPE_CHECKING:
    from httpx_oauth.clients.openid import OpenID

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:4321").rstrip("/")
OIDC_CALLBACK_URL = f"{APP_BASE_URL}/api/auth/oidc/callback"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Stored as oauth_account.oauth_name, so it must not change once accounts are
# linked. It is deliberately independent of OIDC_PROVIDER_NAME, which is a
# display string an operator may reword at any time.
DEFAULT_PROVIDER_KEY = "openid"


@dataclass(frozen=True)
class OidcSettings:
    enabled: bool
    client_id: str
    client_secret: str
    discovery_url: str
    provider_name: str
    provider_key: str
    associate_by_email: bool
    scopes: list[str]


def load_oidc_settings() -> OidcSettings:
    scopes_raw = os.getenv("OIDC_SCOPES", "openid email profile")
    scopes = [s.strip() for s in scopes_raw.split() if s.strip()]
    provider_name = os.getenv("OIDC_PROVIDER_NAME", "SSO").strip() or "SSO"
    provider_key_raw = os.getenv("OIDC_PROVIDER_KEY", "").strip()
    provider_key = provider_key_raw or DEFAULT_PROVIDER_KEY
    return OidcSettings(
        enabled=_env_bool("OIDC_ENABLED"),
        client_id=os.getenv("OIDC_CLIENT_ID", "").strip(),
        client_secret=os.getenv("OIDC_CLIENT_SECRET", "").strip(),
        discovery_url=os.getenv("OIDC_DISCOVERY_URL", "").strip(),
        provider_name=provider_name,
        provider_key=provider_key,
        associate_by_email=_env_bool("OIDC_ASSOCIATE_BY_EMAIL", default=False),
        scopes=scopes or ["openid", "email", "profile"],
    )


def validate_oidc_settings(settings: OidcSettings) -> list[str]:
    if not settings.enabled:
        return []

    errors: list[str] = []
    if _is_placeholder(settings.client_id):
        errors.append("OIDC_CLIENT_ID is missing or a placeholder")
    if _is_placeholder(settings.client_secret):
        errors.append("OIDC_CLIENT_SECRET is missing or a placeholder")
    if not settings.discovery_url:
        errors.append("OIDC_DISCOVERY_URL is required when OIDC_ENABLED=true")
    elif APP_ENV == "prod" and not settings.discovery_url.startswith("https://"):
        errors.append(
            f"OIDC_DISCOVERY_URL must start with https:// in production (got: {settings.discovery_url!r})"
        )
    return errors


@lru_cache(maxsize=1)
def get_oidc_client() -> "OpenID":
    from httpx_oauth.clients.openid import OpenID

    settings = load_oidc_settings()
    errors = validate_oidc_settings(settings)
    if errors:
        raise RuntimeError("; ".join(errors))
    return OpenID(
        settings.client_id,
        settings.client_secret,
        settings.discovery_url,
        name=settings.provider_key,
        base_scopes=settings.scopes,
    )
