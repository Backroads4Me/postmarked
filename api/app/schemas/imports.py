"""
Schemas for RV Trip Wizard Excel import endpoints.
"""
import uuid
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel

from app.schemas.common import BaseResponse


class ImportDiffItem(BaseModel):
    """One row in the diff preview."""
    status: str  # added, unchanged, changed, removed, needs_review
    sequence: int
    name: str
    arrival_date: Optional[date] = None
    departure_date: Optional[date] = None
    nights: Optional[int] = None
    location: Optional[str] = None
    miles: Optional[float] = None
    changes: List[str] = []  # field names that changed
    existing_id: Optional[uuid.UUID] = None
    is_dangerous: bool = False


class ImportPreviewResponse(BaseModel):
    """Response from the parse/preview endpoint."""
    import_run_id: uuid.UUID
    trip_title: str
    start_date: Optional[str] = None
    parsed_stop_count: int
    warnings: List[str] = []
    diff: List[ImportDiffItem] = []
    summary: dict = {}  # { added, unchanged, changed, removed }


class ImportApplyRequest(BaseModel):
    """Request to apply a parsed import."""
    target_trip_id: Optional[uuid.UUID] = None
    create_trip: bool = True
    confirm_dangerous: bool = False


class ImportApplyResponse(BaseModel):
    """Response from the apply endpoint."""
    import_run_id: uuid.UUID
    trip_id: uuid.UUID
    trip_slug: str
    counts: dict = {}  # { added, updated, removed, unchanged }
    stop_ids: List[uuid.UUID] = []


class ImportRunOut(BaseResponse):
    id: uuid.UUID
    source_kind: str
    original_filename: str
    trip_title_from_file: Optional[str] = None
    status: str
    summary_json: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
