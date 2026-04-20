from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

from app.auth.auth_config import fastapi_users_app, auth_backend
from app.routers import trips, stops, profiles, social, search

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';"
        return response

app = FastAPI(title="Goodpath API", description="Self-hosted RV travel journal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:8000", "http://127.0.0.1", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "api", "web"])
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(
    fastapi_users_app.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users_app.get_register_router(),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(trips.router)
app.include_router(stops.router)
app.include_router(profiles.router)
app.include_router(social.router)
app.include_router(search.router)

from app.routers.admin import trips as admin_trips, stops as admin_stops, media as admin_media
app.include_router(admin_trips.router, prefix="/admin")
app.include_router(admin_stops.router, prefix="/admin")
app.include_router(admin_media.router, prefix="/admin")

class HealthCheck(BaseModel):
    status: str
    component: str

@app.get("/api/health", response_model=HealthCheck)
async def health():
    return {"status": "ok", "component": "api_liveness"}

@app.get("/api/health/ready", response_model=HealthCheck)
async def health_ready():
    # In the future, this will check DB and Redis connectivity
    return {"status": "ok", "component": "api_readiness"}
