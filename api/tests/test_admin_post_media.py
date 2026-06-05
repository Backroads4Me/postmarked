import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.enums import Visibility
from app.routers.admin.posts import _attach_media_to_post


def _asset(**overrides):
    values = {
        "id": uuid.uuid4(),
        "post_id": None,
        "stop_id": None,
        "trip_id": None,
        "visibility": Visibility.PRIVATE,
        "sort_order": 99,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_attach_media_assigns_unowned_assets_in_request_order():
    post = SimpleNamespace(id=uuid.uuid4(), stop_id=uuid.uuid4(), trip_id=uuid.uuid4())
    first = _asset()
    second = _asset()
    assets = {first.id: first, second.id: second}
    session = SimpleNamespace(get=AsyncMock(side_effect=lambda _model, media_id: assets.get(media_id)))

    attached = await _attach_media_to_post(
        session,
        post,
        [second.id, first.id],
        Visibility.PUBLIC,
    )

    assert attached == 2
    assert second.post_id == post.id
    assert second.stop_id == post.stop_id
    assert second.trip_id == post.trip_id
    assert second.visibility == Visibility.PUBLIC
    assert second.sort_order == 0
    assert first.sort_order == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "asset",
    [
        _asset(post_id=uuid.uuid4()),
        _asset(stop_id=uuid.uuid4()),
        _asset(trip_id=uuid.uuid4()),
    ],
)
async def test_attach_media_rejects_assets_assigned_elsewhere_without_mutation(asset):
    post = SimpleNamespace(id=uuid.uuid4(), stop_id=uuid.uuid4(), trip_id=uuid.uuid4())
    original = (asset.post_id, asset.stop_id, asset.trip_id, asset.visibility, asset.sort_order)
    session = SimpleNamespace(get=AsyncMock(return_value=asset))

    with pytest.raises(HTTPException) as exc:
        await _attach_media_to_post(session, post, [asset.id], Visibility.PUBLIC)

    assert exc.value.status_code == 409
    assert (asset.post_id, asset.stop_id, asset.trip_id, asset.visibility, asset.sort_order) == original
