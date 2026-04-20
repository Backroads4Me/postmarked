import enum

class Visibility(str, enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"

class TripStatus(str, enum.Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class StopStatus(str, enum.Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class StopType(str, enum.Enum):
    CAMPGROUND = "campground"
    BOONDOCKING = "boondocking"
    OVERNIGHT = "overnight"
    ATTRACTION = "attraction"
    RESTAURANT = "restaurant"
    SERVICE = "service"
    OTHER = "other"

class MediaKind(str, enum.Enum):
    PHOTO = "photo"
    VIDEO = "video"

class MediaProcessingState(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"

class ApprovalState(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class NotificationFrequency(str, enum.Enum):
    ALL_UPDATES = "all_updates"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_DIGEST = "weekly_digest"
    MONTHLY_DIGEST = "monthly_digest"
    NONE = "none"

class POIType(str, enum.Enum):
    CAMPGROUND = "campground"
    TRAILHEAD = "trailhead"
    FUEL = "fuel"
    RESTAURANT = "restaurant"
    ATTRACTION = "attraction"
    OTHER = "other"
