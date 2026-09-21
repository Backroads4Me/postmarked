"""
Schemas for RV Trip Wizard Excel import endpoints.
"""
import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import BaseResponse


class ImportDiffItem(BaseModel):
    """One row in the diff preview."""
    status: str  # added, unchanged, changed, removed, needs_review
    sequence: int
    name: str
    arrival_date: date | None = None
    departure_date: date | None = None
    nights: int | None = None
    location: str | None = None
    miles: float | None = None
    changes: list[str] = []  # field names that changed
    existing_id: uuid.UUID | None = None
    is_dangerous: bool = False


class ImportPreviewResponse(BaseModel):
    """Response from the parse/preview endpoint."""
    import_run_id: uuid.UUID
    trip_title: str
    start_date: str | None = None
    parsed_stop_count: int
    warnings: list[str] = []
    diff: list[ImportDiffItem] = []
    summary: dict = {}  # { added, unchanged, changed, removed }


class ImportApplyRequest(BaseModel):
    """Request to apply a parsed import."""
    target_trip_id: uuid.UUID | None = None
    create_trip: bool = True
    confirm_dangerous: bool = False


class ImportApplyResponse(BaseModel):
    """Response from the apply endpoint."""
    import_run_id: uuid.UUID
    trip_id: uuid.UUID
    trip_slug: str
    counts: dict = {}  # { added, updated, removed, unchanged }
    stop_ids: list[uuid.UUID] = []


class ImportRunOut(BaseResponse):
    id: uuid.UUID
    source_kind: str
    original_filename: str
    trip_title_from_file: str | None = None
    status: str
    summary_json: dict | None = None
    error_message: str | None = None
    created_at: datetime
