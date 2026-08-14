"""Restore treats the uploaded archive as untrusted input.

It is the one admin action that destroys data, and the archive may come from an
instance the operator does not control.
"""

import io
import zipfile

import pytest
from fastapi import HTTPException

from app.routers.admin import backup as backup_mod


def _zip(members: dict[str, bytes]) -> zipfile.ZipFile:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in members.items():
            zf.writestr(name, payload)
    buf.seek(0)
    return zipfile.ZipFile(buf)


def test_restored_media_row_cannot_supply_its_own_path_or_type():
    data = {"id": "abc", "original_path": "/etc/passwd", "mime_type": "text/html"}
    backup_mod._sanitize_restored_row("media_assets", data)
    assert data["original_path"].endswith("/abc.bin")
    assert data["mime_type"] == "application/octet-stream"


def test_sanitizer_leaves_other_entities_alone():
    data = {"id": "t1", "title": "A trip"}
    backup_mod._sanitize_restored_row("trips", data)
    assert data == {"id": "t1", "title": "A trip"}


def test_directory_entries_are_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_mod, "DERIVATIVES_PATH", str(tmp_path / "derivatives"))
    monkeypatch.setattr(backup_mod, "ORIGINALS_PATH", str(tmp_path / "originals"))
    zf = _zip({"media/derivatives/": b"", "media/derivatives/a.webp": b"x" * 10})
    # A bare directory entry has an empty basename and previously raised
    # IsADirectoryError after the media wipe.
    copied = backup_mod._restore_media_files(zf, set(zf.namelist()))
    assert copied == 1
    assert (tmp_path / "derivatives" / "a.webp").read_bytes() == b"x" * 10


def test_existing_media_survives_a_failed_restore(tmp_path, monkeypatch):
    derivatives = tmp_path / "derivatives"
    derivatives.mkdir()
    (derivatives / "keep.webp").write_bytes(b"original")
    monkeypatch.setattr(backup_mod, "DERIVATIVES_PATH", str(derivatives))
    monkeypatch.setattr(backup_mod, "ORIGINALS_PATH", str(tmp_path / "originals"))

    zf = _zip({"media/derivatives/a.webp": b"x"})
    monkeypatch.setattr(backup_mod, "MAX_MEMBER_BYTES", 0)
    with pytest.raises(HTTPException):
        backup_mod._restore_media_files(zf, set(zf.namelist()))

    # The wipe used to happen first, so a failure left media half-deleted.
    assert (derivatives / "keep.webp").read_bytes() == b"original"


def test_a_zip_bomb_member_is_refused():
    info = zipfile.ZipInfo("db.dump")
    info.file_size = 50 * 1024**3
    info.compress_size = 1024
    with pytest.raises(HTTPException) as exc:
        backup_mod._check_archive_member(info)
    assert exc.value.status_code == 413


def test_an_implausible_compression_ratio_is_refused():
    info = zipfile.ZipInfo("data/trips.json")
    info.file_size = 100 * 1024 * 1024
    info.compress_size = 1024
    with pytest.raises(HTTPException) as exc:
        backup_mod._check_archive_member(info)
    assert exc.value.status_code == 400


def test_a_plausible_member_passes():
    info = zipfile.ZipInfo("media/derivatives/a.webp")
    info.file_size = 2 * 1024 * 1024
    info.compress_size = 1024 * 1024
    backup_mod._check_archive_member(info)
