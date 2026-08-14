import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi_users.exceptions import UserNotExists

from app.auth.auth_config import UserManager, apply_new_user_policies
from app.auth.oidc import load_oidc_settings, validate_oidc_settings
from app.auth.oidc_router import _ensure_oidc_client, _parse_email_verified, _safe_next_path
from app.models.enums import ApprovalState
from app.routers.admin.users import AdminProfileUpdate, update_user_profile


def test_load_oidc_settings_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OIDC_ENABLED", raising=False)
    monkeypatch.delenv("OIDC_ASSOCIATE_BY_EMAIL", raising=False)
    settings = load_oidc_settings()
    assert settings.enabled is False
    assert settings.associate_by_email is False


def test_load_oidc_settings_enabled(monkeypatch):
    monkeypatch.setenv("OIDC_ENABLED", "true")
    monkeypatch.setenv("OIDC_CLIENT_ID", "client-id")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("OIDC_DISCOVERY_URL", "https://idp.example.com/.well-known/openid-configuration")
    monkeypatch.setenv("OIDC_PROVIDER_NAME", "Company SSO")
    monkeypatch.delenv("OIDC_ASSOCIATE_BY_EMAIL", raising=False)
    monkeypatch.delenv("OIDC_PROVIDER_KEY", raising=False)
    settings = load_oidc_settings()
    assert settings.enabled is True
    assert settings.provider_name == "Company SSO"
    # The stored key must not track the display name, which operators reword.
    assert settings.provider_key == "openid"
    assert settings.associate_by_email is False


def test_load_oidc_settings_provider_key_override(monkeypatch):
    monkeypatch.setenv("OIDC_PROVIDER_NAME", "Company SSO")
    monkeypatch.setenv("OIDC_PROVIDER_KEY", "azure-ad")
    settings = load_oidc_settings()
    assert settings.provider_key == "azure-ad"


@pytest.mark.parametrize(
    "raw,expected",
    [
        (True, True),
        (False, False),
        ("true", True),
        ("false", False),
        ("True", True),
        (None, None),
        ("maybe", None),
        (1, None),
    ],
)
def test_parse_email_verified(raw, expected):
    assert _parse_email_verified(raw) is expected


def test_load_oidc_settings_associate_by_email_opt_in(monkeypatch):
    monkeypatch.setenv("OIDC_ASSOCIATE_BY_EMAIL", "true")
    settings = load_oidc_settings()
    assert settings.associate_by_email is True


def test_get_oidc_client_passes_provider_key(monkeypatch):
    import app.auth.oidc as oidc_module

    oidc_module.get_oidc_client.cache_clear()
    monkeypatch.setenv("OIDC_ENABLED", "true")
    monkeypatch.setenv("OIDC_CLIENT_ID", "client-id")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("OIDC_DISCOVERY_URL", "https://idp.example.com/.well-known/openid-configuration")
    monkeypatch.setenv("OIDC_PROVIDER_KEY", "keycloak")

    with patch("httpx_oauth.clients.openid.OpenID") as openid_cls:
        oidc_module.get_oidc_client()
        openid_cls.assert_called_once()
        assert openid_cls.call_args.kwargs["name"] == "keycloak"

    oidc_module.get_oidc_client.cache_clear()


def test_validate_oidc_settings_requires_credentials_when_enabled():
    from app.auth.oidc import OidcSettings

    enabled = OidcSettings(
        enabled=True,
        client_id="",
        client_secret="",
        discovery_url="",
        provider_name="SSO",
        provider_key="sso",
        associate_by_email=False,
        scopes=["openid", "email"],
    )
    errors = validate_oidc_settings(enabled)
    assert any("OIDC_CLIENT_ID" in e for e in errors)
    assert any("OIDC_DISCOVERY_URL" in e for e in errors)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "/"),
        ("", "/"),
        ("/admin", "/admin"),
        ("/admin/users", "/admin/users"),
        ("https://evil.example", "/"),
        ("//evil.example", "/"),
    ],
)
def test_safe_next_path(raw, expected):
    assert _safe_next_path(raw) == expected


