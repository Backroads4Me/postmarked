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
from fastapi_users.exceptions import UserAlreadyExists, UserNotExists
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

from app.auth.auth_config import (
    SECRET,
    auth_backend,
    current_active_user,
    fastapi_users_app,
    get_user_manager,
)
from app.config import APP_ENV
from app.auth.oidc import OIDC_CALLBACK_URL, get_oidc_client, load_oidc_settings
from app.models.user import User

logger = logging.getLogger(__name__)

_COOKIE_SECURE = APP_ENV != "dev"
_NEXT_STATE_KEY = "next"
# Set when the flow was started from the account page by a signed-in user, who
# is linking an IdP identity to the account they already control.
_LINK_STATE_KEY = "link"

current_user_optional = fastapi_users_app.current_user(optional=True, active=True)

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


def _login_error_redirect(error_code: str) -> RedirectResponse:
    """End a failed OIDC attempt: redirect and clear the CSRF cookie.

    The cookie otherwise outlives every failed attempt for its full hour,
    leaving a still-valid (cookie, state) pair in the browser.
    """
    response = RedirectResponse(
        url=_login_error_url(error_code), status_code=status.HTTP_302_FOUND
    )
    response.delete_cookie(CSRF_TOKEN_COOKIE_NAME, path="/")
    return response


def _account_url(**params: str) -> str:
    base_url = os.getenv("APP_BASE_URL", "http://localhost:4321").rstrip("/")
    return f"{base_url}/account?{urlencode(params)}"


async def _authorize_redirect(oidc_client, state_data: dict) -> RedirectResponse:
    """Send the browser to the IdP with a signed state and a CSRF cookie."""
    csrf_token = generate_csrf_token()
    state = generate_state_token({CSRF_TOKEN_KEY: csrf_token, **state_data}, SECRET)
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


def _safe_next_path(raw: str | None) -> str:
    if not raw:
        return "/"
    if not raw.startswith("/") or raw.startswith("//"):
        return "/"
    return raw


def _copy_response_cookies(source, target: RedirectResponse) -> None:
    for cookie in source.headers.getlist("set-cookie"):
        target.headers.append("set-cookie", cookie)


