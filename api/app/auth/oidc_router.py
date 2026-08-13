import os
import secrets
import uuid
import logging
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi_users import BaseUserManager
from fastapi_users.authentication import Strategy
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.jwt import decode_jwt
from fastapi_users.router.common import ErrorCode
from fastapi_users.router.oauth import (
    CSRF_TOKEN_COOKIE_NAME,
    CSRF_TOKEN_KEY,
    STATE_TOKEN_AUDIENCE,
    generate_csrf_token,
    generate_state_token,
)
from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback, OAuth2AuthorizeCallbackError

from app.auth.auth_config import SECRET, auth_backend, get_user_manager
from app.config import APP_ENV
from app.auth.oidc import OIDC_CALLBACK_URL, get_oidc_client, load_oidc_settings
from app.models.user import User

logger = logging.getLogger(__name__)

_COOKIE_SECURE = APP_ENV != "dev"
_NEXT_STATE_KEY = "next"

router = APIRouter()

_settings = load_oidc_settings()
_oidc_client = None
_oauth2_authorize_callback = None


def _ensure_oidc_client():
    """Lazy-init so a down IdP cannot block API process import/startup."""
    global _oidc_client, _oauth2_authorize_callback
    if not _settings.enabled:
        return None, None
    if _oidc_client is None:
        _oidc_client = get_oidc_client()
        _oauth2_authorize_callback = OAuth2AuthorizeCallback(
            _oidc_client,
            redirect_url=OIDC_CALLBACK_URL,
        )
    return _oidc_client, _oauth2_authorize_callback


def _login_error_url(error_code: str) -> str:
    base_url = os.getenv("APP_BASE_URL", "http://localhost:4321").rstrip("/")
    return f"{base_url}/auth/login?{urlencode({'error': error_code})}"


def _safe_next_path(raw: str | None) -> str:
    if not raw:
        return "/"
    if not raw.startswith("/") or raw.startswith("//"):
        return "/"
    return raw


def _copy_response_cookies(source, target: RedirectResponse) -> None:
    for cookie in source.headers.getlist("set-cookie"):
        target.headers.append("set-cookie", cookie)


def _detail_to_error_code(detail: str | None) -> str:
    if detail == ErrorCode.LOGIN_BAD_CREDENTIALS:
        return "oauth_pending"
    if detail == ErrorCode.OAUTH_USER_ALREADY_EXISTS:
        return "oauth_exists"
    if detail == ErrorCode.OAUTH_NOT_AVAILABLE_EMAIL:
        return "oauth_no_email"
    return "oauth_failed"


@router.get("/start")
async def oidc_start(
    request: Request,
    next: str = Query("/", alias="next"),
):
    try:
        oidc_client, _ = _ensure_oidc_client()
    except Exception:
        logger.exception("OIDC client initialization failed")
        return RedirectResponse(url=_login_error_url("oauth_failed"), status_code=status.HTTP_302_FOUND)

    if oidc_client is None:
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    next_path = _safe_next_path(next)
    csrf_token = generate_csrf_token()
    state_data = {CSRF_TOKEN_KEY: csrf_token, _NEXT_STATE_KEY: next_path}
    state = generate_state_token(state_data, SECRET)
    authorization_url = await oidc_client.get_authorization_url(
        OIDC_CALLBACK_URL,
        state,
        _settings.scopes,
    )

    response = RedirectResponse(url=authorization_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        CSRF_TOKEN_COOKIE_NAME,
        csrf_token,
        max_age=3600,
        path="/",
        secure=_COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/callback")
async def oidc_callback(
    request: Request,
    user_manager: BaseUserManager[User, uuid.UUID] = Depends(get_user_manager),
    strategy: Strategy[User, uuid.UUID] = Depends(auth_backend.get_strategy),
):
    try:
        oidc_client, oauth2_authorize_callback = _ensure_oidc_client()
    except Exception:
        logger.exception("OIDC client initialization failed")
        return RedirectResponse(url=_login_error_url("oauth_failed"), status_code=status.HTTP_302_FOUND)

    if oidc_client is None or oauth2_authorize_callback is None:
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    try:
        code = request.query_params.get("code")
        state_param = request.query_params.get("state")
        error = request.query_params.get("error")
        token, state = await oauth2_authorize_callback(
            request, code=code, state=state_param, error=error
        )
    except OAuth2AuthorizeCallbackError:
        return RedirectResponse(url=_login_error_url("oauth_failed"), status_code=status.HTTP_302_FOUND)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else None
        return RedirectResponse(
            url=_login_error_url(_detail_to_error_code(detail)),
            status_code=status.HTTP_302_FOUND,
        )

    try:
        state_data = decode_jwt(state, SECRET, [STATE_TOKEN_AUDIENCE])
    except jwt.DecodeError:
        return RedirectResponse(url=_login_error_url("oauth_failed"), status_code=status.HTTP_302_FOUND)
    except jwt.ExpiredSignatureError:
        return RedirectResponse(url=_login_error_url("oauth_failed"), status_code=status.HTTP_302_FOUND)

    cookie_csrf_token = request.cookies.get(CSRF_TOKEN_COOKIE_NAME)
    state_csrf_token = state_data.get(CSRF_TOKEN_KEY)
    if (
        not cookie_csrf_token
        or not state_csrf_token
        or not secrets.compare_digest(cookie_csrf_token, state_csrf_token)
    ):
        return RedirectResponse(url=_login_error_url("oauth_failed"), status_code=status.HTTP_302_FOUND)

    next_path = _safe_next_path(state_data.get(_NEXT_STATE_KEY))
    base_url = os.getenv("APP_BASE_URL", "http://localhost:4321").rstrip("/")
    success_url = f"{base_url}{next_path}"

    try:
        account_id, account_email = await oidc_client.get_id_email(token["access_token"])
    except Exception:
        logger.exception("OIDC get_id_email failed")
        return RedirectResponse(url=_login_error_url("oauth_no_email"), status_code=status.HTTP_302_FOUND)

    if account_email is None:
        return RedirectResponse(url=_login_error_url("oauth_no_email"), status_code=status.HTTP_302_FOUND)

    display_name: str | None = None
    try:
        profile = await oidc_client.get_profile(token["access_token"])
        display_name = profile.get("name") or profile.get("preferred_username")
        if display_name is not None:
            display_name = str(display_name).strip() or None
    except Exception:
        logger.debug("OIDC profile fetch failed; continuing without display_name", exc_info=True)

    try:
        user = await user_manager.oauth_callback(
            oidc_client.name,
            token["access_token"],
            account_id,
            account_email,
            token.get("expires_at"),
            token.get("refresh_token"),
            request,
            associate_by_email=_settings.associate_by_email,
            is_verified_by_default=True,
            display_name=display_name,
        )
    except UserAlreadyExists:
        return RedirectResponse(url=_login_error_url("oauth_exists"), status_code=status.HTTP_302_FOUND)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else None
        return RedirectResponse(
            url=_login_error_url(_detail_to_error_code(detail)),
            status_code=status.HTTP_302_FOUND,
        )

    if not user.is_active:
        return RedirectResponse(url=_login_error_url("oauth_pending"), status_code=status.HTTP_302_FOUND)

    login_response = await auth_backend.login(strategy, user)
    await user_manager.on_after_login(user, request, login_response)

    redirect = RedirectResponse(url=success_url, status_code=status.HTTP_302_FOUND)
    _copy_response_cookies(login_response, redirect)
    redirect.delete_cookie(CSRF_TOKEN_COOKIE_NAME, path="/")
    return redirect
