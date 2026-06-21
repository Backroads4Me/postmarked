import enum

class Visibility(str, enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"

class TripStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    ARCHIVED = "archived"

class StopStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    ARCHIVED = "archived"

class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    ARCHIVED = "archived"

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

class POIType(str, enum.Enum):
    CAMPGROUND = "campground"
    TRAILHEAD = "trailhead"
    FUEL = "fuel"
    RESTAURANT = "restaurant"
    ATTRACTION = "attraction"
    OTHER = "other"

class PostType(str, enum.Enum):
    UPDATE = "update"
    ACTIVITY = "activity"

class ActivityType(str, enum.Enum):
    HIKING = "hiking"
    MUSEUM = "museum"
    RESTAURANT = "restaurant"
    ATTRACTION = "attraction"
    SERVICE = "service"
    SCENIC_DRIVE = "scenic_drive"
    SHOPPING = "shopping"
    FAMILY = "family"
    OTHER = "other"
