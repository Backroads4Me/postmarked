from datetime import datetime
from pydantic import BaseModel


class BackupManifest(BaseModel):
    app_version: str
    created_at: datetime
    entity_counts: dict[str, int]


class ImportResult(BaseModel):
    entity_counts: dict[str, int]
    media_files_copied: int
