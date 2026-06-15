from datetime import datetime
from pydantic import BaseModel


class BackupManifest(BaseModel):
    app_version: str
    created_at: datetime
    entity_counts: dict[str, int] = {}
    # "pgdump" = db.dump from pg_dump --data-only; "json" = legacy per-table JSON dumps.
    format: str = "json"


class ImportResult(BaseModel):
    entity_counts: dict[str, int]
    media_files_copied: int
