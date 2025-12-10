"""Core data models for TwinSync Spot."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class SpotType(str, Enum):
    """Types of spots to monitor."""
    COUNTER = "counter"
    SINK = "sink"
    TABLE = "table"
    FLOOR = "floor"
    SHELF = "shelf"
    DESK = "desk"
    CUSTOM = "custom"


class SpotStatus(str, Enum):
    """Status of a spot check."""
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


# Spot templates with default prompts
SPOT_TEMPLATES = {
    "counter": {
        "name": "Kitchen Counter",
        "description": "Clear counter with no dishes, clutter, or food items",
        "type": SpotType.COUNTER
    },
    "sink": {
        "name": "Kitchen Sink",
        "description": "Empty sink with no dirty dishes",
        "type": SpotType.SINK
    },
    "table": {
        "name": "Dining Table",
        "description": "Clean table surface with no clutter",
        "type": SpotType.TABLE
    },
    "floor": {
        "name": "Floor Space",
        "description": "Clear floor with no items or clutter",
        "type": SpotType.FLOOR
    },
    "shelf": {
        "name": "Storage Shelf",
        "description": "Organized shelf with items neatly arranged",
        "type": SpotType.SHELF
    },
    "desk": {
        "name": "Work Desk",
        "description": "Clean desk ready for work",
        "type": SpotType.DESK
    }
}


@dataclass
class ToSortItem:
    """Item that needs sorting/organizing."""
    name: str
    location: str
    suggestion: str


@dataclass
class CheckResult:
    """Result of a spot check."""
    timestamp: datetime
    status: SpotStatus
    score: int  # 0-100
    feedback: str
    items_to_sort: List[ToSortItem] = field(default_factory=list)
    image_path: Optional[str] = None


@dataclass
class SpotPatterns:
    """Patterns detected in spot history."""
    recurring_items: List[str] = field(default_factory=list)
    best_day: Optional[str] = None
    worst_day: Optional[str] = None
    current_streak: int = 0
    best_streak: int = 0


@dataclass
class SpotMemory:
    """Memory/context for a spot."""
    patterns: SpotPatterns
    last_updated: datetime
    total_checks: int
    pass_rate: float


@dataclass
class Spot:
    """A monitored spot/location."""
    id: int
    name: str
    description: str
    camera_entity_id: str
    spot_type: SpotType
    voice_id: str
    created_at: datetime
    updated_at: datetime
    last_check: Optional[CheckResult] = None
    memory: Optional[SpotMemory] = None
    snoozed_until: Optional[datetime] = None


@dataclass
class Camera:
    """A Home Assistant camera entity."""
    entity_id: str
    name: str
    state: str