def test_ensure_oidc_client_skips_when_disabled(monkeypatch):
    import app.auth.oidc_router as oidc_router

    monkeypatch.setattr(oidc_router, "_settings", MagicMock(enabled=False))
    monkeypatch.setattr(oidc_router, "_oidc_client", None)
    monkeypatch.setattr(oidc_router, "_oauth2_authorize_callback", None)
    client, callback = _ensure_oidc_client()
    assert client is None
    assert callback is None


@pytest.mark.asyncio
async def test_apply_new_user_policies_pending_when_approval_required():
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(require_user_approval=True))),
        ]
    )
    user = MagicMock()
    user.id = "user-id"
    user.is_active = True
    user.approval_state = ApprovalState.PENDING

    await apply_new_user_policies(session, user, "new@example.com")

    session.add.assert_called_once()
    assert user.is_active is False


@pytest.mark.asyncio
async def test_oauth_callback_applies_policies_when_preference_missing():
    manager = UserManager(MagicMock())
    manager.user_db = MagicMock()
    manager.user_db.session = AsyncMock()
    manager.get_by_oauth_account = AsyncMock(side_effect=UserNotExists())
    manager.get_by_email = AsyncMock(side_effect=UserNotExists())
    manager.user_db.session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(require_user_approval=False))),
        ]
    )
    manager.user_db.session.commit = AsyncMock()
    manager.user_db.session.refresh = AsyncMock()

    created_user = MagicMock()
    created_user.email = "oidc@example.com"
    created_user.id = "user-id"
    created_user.display_name = None
    created_user.is_active = True
    with patch(
        "fastapi_users.manager.BaseUserManager.oauth_callback",
        new_callable=AsyncMock,
    ) as super_cb:
        super_cb.return_value = created_user
        result = await UserManager.oauth_callback(
            manager,
            "openid",
            "token",
            "sub-1",
            "oidc@example.com",
            associate_by_email=False,
            is_verified_by_default=True,
            display_name="Oidc User",
        )

    assert result is created_user
    assert created_user.display_name == "Oidc User"
    manager.user_db.session.commit.assert_awaited()
    manager.user_db.session.add.assert_called_once()


@pytest.mark.asyncio
async def test_oauth_callback_backfills_preference_without_deactivating_established_user():
    manager = UserManager(MagicMock())
    manager.user_db = MagicMock()
    manager.user_db.session = AsyncMock()
    established = MagicMock()
    established.id = uuid.uuid4()
    established.is_active = True
    established.approval_state = ApprovalState.APPROVED
    manager.get_by_oauth_account = AsyncMock(side_effect=UserNotExists())
    manager.get_by_email = AsyncMock(return_value=established)
    manager.user_db.session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    manager.user_db.session.commit = AsyncMock()
    manager.user_db.session.refresh = AsyncMock()

    linked_user = MagicMock()
    linked_user.id = established.id
    linked_user.email = "admin@example.com"
    linked_user.display_name = "Admin"
    linked_user.is_active = True
    linked_user.approval_state = ApprovalState.APPROVED

    with (
        patch(
            "fastapi_users.manager.BaseUserManager.oauth_callback",
            new_callable=AsyncMock,
        ) as super_cb,
        patch(
            "app.auth.auth_config.apply_new_user_policies",
            new_callable=AsyncMock,
        ) as apply_policies,
    ):
        super_cb.return_value = linked_user
        result = await UserManager.oauth_callback(
            manager,
            "company-sso",
            "token",
            "sub-admin",
            "admin@example.com",
            associate_by_email=True,
            is_verified_by_default=True,
        )

    assert result is linked_user
    apply_policies.assert_not_awaited()
    assert linked_user.is_active is True
    manager.user_db.session.add.assert_called_once()
    manager.user_db.session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_oauth_callback_skips_policies_when_preference_exists():
    manager = UserManager(MagicMock())
    manager.user_db = MagicMock()
    manager.user_db.session = AsyncMock()
    manager.get_by_oauth_account = AsyncMock(return_value=MagicMock())
    manager.user_db.session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock()))
    )
    manager.user_db.session.commit = AsyncMock()

    existing_user = MagicMock()
    existing_user.id = "user-id"
    existing_user.display_name = "Already Named"
    with patch(
        "fastapi_users.manager.BaseUserManager.oauth_callback",
        new_callable=AsyncMock,
    ) as super_cb:
        super_cb.return_value = existing_user
        result = await UserManager.oauth_callback(
            manager,
            "openid",
            "token",
            "sub-1",
            "oidc@example.com",
            associate_by_email=True,
            display_name="Ignored",
        )

    assert result is existing_user
    assert existing_user.display_name == "Already Named"
    manager.user_db.session.commit.assert_not_awaited()
    manager.user_db.session.add.assert_not_called()


