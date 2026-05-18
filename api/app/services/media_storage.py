import os

from app.models.content import MediaAsset

ORIGINALS_PATH = os.getenv("ORIGINALS_PATH", "/tmp/originals")
DERIVATIVES_PATH = os.getenv("DERIVATIVES_PATH", "/tmp/derivatives")


def media_asset_file_paths(asset: MediaAsset) -> list[str]:
    paths = []
    if asset.original_path:
        paths.append(asset.original_path)
    paths.append(os.path.join(ORIGINALS_PATH, f"{asset.id}.bin"))
    paths.append(os.path.join(ORIGINALS_PATH, f"{asset.id}.json"))
    paths.append(os.path.join(DERIVATIVES_PATH, f"{asset.id}.webp"))
    paths.append(os.path.join(DERIVATIVES_PATH, f"{asset.id}-poster.jpg"))
    return list(dict.fromkeys(paths))


def delete_media_asset_files(asset: MediaAsset) -> None:
    for path in media_asset_file_paths(asset):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
