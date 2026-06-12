import ipaddress
import logging
import os
import time
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.auth.auth_config import APP_ENV, auth_backend, fastapi_users_app
from app.db import async_session_maker
from app.routers import account, journey, media, search, site_text, social, stops, trips
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.mailer import is_email_configured
from app.services.original_retention import cleanup_processed_originals

def _env_list(var: str, default: str) -> list[str]:
    raw = os.getenv(var, default)
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:4321").rstrip("/")


def _default_allowed_origins() -> list[str]:
    origins = [APP_BASE_URL]
    if APP_ENV == "dev":
        origins.append("http://localhost:8000")
    return origins


def _default_allowed_hosts() -> list[str]:
    parsed = urlparse(APP_BASE_URL)
    hosts = ["localhost", "127.0.0.1", "api", "web"]
    if parsed.hostname:
        hosts.append(parsed.hostname)
    return list(dict.fromkeys(hosts))


# Advanced deployments can override these directly, but normal installs only
# need APP_BASE_URL.
ALLOWED_ORIGINS = _env_list("ALLOWED_ORIGINS", ",".join(_default_allowed_origins()))
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", ",".join(_default_allowed_hosts()))
TRUSTED_PROXY_CIDRS = [
    ipaddress.ip_network(item, strict=False)
    for item in _env_list(
        "TRUSTED_PROXY_CIDRS",
        "127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
    )
]


# Exact paths exempted from Origin/Referer checks.
CSRF_EXEMPT_PATHS = {
    "/api/auth/jwt/login",
    "/api/health",
    "/api/health/ready",
}

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class SecurityHeadersMiddleware:
    """
    Security headers for API JSON and media-byte responses.

    Astro frontend is served separately from FastAPI, so its HTML pages should
    get CSP/HSTS from the Astro deployment reverse proxy. The CSP we set here
    applies only to /api/* and /media/* responses, non-HTML, so default-src
    'none' is an appropriate strict default.
    """

    DEFAULT_HEADERS = {
        "strict-transport-security": "max-age=31536000; includeSubDomains",
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": "geolocation=(), microphone=(), camera=(), interest-cohort=()",
        "content-security-policy": "default-src 'none'; frame-ancestors 'none';",
    }

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                existing = {
                    key.decode("latin1").lower()
                    for key, _value in message.get("headers", [])
                }
                message.setdefault("headers", [])
                for key, value in self.DEFAULT_HEADERS.items():
                    if key not in existing:
                        message["headers"].append((key.encode("latin1"), value.encode("latin1")))
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


