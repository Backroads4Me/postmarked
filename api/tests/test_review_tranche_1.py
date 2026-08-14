import jwt
import pytest
from fastapi_users.router.oauth import CSRF_TOKEN_COOKIE_NAME

from app.auth.oidc_router import _login_error_redirect
from app.imports.rv_trip_wizard import parse_float, parse_latitude, parse_longitude


def test_failed_oidc_attempt_clears_the_csrf_cookie():
    response = _login_error_redirect("oauth_failed")
    cookies = response.headers.getlist("set-cookie")
    assert any(CSRF_TOKEN_COOKIE_NAME in c for c in cookies)
    # A deletion is an expiry, not a value.
    assert any("Max-Age=0" in c or "expires=Thu, 01 Jan 1970" in c.lower() for c in cookies)
    assert "error=oauth_failed" in response.headers["location"]


def test_state_decode_handles_every_pyjwt_error():
    # A token signed with the right secret but the wrong audience raises
    # InvalidAudienceError, which is not a DecodeError.
    token = jwt.encode({"aud": ["something-else"]}, "s3cret", algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(token, "s3cret", audience=["fastapi-users:oauth-state"], algorithms=["HS256"])


@pytest.mark.parametrize(
    "raw,expected",
    [("1e400", None), ("nan", None), ("-inf", None), ("12.5", 12.5), ("0", 0.0), ("x", None)],
)
def test_parse_float_rejects_non_finite(raw, expected):
    assert parse_float(raw) == expected


@pytest.mark.parametrize("raw,expected", [(91, None), (-91, None), (90, 90.0), (0, 0.0), ("nan", None)])
def test_parse_latitude_range(raw, expected):
    assert parse_latitude(raw) == expected


@pytest.mark.parametrize("raw,expected", [(181, None), (-181, None), (180, 180.0), (-45.5, -45.5)])
def test_parse_longitude_range(raw, expected):
    assert parse_longitude(raw) == expected


@pytest.mark.parametrize(
    "template,expected",
    [
        ("New: {post_title}", "New: A Post"),
        ("Braces {0} and {oops}", "Braces {0} and {oops}"),
        ("A literal { brace", "A literal { brace"),
        ("", ""),
    ],
)
def test_site_text_templates_tolerate_stray_braces(template, expected):
    """A stray brace used to raise before the recipient loop, so a whole post's
    notification was silently never sent."""
    from app.tasks import _fill_post_template

    assert _fill_post_template(template, "A Post") == expected
