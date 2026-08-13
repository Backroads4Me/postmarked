import uuid
from types import SimpleNamespace

from app.models.enums import ApprovalState, NotificationFrequency, UserRole
from app.routers.admin.users import _summary_from


def _user(**overrides):
    base = dict(
        id=uuid.uuid4(),
        email="subscriber@example.com",
        display_name="Subscriber",
        approval_state=ApprovalState.APPROVED,
        is_active=True,
        role=UserRole.USER,
        oauth_accounts=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_summary_falls_back_to_defaults_without_a_preference():
    # Listing users must not create preference rows, so the summary has to
    # render a user that has none.
    summary = _summary_from(_user(), None)
    assert summary.email_opted_in is False
    assert summary.notification_frequency is NotificationFrequency.ALL_UPDATES


def test_summary_uses_the_loaded_preference():
    preference = SimpleNamespace(
        email_opted_in=True,
        frequency=NotificationFrequency.WEEKLY_DIGEST,
    )
    summary = _summary_from(_user(), preference)
    assert summary.email_opted_in is True
    assert summary.notification_frequency is NotificationFrequency.WEEKLY_DIGEST


def test_summary_reports_oauth_linked_state():
    assert _summary_from(_user(), None).oauth_linked is False
    assert _summary_from(_user(oauth_accounts=[object()]), None).oauth_linked is True