class CsrfOriginMiddleware:
    """
    CSRF defense via Origin/Referer checks for unsafe browser methods.

    SameSite=Lax cookies are set in app/auth/auth_config.py. Non-browser clients
    that send neither Origin nor Referer are allowed.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]
        if method not in UNSAFE_METHODS or path in CSRF_EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }
        origin = headers.get("origin")
        referer = headers.get("referer")
        blocked_detail = None

        if origin is not None and origin not in ALLOWED_ORIGINS:
            logging.error("CSRF blocked: origin=%r, allowed=%s, path=%s", origin, ALLOWED_ORIGINS, path)
            blocked_detail = f"Origin not allowed: {origin}"
        elif referer is not None:
            parsed = urlparse(referer)
            referer_origin = f"{parsed.scheme}://{parsed.netloc}"
            if referer_origin not in ALLOWED_ORIGINS:
                logging.error("CSRF blocked: referer=%r, allowed=%s, path=%s", referer, ALLOWED_ORIGINS, path)
                blocked_detail = f"Referer not allowed: {referer_origin}"

        if blocked_detail is not None:
            response = JSONResponse(status_code=403, content={"detail": blocked_detail})
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


class RateLimitMiddleware:
    """Small in-process fixed-window limiter for public auth endpoints."""

    LIMITS = {
        "/api/auth/jwt/login": (10, 60),
        "/api/auth/register": (5, 300),
        "/api/auth/forgot-password": (5, 300),
    }

    def __init__(self, app):
        self.app = app
        self._buckets: dict[tuple[str, str], list[float]] = {}
        self._last_prune = 0.0

    def _client_host(self, scope) -> str:
        peer_host = (scope.get("client") or ("unknown",))[0]
        try:
            peer_ip = ipaddress.ip_address(peer_host)
        except ValueError:
            return peer_host

        if any(peer_ip in network for network in TRUSTED_PROXY_CIDRS):
            forwarded_for = dict(scope.get("headers") or []).get(b"x-forwarded-for")
            if forwarded_for:
                first_hop = forwarded_for.decode("latin1").split(",", 1)[0].strip()
                if first_hop:
                    return first_hop
        return peer_host

    def _prune(self, now: float) -> None:
        if now - self._last_prune < 60:
            return
        self._last_prune = now
        for key, timestamps in list(self._buckets.items()):
            path, _host = key
            limit_config = self.LIMITS.get(path)
            if not limit_config:
                del self._buckets[key]
                continue
            _limit, window_seconds = limit_config
            active = [ts for ts in timestamps if ts > now - window_seconds]
            if active:
                self._buckets[key] = active
            else:
                del self._buckets[key]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        limit_config = self.LIMITS.get(path)
        if limit_config is None:
            await self.app(scope, receive, send)
            return

        client_host = self._client_host(scope)
        key = (path, client_host)
        limit, window_seconds = limit_config
        now = time.monotonic()
        self._prune(now)
        attempts = [ts for ts in self._buckets.get(key, []) if ts > now - window_seconds]

        if len(attempts) >= limit:
            retry_after = max(1, int(window_seconds - (now - attempts[0])))
            response = JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again later."},
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return

        attempts.append(now)
        self._buckets[key] = attempts
        await self.app(scope, receive, send)


app = FastAPI(title="Postmarked API", description="Self-hosted travel journal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(CsrfOriginMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.on_event("startup")
async def cleanup_retained_originals_on_startup():
    async with async_session_maker() as session:
        await cleanup_processed_originals(session)


# Auth
app.include_router(
    fastapi_users_app.get_auth_router(auth_backend),
    prefix="/api/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users_app.get_register_router(UserRead, UserCreate),
    prefix="/api/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users_app.get_reset_password_router(),
    prefix="/api/auth",
    tags=["auth"],
)
# /api/users/me — lets the frontend check auth state without a custom endpoint
app.include_router(
    fastapi_users_app.get_users_router(UserRead, UserUpdate),
    prefix="/api/users",
    tags=["users"],
)
app.include_router(account.router, prefix="/api")


# Public read API
app.include_router(trips.router, prefix="/api")
app.include_router(stops.router, prefix="/api")
app.include_router(journey.router, prefix="/api")
app.include_router(social.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(site_text.router, prefix="/api")

# Media streaming is mounted at the root so a deployment proxy or the Astro
# middleware can route /media/* directly to the API.
app.include_router(media.router)


# Admin (mounted under /api/admin)
from app.routers.admin import (
    backup as admin_backup,
    imports as admin_imports,
    media as admin_media,
    pois as admin_pois,
    posts as admin_posts,
    site_config as admin_site_config,
    stops as admin_stops,
    site_text as admin_site_text,
    trips as admin_trips,
    users as admin_users,
)

app.include_router(admin_trips.router, prefix="/api/admin")
app.include_router(admin_stops.router, prefix="/api/admin")
app.include_router(admin_pois.router, prefix="/api/admin")
app.include_router(admin_media.router, prefix="/api/admin")
app.include_router(admin_posts.router, prefix="/api/admin")
app.include_router(admin_imports.router, prefix="/api/admin")
app.include_router(admin_users.router, prefix="/api/admin")
app.include_router(admin_site_config.router, prefix="/api/admin")
app.include_router(admin_site_text.router, prefix="/api/admin")
app.include_router(admin_backup.router, prefix="/api/admin")


class AppConfig(BaseModel):
    email_enabled: bool
    require_user_approval: bool


@app.get("/api/config", response_model=AppConfig)
async def app_config():
    from sqlalchemy import select

    from app.models.system import SiteConfig

    require_approval = True
    async with async_session_maker() as session:
        config = (await session.execute(select(SiteConfig).limit(1))).scalar_one_or_none()
        if config is not None:
            require_approval = config.require_user_approval
    return {"email_enabled": is_email_configured(), "require_user_approval": require_approval}


class HealthCheck(BaseModel):
    status: str
    component: str


@app.get("/api/health", response_model=HealthCheck)
async def health():
    return {"status": "ok", "component": "api_liveness"}


@app.get("/api/health/ready", response_model=HealthCheck)
async def health_ready():
    async with async_session_maker() as session:
        await session.execute(text("select 1"))
    return {"status": "ok", "component": "api_readiness"}