@pytest.mark.asyncio
async def test_admin_update_profile_rejects_email_change_for_sso_user():
    user_id = uuid.uuid4()
    user = MagicMock()
    user.id = user_id
    user.email = "sso@example.com"
    user.display_name = "SSO User"
    user.oauth_accounts = [MagicMock()]

    session = AsyncMock()
    session.get = AsyncMock(return_value=user)

    with pytest.raises(HTTPException) as exc:
        await update_user_profile(
            user_id,
            AdminProfileUpdate(email="new@example.com", display_name="SSO User"),
            session=session,
            _admin=MagicMock(),
        )

    assert exc.value.status_code == 400
    assert "SSO-linked" in exc.value.detail


@pytest.mark.asyncio
async def test_oidc_callback_pending_user_redirects_without_session(monkeypatch):
    """Inactive SSO users must not receive postmarked_session."""
    from fastapi import FastAPI
    from fastapi.responses import RedirectResponse
    from httpx import ASGITransport, AsyncClient

    import app.auth.oidc_router as oidc_router
    from fastapi_users.router.oauth import CSRF_TOKEN_COOKIE_NAME, CSRF_TOKEN_KEY

    inactive = MagicMock()
    inactive.is_active = False

    client = MagicMock()
    client.name = "openid"
    client.get_id_email = AsyncMock(return_value=("sub-pending", "pending@example.com"))
    client.get_profile = AsyncMock(return_value={"name": "Pending"})
    oauth_cb = AsyncMock(return_value=({"access_token": "tok", "expires_at": None}, "state-token"))

    def fake_ensure():
        return client, oauth_cb

    monkeypatch.setattr(
        oidc_router,
        "_settings",
        MagicMock(enabled=True, associate_by_email=False, scopes=["openid", "email"]),
    )
    monkeypatch.setattr(oidc_router, "_ensure_oidc_client", fake_ensure)
    monkeypatch.setattr(
        oidc_router,
        "decode_jwt",
        lambda *a, **k: {CSRF_TOKEN_KEY: "csrf", oidc_router._NEXT_STATE_KEY: "/"},
    )

    app = FastAPI()
    app.include_router(oidc_router.router, prefix="/api/auth/oidc")

    async def override_user_manager():
        mgr = MagicMock()
        mgr.oauth_callback = AsyncMock(return_value=inactive)
        mgr.on_after_login = AsyncMock()
        return mgr

    async def override_strategy():
        return MagicMock()

    from app.auth.auth_config import auth_backend, get_user_manager

    app.dependency_overrides[get_user_manager] = override_user_manager
    app.dependency_overrides[auth_backend.get_strategy] = override_strategy

    login_called = False

    async def fake_login(*a, **k):
        nonlocal login_called
        login_called = True
        return RedirectResponse("/")

    monkeypatch.setattr(oidc_router.auth_backend, "login", fake_login)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={CSRF_TOKEN_COOKIE_NAME: "csrf"},
    ) as http:
        resp = await http.get(
            "/api/auth/oidc/callback",
            params={"code": "x", "state": "y"},
            follow_redirects=False,
        )

    assert resp.status_code == 302
    assert "error=oauth_pending" in resp.headers["location"]
    assert login_called is False
    assert "postmarked_session" not in (resp.headers.get("set-cookie") or "")


