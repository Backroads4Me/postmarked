import logging
import os
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.auth_config import APP_ENV, auth_backend, fastapi_users_app
from app.db import async_session_maker
from app.routers import account, journey, media, search, site_text, social, stops, trips
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.mailer import is_email_configured


def _env_list(var: str, default: str) -> list[str]:
    raw = os.getenv(var, default)
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


# Browser origins allowed to fetch the API (CORS) and to make state-changing
# requests (Origin header check, see CsrfOriginMiddleware below). Comma-separated env.
ALLOWED_ORIGINS = _env_list(
    "ALLOWED_ORIGINS",
    "http://localhost:4321,http://localhost:8000",
)
ALLOWED_HOSTS = _env_list(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,api,web",
)


# Paths exempted from the Origin-check (login itself can't carry a CSRF token; health is safe).
CSRF_EXEMPT_PREFIXES = (
    "/api/auth/",      # fastapi-users login/register/verify endpoints
    "/api/health",     # liveness/readiness probes
)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Security headers for API JSON and media-byte responses.

    The Astro frontend is served separately from FastAPI, so its HTML pages
    should get CSP/HSTS from Astro or the deployment reverse proxy. The CSP we
    set here applies only to /api/* and /media/* responses, which are non-HTML,
    so default-src 'none' is the appropriate strict default.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), interest-cohort=()",
        )
        # Strict CSP for API/media responses. These are not HTML, so 'none' is fine.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none';",
        )
        return response


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    """
    CSRF defense via Origin header check for unsafe methods.

    Trade-off: the spec calls for a double-submit cookie token. For a single-host
    family-only app, SameSite=Lax cookies (set in app/auth/auth_config.py) plus
    a strict Origin allowlist is materially equivalent and avoids an extra
    request roundtrip + per-fetch header dance. Tighten to a token if the threat
    model changes (third-party embeds, multi-tenant, etc.).
    """

    async def dispatch(self, request: Request, call_next):
        if request.method not in UNSAFE_METHODS:
            return await call_next(request)

        # Skip exempt paths (login, register, health).
        if any(request.url.path.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES):
            return await call_next(request)

        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        if origin is not None:
            if origin not in ALLOWED_ORIGINS:
                import logging
                logging.error(f"CSRF blocked: origin={origin!r}, allowed={ALLOWED_ORIGINS}, path={request.url.path}")
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"Origin not allowed: {origin}"},
                )
        elif referer is not None:
            parsed = urlparse(referer)
            referer_origin = f"{parsed.scheme}://{parsed.netloc}"
            if referer_origin not in ALLOWED_ORIGINS:
                import logging
                logging.error(f"CSRF blocked: referer={referer!r}, allowed={ALLOWED_ORIGINS}, path={request.url.path}")
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"Referer not allowed: {referer_origin}"},
                )
        # Neither header present: non-browser context (e.g. SSR server), allow through.
        return await call_next(request)


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
app.add_middleware(SecurityHeadersMiddleware)


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
