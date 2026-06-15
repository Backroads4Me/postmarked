from pathlib import Path

from starlette.requests import Request

from app.routers.media import _serve_file


def _request(*, method: str = "GET", range_header: str | None = None) -> Request:
    headers = []
    if range_header:
        headers.append((b"range", range_header.encode("ascii")))
    return Request({"type": "http", "method": method, "headers": headers})


def test_mp4_range_response_keeps_browser_cache_and_bypasses_cloudflare(tmp_path: Path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"0123456789")

    immutable = "public, max-age=31536000, immutable, no-transform"
    response = _serve_file(
        str(video),
        "video/mp4",
        "mp4",
        immutable,
        _request(range_header="bytes=0-1"),
        head_only=False,
    )

    assert response.status_code == 206
    assert response.headers["content-range"] == "bytes 0-1/10"
    assert response.headers["cache-control"] == immutable
    assert response.headers["cloudflare-cdn-cache-control"] == "no-store"


def test_mp4_head_response_keeps_browser_cache_and_bypasses_cloudflare(tmp_path: Path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"0123456789")

    immutable = "public, max-age=31536000, immutable, no-transform"
    response = _serve_file(
        str(video),
        "video/mp4",
        "mp4",
        immutable,
        _request(method="HEAD"),
        head_only=True,
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == immutable
    assert response.headers["cloudflare-cdn-cache-control"] == "no-store"


def test_image_response_keeps_immutable_cache_policy(tmp_path: Path):
    image = tmp_path / "image.webp"
    image.write_bytes(b"image")
    immutable = "public, max-age=31536000, immutable, no-transform"

    response = _serve_file(
        str(image),
        "image/webp",
        "webp",
        immutable,
        _request(method="HEAD"),
        head_only=True,
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == immutable
    assert "cloudflare-cdn-cache-control" not in response.headers
