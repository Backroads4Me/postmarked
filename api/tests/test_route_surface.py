"""Guards on which auth-adjacent routes are exposed.

account.py owns email and password changes because it enforces re-authentication
and refuses to change the email of an SSO-linked account. Mounting fastapi-users'
users router would re-expose those fields on PATCH /api/users/me without either
guard, so the surface is asserted here rather than left to review.
"""

import pytest


@pytest.fixture(scope="module")
def paths():
    from app.main import app

    return app.openapi()["paths"]


def test_current_user_endpoint_is_read_only(paths):
    assert "/api/users/me" in paths
    assert {m.upper() for m in paths["/api/users/me"]} == {"GET"}


def test_no_writable_user_routes_are_exposed(paths):
    writable = {
        (path, method.upper())
        for path, methods in paths.items()
        if path.startswith("/api/users")
        for method in methods
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
    }
    assert writable == set()


def test_account_router_still_owns_credential_changes(paths):
    assert "PATCH" in {m.upper() for m in paths["/api/account/password"]}
    assert "PATCH" in {m.upper() for m in paths["/api/account/profile"]}