def _link_client(account_id="idp-account-1"):
    client = MagicMock()
    client.name = "openid"
    client.get_id_email = AsyncMock(return_value=(account_id, "person@example.com"))
    return client


def _link_manager(existing=None):
    manager = MagicMock()
    if existing is None:
        manager.get_by_oauth_account = AsyncMock(side_effect=UserNotExists())
    else:
        manager.get_by_oauth_account = AsyncMock(return_value=existing)
    manager.user_db = MagicMock()
    manager.user_db.add_oauth_account = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_link_requires_a_session_for_the_linking_account():
    from app.auth.oidc_router import _complete_link

    manager = _link_manager()
    response = await _complete_link(
        _link_client(), {"access_token": "t"}, str(uuid.uuid4()), None, manager
    )
    assert "error=link_mismatch" in response.headers["location"]
    manager.user_db.add_oauth_account.assert_not_awaited()


@pytest.mark.asyncio
async def test_link_rejects_a_session_for_a_different_account():
    from app.auth.oidc_router import _complete_link

    signed_in = MagicMock(id=uuid.uuid4())
    manager = _link_manager()
    response = await _complete_link(
        _link_client(), {"access_token": "t"}, str(uuid.uuid4()), signed_in, manager
    )
    assert "error=link_mismatch" in response.headers["location"]
    manager.user_db.add_oauth_account.assert_not_awaited()


@pytest.mark.asyncio
async def test_link_refuses_an_identity_already_held_by_another_user():
    from app.auth.oidc_router import _complete_link

    signed_in = MagicMock(id=uuid.uuid4(), email="me@example.com")
    other = MagicMock(id=uuid.uuid4())
    manager = _link_manager(existing=other)
    response = await _complete_link(
        _link_client(), {"access_token": "t"}, str(signed_in.id), signed_in, manager
    )
    assert "error=link_taken" in response.headers["location"]
    manager.user_db.add_oauth_account.assert_not_awaited()


@pytest.mark.asyncio
async def test_link_attaches_the_identity_to_the_signed_in_account():
    from app.auth.oidc_router import _complete_link

    signed_in = MagicMock(id=uuid.uuid4(), email="me@example.com")
    manager = _link_manager()
    response = await _complete_link(
        _link_client(),
        {"access_token": "t", "expires_at": 123, "refresh_token": "r"},
        str(signed_in.id),
        signed_in,
        manager,
    )
    assert "linked=1" in response.headers["location"]
    manager.user_db.add_oauth_account.assert_awaited_once()
    create_dict = manager.user_db.add_oauth_account.await_args.args[1]
    assert create_dict["account_id"] == "idp-account-1"
    assert create_dict["oauth_name"] == "openid"


@pytest.mark.asyncio
async def test_oauth_callback_applies_approval_even_if_preference_already_exists():
    """A concurrent callback for the same new account may create the preference
    row first. The approval gate must still be applied to the new user."""
    manager = UserManager(MagicMock())
    manager.user_db = MagicMock()
    manager.user_db.session = AsyncMock()
    manager.get_by_oauth_account = AsyncMock(side_effect=UserNotExists())
    manager.get_by_email = AsyncMock(side_effect=UserNotExists())
    manager.user_db.session.execute = AsyncMock(
        side_effect=[
            # the racing request already inserted the preference row
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock())),
            # not pre-approved
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            # approval is required
            MagicMock(
                scalar_one_or_none=MagicMock(
                    return_value=MagicMock(require_user_approval=True)
                )
            ),
        ]
    )
    manager.user_db.session.commit = AsyncMock()
    manager.user_db.session.refresh = AsyncMock()

    created = MagicMock()
    created.id = uuid.uuid4()
    created.email = "new@example.com"
    created.display_name = None
    created.is_active = True
    created.approval_state = ApprovalState.PENDING

    with patch(
        "fastapi_users.manager.BaseUserManager.oauth_callback", new_callable=AsyncMock
    ) as super_cb:
        super_cb.return_value = created
        await UserManager.oauth_callback(
            manager, "openid", "token", "sub-new", "new@example.com"
        )

    assert created.is_active is False
    manager.user_db.session.commit.assert_awaited()
