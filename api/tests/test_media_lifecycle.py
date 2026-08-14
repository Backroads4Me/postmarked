"""Guards on the media lifecycle decisions from the security review.

Requeue used to destroy healthy assets, and the sweep deletes files, so both
need their boundaries pinned.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import MediaProcessingState


@pytest.mark.asyncio
async def test_requeue_refuses_a_ready_asset_whose_original_is_gone(tmp_path, monkeypatch):
    from app.routers.admin import media as media_router

    monkeypatch.setattr(media_router, "ORIGINALS_PATH", str(tmp_path))
    asset = MagicMock()
    asset.id = uuid.uuid4()
    asset.original_path = None
    asset.processing_state = MediaProcessingState.READY

    session = MagicMock()

    async def _get(_model, _id):
        return asset

    session.get = _get

    with pytest.raises(HTTPException) as exc:
        await media_router.requeue_media_asset(asset.id, session=session, user=None)

    assert exc.value.status_code == 409
    # The old behaviour set PENDING here, and the worker then set FAILED, which
    # hid the asset everywhere with no way back through the UI.
    assert asset.processing_state == MediaProcessingState.READY


@pytest.mark.asyncio
async def test_requeue_proceeds_when_the_original_is_present(tmp_path, monkeypatch):
    from app.routers.admin import media as media_router

    monkeypatch.setattr(media_router, "ORIGINALS_PATH", str(tmp_path))
    asset = MagicMock()
    asset.id = uuid.uuid4()
    asset.original_path = None
    asset.processing_state = MediaProcessingState.FAILED
    (tmp_path / f"{asset.id}.bin").write_bytes(b"source")

    session = MagicMock()

    async def _get(_model, _id):
        return asset

    async def _commit():
        return None

    session.get = _get
    session.commit = _commit

    with patch.object(media_router.process_media_asset, "delay") as delay:
        result = await media_router.requeue_media_asset(asset.id, session=session, user=None)

    assert result == {"ok": True}
    assert asset.processing_state == MediaProcessingState.PENDING
    delay.assert_called_once()


def test_sweep_keeps_artifacts_belonging_to_a_known_asset(tmp_path, monkeypatch):
    from app import tasks

    monkeypatch.setattr(tasks, "ORIGINALS_PATH", str(tmp_path / "originals"))
    monkeypatch.setattr(tasks, "DERIVATIVES_PATH", str(tmp_path / "derivatives"))
    os.makedirs(tasks.ORIGINALS_PATH)
    os.makedirs(tasks.DERIVATIVES_PATH)

    live_id = uuid.uuid4()
    old = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()

    live = os.path.join(tasks.ORIGINALS_PATH, f"{live_id}.bin")
    orphan = os.path.join(tasks.ORIGINALS_PATH, f"{uuid.uuid4()}.bin")
    for path in (live, orphan):
        with open(path, "wb") as fh:
            fh.write(b"x")
        os.utime(path, (old, old))

    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = []
    db.execute.return_value.all.return_value = [(live_id,)]
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)

    tasks.sweep_stale_media()

    assert os.path.exists(live), "an artifact with a live row must survive"
    assert not os.path.exists(orphan)


def test_sweep_leaves_recent_orphans_alone(tmp_path, monkeypatch):
    from app import tasks

    monkeypatch.setattr(tasks, "ORIGINALS_PATH", str(tmp_path / "originals"))
    monkeypatch.setattr(tasks, "DERIVATIVES_PATH", str(tmp_path / "derivatives"))
    os.makedirs(tasks.ORIGINALS_PATH)
    os.makedirs(tasks.DERIVATIVES_PATH)

    # An upload in progress has no row yet; deleting it would break the upload.
    in_flight = os.path.join(tasks.ORIGINALS_PATH, f"{uuid.uuid4()}.bin")
    with open(in_flight, "wb") as fh:
        fh.write(b"partial")

    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = []
    db.execute.return_value.all.return_value = []
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)

    tasks.sweep_stale_media()

    assert os.path.exists(in_flight)
