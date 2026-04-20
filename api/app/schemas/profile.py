from typing import Optional
from app.schemas.common import BaseResponse
from app.schemas.media import MediaAssetOut

class RvProfileOut(BaseResponse):
    title: Optional[str] = None
    rv_name: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    rv_type: Optional[str] = None
    length_feet: Optional[float] = None
    
    description: Optional[str] = None
    setup_notes: Optional[str] = None
    towing_info: Optional[str] = None
    modifications: Optional[str] = None
    
    cover_media: Optional[MediaAssetOut] = None

class TravelerProfileOut(BaseResponse):
    title: Optional[str] = None
    intro: Optional[str] = None
    story: Optional[str] = None
    travel_style: Optional[str] = None
    family_info: Optional[str] = None
    pet_info: Optional[str] = None
    
    contact_links: Optional[dict] = None
    
    cover_media: Optional[MediaAssetOut] = None
    
class CombinedProfilesOut(BaseResponse):
    rv: Optional[RvProfileOut] = None
    traveler: Optional[TravelerProfileOut] = None
