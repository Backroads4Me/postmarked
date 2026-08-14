"""The tus PATCH handler must write at the client's offset, not append.

Appending let a rejected chunk stay on disk while the recorded offset did not
move, so replaying the same request grew the part file without bound and broke
resumption for honest clients.
"""

import json
import uuid

import pytest

from app.routers.admin import media as media_router


class _FakeRequest:
    def __init__(self, chunks):
        self._chunks = chunks

    async def stream(self):
        for chunk in self._chunks:
            yield chunk


@pytest.fixture
def upload(tmp_path, monkeypatch):
    monkeypatch.setattr(media_router, "ORIGINALS_PATH", str(tmp_path))
    file_id = uuid.uuid4()
    info = tmp_path / f"{file_id}.json"
    binp = tmp_path / f"{file_id}.bin"
    info.write_text(json.dumps({"offset": 0, "upload_length": 100}))
    binp.write_bytes(b"")
    return file_id, info, binp


async def _patch(file_id, offset, chunks):
    return await media_router.patch_upload(
        file_id=file_id,
        request=_FakeRequest(chunks),
        upload_offset=offset,
        content_type="application/offset+octet-stream",
        session=None,
        user=None,
    )


@pytest.mark.asyncio
async def test_rejected_chunk_leaves_file_and_sidecar_in_agreement(upload):
    file_id, info, binp = upload
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await _patch(file_id, 0, [b"x" * 60, b"y" * 60])
    assert exc.value.status_code == 413

    recorded = json.loads(info.read_text())["offset"]
    assert binp.stat().st_size == 60
    assert recorded == 60, "the accepted bytes must be recorded, not silently dropped"


@pytest.mark.asyncio
async def test_replaying_a_rejected_request_does_not_grow_the_file(upload):
    file_id, info, binp = upload
    from fastapi import HTTPException

    for _ in range(5):
        with pytest.raises(HTTPException):
            await _patch(file_id, 0, [b"x" * 60, b"y" * 60])

    # Before the fix each replay appended another 60 bytes without end.
    assert binp.stat().st_size == 60
    assert json.loads(info.read_text())["offset"] == 60


@pytest.mark.asyncio
async def test_resume_overwrites_a_stale_tail_instead_of_appending(upload):
    file_id, info, binp = upload
    binp.write_bytes(b"a" * 40)
    info.write_text(json.dumps({"offset": 20, "upload_length": 100}))

    from fastapi import HTTPException

    try:
        await _patch(file_id, 20, [b"b" * 10])
    except HTTPException:  # pragma: no cover - completion path needs a session
        pass

    data = binp.read_bytes()
    assert len(data) == 30, "bytes past the resume point must be discarded"
    assert data == b"a" * 20 + b"b" * 10


@pytest.mark.asyncio
async def test_offset_beyond_what_is_on_disk_is_refused(upload):
    file_id, info, binp = upload
    info.write_text(json.dumps({"offset": 90, "upload_length": 100}))
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await _patch(file_id, 90, [b"z"])
    assert exc.value.status_code == 409
