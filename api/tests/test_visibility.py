from types import SimpleNamespace

from app.models.enums import ApprovalState, MediaProcessingState, UserRole, Visibility
from app.services.visibility import visible_ready_cover_media, visible_ready_media


def _asset(*, state=MediaProcessingState.READY, visibility=Visibility.PUBLIC):
    return SimpleNamespace(processing_state=state, visibility=visibility)


def _admin():
    return SimpleNamespace(role=UserRole.ADMIN, approval_state=ApprovalState.APPROVED)


def test_public_media_filters_out_pending_and_failed_assets_for_anonymous_users():
    ready_public = _asset()
    pending_public = _asset(state=MediaProcessingState.PENDING)
    failed_public = _asset(state=MediaProcessingState.FAILED)
    ready_private = _asset(visibility=Visibility.PRIVATE)

    assert visible_ready_media(
        [ready_public, pending_public, failed_public, ready_private],
        user=None,
    ) == [ready_public]


def test_admin_media_filter_still_requires_ready_processing_state():
    ready_private = _asset(visibility=Visibility.PRIVATE)
    pending_private = _asset(
        state=MediaProcessingState.PENDING,
        visibility=Visibility.PRIVATE,
    )

    assert visible_ready_media([ready_private, pending_private], user=_admin()) == [ready_private]


def test_cover_media_filter_returns_none_for_missing_or_unready_assets():
    ready_public = _asset()
    pending_public = _asset(state=MediaProcessingState.PENDING)

    assert visible_ready_cover_media(None, user=None) is None
    assert visible_ready_cover_media(pending_public, user=None) is None
    assert visible_ready_cover_media(ready_public, user=None) is ready_public
