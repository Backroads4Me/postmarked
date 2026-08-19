"""Guards on the media lifecycle decisions from the security review.

Requeue used to destroy healthy assets, and the sweep deletes files, so both
need their boundaries pinned.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

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
    live_info = os.path.join(tasks.ORIGINALS_PATH, f"{live_id}.json")
    orphan = os.path.join(tasks.ORIGINALS_PATH, f"{uuid.uuid4()}.bin")
    for path in (live, live_info, orphan):
        with open(path, "wb") as fh:
            fh.write(b"x")
        os.utime(path, (old, old))

    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = []
    db.execute.return_value.all.return_value = [(live_id,)]
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)

    tasks.sweep_stale_media()

    assert os.path.exists(live), "an artifact with a live row must survive"
    assert os.path.exists(live_info)
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


def _write_tus_upload(directory, file_id, state, content, age):
    info = directory / f"{file_id}.json"
    binary = directory / f"{file_id}.bin"
    info.write_text(state)
    binary.write_bytes(content)
    modified = (datetime.now(timezone.utc) - age).timestamp()
    os.utime(info, (modified, modified))
    os.utime(binary, (modified, modified))
    return info, binary


def _empty_sweep_db():
    stale_result = MagicMock()
    stale_result.scalars.return_value.all.return_value = []
    known_result = MagicMock()
    known_result.all.return_value = []
    db = MagicMock()
    db.execute.side_effect = [stale_result, known_result]
    return db


def test_sweep_preserves_a_valid_paused_tus_upload(tmp_path, monkeypatch):
    from app import tasks

    originals = tmp_path / "originals"
    derivatives = tmp_path / "derivatives"
    originals.mkdir()
    derivatives.mkdir()
    monkeypatch.setattr(tasks, "ORIGINALS_PATH", str(originals))
    monkeypatch.setattr(tasks, "DERIVATIVES_PATH", str(derivatives))
    monkeypatch.setattr(tasks, "TUS_UPLOAD_RETENTION_SECONDS", 7 * 24 * 60 * 60)
    file_id = uuid.uuid4()
    state = '{"upload_length": 10, "offset": 7, "metadata": {}}'
    info, binary = _write_tus_upload(
        originals, file_id, state, b"partial", timedelta(days=2)
    )
    monkeypatch.setattr(tasks, "SessionLocal", _empty_sweep_db)

    tasks.sweep_stale_media()

    assert info.exists()
    assert binary.exists()


def test_sweep_expires_an_abandoned_tus_upload(tmp_path, monkeypatch):
    from app import tasks

    originals = tmp_path / "originals"
    derivatives = tmp_path / "derivatives"
    originals.mkdir()
    derivatives.mkdir()
    monkeypatch.setattr(tasks, "ORIGINALS_PATH", str(originals))
    monkeypatch.setattr(tasks, "DERIVATIVES_PATH", str(derivatives))
    monkeypatch.setattr(tasks, "TUS_UPLOAD_RETENTION_SECONDS", 7 * 24 * 60 * 60)
    file_id = uuid.uuid4()
    state = '{"upload_length": 10, "offset": 7, "metadata": {}}'
    info, binary = _write_tus_upload(
        originals, file_id, state, b"partial", timedelta(days=8)
    )
    monkeypatch.setattr(tasks, "SessionLocal", _empty_sweep_db)

    tasks.sweep_stale_media()

    assert not info.exists()
    assert not binary.exists()


def test_sweep_removes_corrupt_tus_state_after_orphan_grace(tmp_path, monkeypatch):
    from app import tasks

    originals = tmp_path / "originals"
    derivatives = tmp_path / "derivatives"
    originals.mkdir()
    derivatives.mkdir()
    monkeypatch.setattr(tasks, "ORIGINALS_PATH", str(originals))
    monkeypatch.setattr(tasks, "DERIVATIVES_PATH", str(derivatives))
    file_id = uuid.uuid4()
    info, binary = _write_tus_upload(
        originals, file_id, "not-json", b"partial", timedelta(hours=2)
    )
    monkeypatch.setattr(tasks, "SessionLocal", _empty_sweep_db)

    tasks.sweep_stale_media()

    assert not info.exists()
    assert not binary.exists()


def test_processing_claim_has_one_winner_for_concurrent_workers():
    from app import tasks

    asset_id = uuid.uuid4()
    first = MagicMock()
    first.scalar_one_or_none.return_value = asset_id
    second = MagicMock()
    second.scalar_one_or_none.return_value = None
    db = MagicMock()
    db.execute.side_effect = [first, second]
    now = datetime.now(timezone.utc)

    assert tasks._claim_media_asset(db, asset_id, now=now) is True
    assert tasks._claim_media_asset(db, asset_id, now=now) is False
    db.commit.assert_called_once()


def test_stale_requeue_lease_has_one_winner_for_concurrent_sweeps():
    from app import tasks

    asset_id = uuid.uuid4()
    first = MagicMock()
    first.scalars.return_value.all.return_value = [asset_id]
    second = MagicMock()
    second.scalars.return_value.all.return_value = []
    db = MagicMock()
    db.execute.side_effect = [first, second]
    now = datetime.now(timezone.utc)

    assert tasks._lease_stale_media_requeues(db, now=now) == [asset_id]
    assert tasks._lease_stale_media_requeues(db, now=now) == []
    db.commit.assert_called_once()


def test_processing_lock_blocks_a_second_worker(monkeypatch):
    from app import tasks

    asset_id = uuid.uuid4()
    db = MagicMock()
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(tasks, "_acquire_media_lock", lambda _db, _asset_id: False)
    claim = MagicMock()
    monkeypatch.setattr(tasks, "_claim_media_asset", claim)

    assert tasks.process_media_asset(str(asset_id)) == "Asset is already processing"
    claim.assert_not_called()
    db.get.assert_not_called()
    db.close.assert_called_once()


def test_completed_asset_is_not_reclaimed(monkeypatch):
    from app import tasks

    asset_id = uuid.uuid4()
    db = MagicMock()
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(tasks, "_acquire_media_lock", lambda _db, _asset_id: True)
    monkeypatch.setattr(tasks, "_claim_media_asset", lambda _db, _asset_id: False)
    release = MagicMock()
    monkeypatch.setattr(tasks, "_release_media_lock", release)

    assert tasks.process_media_asset(str(asset_id)) == "Asset is not pending or recoverable"
    db.get.assert_not_called()
    release.assert_called_once_with(db, asset_id)


def test_sweep_requeues_pending_and_expired_processing_assets(monkeypatch, tmp_path):
    from app import tasks

    monkeypatch.setattr(tasks, "ORIGINALS_PATH", str(tmp_path / "originals"))
    monkeypatch.setattr(tasks, "DERIVATIVES_PATH", str(tmp_path / "derivatives"))
    os.makedirs(tasks.ORIGINALS_PATH)
    os.makedirs(tasks.DERIVATIVES_PATH)

    queued_id = uuid.uuid4()
    expired_id = uuid.uuid4()
    stale_result = MagicMock()
    stale_result.scalars.return_value.all.return_value = [queued_id, expired_id]
    known_result = MagicMock()
    known_result.all.return_value = [(queued_id,), (expired_id,)]
    db = MagicMock()
    db.execute.side_effect = [stale_result, known_result]
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)

    with patch.object(tasks.process_media_asset, "delay") as delay:
        result = tasks.sweep_stale_media()

    assert result == "Requeued 2 pending assets, removed 0 orphaned files"
    assert delay.call_args_list == [call(str(queued_id)), call(str(expired_id))]
