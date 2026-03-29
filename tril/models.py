from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


Coordinates = Tuple[float, float]


@dataclass
class VehicleProfile:
    height_ft: float = 13.5
    weight_lb: float = 80000.0
    length_ft: float = 70.0
    axles: int = 5
    hazmat: bool = False


@dataclass
class HOSState:
    remaining_drive_hours: float
    remaining_duty_hours: float


@dataclass
class PreferencesOverride:
    avoid_zones: List[str] = field(default_factory=list)
    prefer_corridors: List[str] = field(default_factory=list)


@dataclass
class RouteRequest:
    origin: str
    destination: str
    stops: List[str] = field(default_factory=list)
    vehicle_profile: VehicleProfile = field(default_factory=VehicleProfile)
    hos: Optional[HOSState] = None
    preferences_override: PreferencesOverride = field(default_factory=PreferencesOverride)


@dataclass
class GeocodeResult:
    input_text: str
    matched_name: str
    coordinates: Coordinates
    confidence: float = 1.0


@dataclass
class Segment:
    segment_id: str
    name: str
    road_class: str
    distance_miles: float
    maxheight_ft: Optional[float] = None
    maxweight_lb: Optional[float] = None
    maxlength_ft: Optional[float] = None
    max_axle_weight_lb: Optional[float] = None
    hgv_allowed: Optional[bool] = None
    hazmat_allowed: Optional[bool] = None
    source_tags: Dict[str, Any] = field(default_factory=dict)
    source_flags: List[str] = field(default_factory=list)
    confidence_tier: Optional[int] = None


@dataclass
class RouteCandidate:
    route_candidate_id: str
    summary: str
    distance_miles: float
    estimated_drive_time_hours: float
    segments: List[Segment]
    source_engine: str
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Violation:
    type: str
    segment_id: str
    threshold_value: Optional[float] = None
    actual_value: Optional[float] = None
    description: str = ""


@dataclass
class ConstraintWarning:
    type: str
    segment_id: str
    tier: Optional[int] = None
    description: str = ""


@dataclass
class SourceVersionSummary:
    source_name: str
    version: str
    published_at: Optional[str] = None
    effective_from: Optional[str] = None
    stale_after_days: Optional[int] = None
    age_days: Optional[int] = None
    status: str = "unknown"
    record_count: int = 0
    coverage: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationTrace:
    segment_id: str
    segment_name: str
    applied_sources: List[str] = field(default_factory=list)
    matched_reference_ids: Dict[str, str] = field(default_factory=dict)
    applied_limits: Dict[str, Any] = field(default_factory=dict)
    source_age_days: Dict[str, Optional[int]] = field(default_factory=dict)
    stale_sources: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class ConstraintReport:
    violations_found: int
    violations: List[Violation] = field(default_factory=list)
    warnings: List[ConstraintWarning] = field(default_factory=list)
    validation_trace: List[ValidationTrace] = field(default_factory=list)
    source_versions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    turn_feasibility_validated: bool = False
    turn_feasibility_note: str = (
        "Sequence-level turn validation not available in MVP. "
        "Routing engine profile provides partial coverage."
    )


@dataclass
class RetryState:
    attempt_number: int
    blacklisted_segments: List[str] = field(default_factory=list)
    last_failure_types: List[str] = field(default_factory=list)


@dataclass
class ResetRecommendation:
    location_name: str
    location_type: str
    distance_from_origin_miles: float
    drive_time_to_reset_hours: float
    coordinates: Coordinates
    post_reset_remaining_miles: float


@dataclass
class HOSAnalysis:
    hos_warning: bool = False
    remaining_drive_hours: Optional[float] = None
    remaining_duty_hours: Optional[float] = None
    route_drive_time_hours: Optional[float] = None
    route_duty_time_hours: Optional[float] = None
    projected_drive_hours_remaining: Optional[float] = None
    projected_duty_hours_remaining: Optional[float] = None
    overage_hours: float = 0.0
    duty_overage_hours: float = 0.0
    summary: str = "No HOS analysis requested"
    recommended_reset: Optional[ResetRecommendation] = None
    alternative_resets: List[ResetRecommendation] = field(default_factory=list)


@dataclass
class RouteScores:
    confidence_score: float
    safety_score: float
    preference_score: float
    data_tiers: Dict[str, float]


@dataclass
class ToolError:
    code: str
    message: str
    failed_input: Optional[str] = None
    retry_report: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteResult:
    status: str
    route: Optional[Dict[str, Any]] = None
    constraint_report: Optional[Dict[str, Any]] = None
    hos_analysis: Optional[Dict[str, Any]] = None
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