def _parse_email_verified(raw: object) -> bool | None:
    """Read the OIDC email_verified claim, which some providers send as a string."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in ("1", "true", "yes"):
            return True
        if value in ("0", "false", "no"):
            return False
    return None


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
        return _login_error_redirect("oauth_failed")

    if oidc_client is None:
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    return await _authorize_redirect(
        oidc_client, {_NEXT_STATE_KEY: _safe_next_path(next)}
    )


@router.get("/link/start")
async def oidc_link_start(user: User = Depends(current_active_user)):
    """Begin linking an IdP identity to the account the caller is signed in as.

    Ownership of the local account is proved by the session, so no trust is
    placed in the email address the IdP returns.
    """
    try:
        oidc_client, _ = _ensure_oidc_client()
    except Exception:
        logger.exception("OIDC client initialization failed")
        return RedirectResponse(
            url=_account_url(error="link_failed"), status_code=status.HTTP_302_FOUND
        )

    if oidc_client is None:
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    return await _authorize_redirect(oidc_client, {_LINK_STATE_KEY: str(user.id)})


async def _complete_link(
    oidc_client,
    token: dict,
    link_user_id: str,
    linking_user: User | None,
    user_manager: BaseUserManager[User, uuid.UUID],
) -> RedirectResponse:
    """Attach an IdP identity to the signed-in account that started the flow."""
    # The state is signed, but it is replayable by anyone who obtains the URL.
    # Requiring a live session for that exact user is what makes the link safe.
    if linking_user is None or str(linking_user.id) != link_user_id:
        logger.warning("OIDC link rejected: session does not match the linking account")
        return RedirectResponse(
            url=_account_url(error="link_mismatch"), status_code=status.HTTP_302_FOUND
        )

    try:
        account_id, account_email = await oidc_client.get_id_email(token["access_token"])
    except Exception:
        logger.exception("OIDC get_id_email failed during link")
        return RedirectResponse(
            url=_account_url(error="link_failed"), status_code=status.HTTP_302_FOUND
        )

    if account_id is None:
        return RedirectResponse(
            url=_account_url(error="link_failed"), status_code=status.HTTP_302_FOUND
        )

    try:
        existing = await user_manager.get_by_oauth_account(oidc_client.name, account_id)
    except UserNotExists:
        existing = None
    if existing is not None and existing.id != linking_user.id:
        return RedirectResponse(
            url=_account_url(error="link_taken"), status_code=status.HTTP_302_FOUND
        )

    if existing is None:
        await user_manager.user_db.add_oauth_account(
            linking_user,
            {
                "oauth_name": oidc_client.name,
                "access_token": token["access_token"],
                "account_id": account_id,
                "account_email": account_email or linking_user.email,
                "expires_at": token.get("expires_at"),
                "refresh_token": token.get("refresh_token"),
            },
        )

    response = RedirectResponse(
        url=_account_url(linked="1"), status_code=status.HTTP_302_FOUND
    )
    response.delete_cookie(CSRF_TOKEN_COOKIE_NAME, path="/")
    return response


@router.get("/callback")
async def oidc_callback(
    request: Request,
    user_manager: BaseUserManager[User, uuid.UUID] = Depends(get_user_manager),
    strategy: Strategy[User, uuid.UUID] = Depends(auth_backend.get_strategy),
    linking_user: User | None = Depends(current_user_optional),
):
    try:
        oidc_client, oauth2_authorize_callback = _ensure_oidc_client()
    except Exception:
        logger.exception("OIDC client initialization failed")
        return _login_error_redirect("oauth_failed")

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
        return _login_error_redirect("oauth_failed")
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else None
        return _login_error_redirect(_detail_to_error_code(detail))

    try:
        # PyJWTError is the common base: a token signed with the same secret but
        # a different audience raises InvalidAudienceError, and the app mints
        # session and reset tokens with that secret.
        state_data = decode_jwt(state, SECRET, [STATE_TOKEN_AUDIENCE])
    except jwt.PyJWTError:
        return _login_error_redirect("oauth_failed")

    cookie_csrf_token = request.cookies.get(CSRF_TOKEN_COOKIE_NAME)
    state_csrf_token = state_data.get(CSRF_TOKEN_KEY)
    if (
        not cookie_csrf_token
        or not state_csrf_token
        or not secrets.compare_digest(cookie_csrf_token, state_csrf_token)
    ):
        return _login_error_redirect("oauth_failed")

    link_user_id = state_data.get(_LINK_STATE_KEY)
    if link_user_id is not None:
        return await _complete_link(
            oidc_client, token, link_user_id, linking_user, user_manager
        )

    next_path = _safe_next_path(state_data.get(_NEXT_STATE_KEY))
    base_url = os.getenv("APP_BASE_URL", "http://localhost:4321").rstrip("/")
    success_url = f"{base_url}{next_path}"

    try:
        account_id, account_email = await oidc_client.get_id_email(token["access_token"])
    except Exception:
        logger.exception("OIDC get_id_email failed")
        return _login_error_redirect("oauth_no_email")

    if account_email is None:
        return _login_error_redirect("oauth_no_email")

    display_name: str | None = None
    email_verified: bool | None = None
    try:
        profile = await oidc_client.get_profile(token["access_token"])
        display_name = profile.get("name") or profile.get("preferred_username")
        if display_name is not None:
            display_name = str(display_name).strip() or None
        email_verified = _parse_email_verified(profile.get("email_verified"))
    except Exception:
        logger.debug("OIDC profile fetch failed; continuing without display_name", exc_info=True)

    # Linking by email hands an existing local account to whoever controls the
    # address at the IdP, so an explicit denial from the provider overrides the
    # operator's opt-in.
    associate_by_email = _settings.associate_by_email
    if associate_by_email and email_verified is False:
        logger.warning(
            "OIDC provider reports email_verified=false for %s; refusing to associate by email",
            account_email,
        )
        associate_by_email = False
    elif associate_by_email and email_verified is None:
        logger.warning(
            "OIDC provider returned no email_verified claim; associating by email on trust"
        )

    try:
        user = await user_manager.oauth_callback(
            oidc_client.name,
            token["access_token"],
            account_id,
            account_email,
            token.get("expires_at"),
            token.get("refresh_token"),
            request,
            associate_by_email=associate_by_email,
            is_verified_by_default=True,
            display_name=display_name,
        )
    except UserAlreadyExists:
        return _login_error_redirect("oauth_exists")
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else None
        return _login_error_redirect(_detail_to_error_code(detail))

    if not user.is_active:
        return _login_error_redirect("oauth_pending")

    login_response = await auth_backend.login(strategy, user)
    await user_manager.on_after_login(user, request, login_response)

    redirect = RedirectResponse(url=success_url, status_code=status.HTTP_302_FOUND)
    _copy_response_cookies(login_response, redirect)
    redirect.delete_cookie(CSRF_TOKEN_COOKIE_NAME, path="/")
    return redirect
