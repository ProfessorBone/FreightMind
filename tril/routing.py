from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Sequence

from .geocoding import CircuitBreaker, _retry_with_backoff
from .models import GeocodeResult, RouteCandidate, Segment, VehicleProfile

logger = logging.getLogger("tril.routing")


class RoutingError(Exception):
    pass


class StubGraphHopperClient:
    """MVP stand-in for GraphHopper.

    Produces deterministic route candidates so the independent TRIL layers can be built now.
    Replace this with a live GraphHopper adapter later.
    """

    def generate_candidates(
        self,
        points: Sequence[GeocodeResult],
        vehicle: VehicleProfile,
        max_alternatives: int = 3,
        blacklist_segments: Sequence[str] | None = None,
    ) -> List[RouteCandidate]:
        blacklist = set(blacklist_segments or [])
        
        # Create routes with realistic constraints for testing
        all_candidates = [
            RouteCandidate(
                route_candidate_id="route-1",
                summary="Primary interstate-heavy route",
                distance_miles=220.0,
                estimated_drive_time_hours=4.25,
                source_engine="stub-graphhopper",
                segments=[
                    Segment("seg-i81-1", "I-81 N", "interstate", 120.0, 
                           maxheight_ft=16.0,  # High clearance (safe for most trucks)
                           maxweight_lb=100000,  # High weight limit
                           maxlength_ft=75.0,  # Allows long vehicles
                           hgv_allowed=True, hazmat_allowed=True, 
                           source_flags=["osm", "overlay:njdot"]),
                    Segment("seg-i380-1", "I-380 N", "interstate", 55.0,
                           maxheight_ft=14.5,  # Moderate clearance
                           maxweight_lb=90000,
                           maxlength_ft=70.0,
                           hgv_allowed=True, hazmat_allowed=True, 
                           source_flags=["osm"]),
                    Segment("seg-local-1", "Industrial Access Rd", "local", 2.0,
                           maxheight_ft=None,  # Unknown clearance (Tier 4)
                           maxweight_lb=None,
                           maxlength_ft=None,
                           hgv_allowed=True, hazmat_allowed=True, 
                           source_flags=[]),
                    Segment("seg-warehouse-1", "Warehouse Connector", "service", 1.0,
                           maxheight_ft=15.0,
                           maxweight_lb=80000,
                           maxlength_ft=70.0,
                           hgv_allowed=True, hazmat_allowed=True, 
                           source_flags=[]),
                ],
                raw_payload={"points": [p.matched_name for p in points], "vehicle": vehicle.__dict__},
            ),
            RouteCandidate(
                route_candidate_id="route-2",
                summary="Route with low bridge",
                distance_miles=235.0,
                estimated_drive_time_hours=4.55,
                source_engine="stub-graphhopper",
                segments=[
                    Segment("seg-i78-1", "I-78 W", "interstate", 90.0,
                           maxheight_ft=15.0,
                           maxweight_lb=90000,
                           maxlength_ft=70.0,
                           hgv_allowed=True, hazmat_allowed=True, 
                           source_flags=["osm", "nbi"]),
                    Segment("seg-bridge-1", "Low Bridge on SR-309", "primary", 0.5,
                           maxheight_ft=12.0,  # LOW BRIDGE - will violate for 13.5ft vehicles
                           maxweight_lb=80000,
                           maxlength_ft=70.0,
                           hgv_allowed=True, hazmat_allowed=True,
                           source_flags=["osm", "nbi"]),
                    Segment("seg-i81-2", "I-81 N", "interstate", 130.0,
                           maxheight_ft=16.0,
                           maxweight_lb=100000,
                           maxlength_ft=75.0,
                           hgv_allowed=True, hazmat_allowed=True, 
                           source_flags=["osm", "overlay:padot"]),
                    Segment("seg-local-2", "DC Access Dr", "service", 1.5,
                           maxheight_ft=14.0,
                           maxweight_lb=80000,
                           maxlength_ft=70.0,
                           hgv_allowed=True, hazmat_allowed=True, 
                           source_flags=[]),
                ],
                raw_payload={"points": [p.matched_name for p in points], "vehicle": vehicle.__dict__},
            ),
            RouteCandidate(
                route_candidate_id="route-3",
                summary="Route with weight and length restrictions",
                distance_miles=208.0,
                estimated_drive_time_hours=4.6,
                source_engine="stub-graphhopper",
                segments=[
                    Segment("seg-urban-1", "Urban Connector", "primary", 25.0,
                           maxheight_ft=14.0,
                           maxweight_lb=60000,  # WEIGHT LIMIT - will violate for 80000lb vehicles
                           maxlength_ft=65.0,   # LENGTH LIMIT - will violate for 70ft vehicles
                           hgv_allowed=True, hazmat_allowed=False,  # NO HAZMAT
                           source_flags=[]),
                    Segment("seg-res-1", "Tight Residential Cutthrough", "residential", 3.0,
                           maxheight_ft=13.0,   # Low clearance
                           maxweight_lb=40000,  # Very low weight limit
                           maxlength_ft=55.0,   # Short vehicle only
                           max_axle_weight_lb=8000,  # Low axle weight
                           hgv_allowed=False,   # NO TRUCKS!
                           hazmat_allowed=False,
                           source_flags=[]),
                    Segment("seg-i80-1", "I-80 W", "interstate", 160.0,
                           maxheight_ft=16.0,
                           maxweight_lb=100000,
                           maxlength_ft=75.0,
                           hgv_allowed=True, hazmat_allowed=True, 
                           source_flags=["osm"]),
                ],
                raw_payload={"points": [p.matched_name for p in points], "vehicle": vehicle.__dict__},
            ),
        ]
        filtered = []
        for candidate in all_candidates:
            if any(seg.segment_id in blacklist for seg in candidate.segments):
                continue
            filtered.append(candidate)
        return filtered[:max_alternatives]


class GraphHopperLocalClient:
    def __init__(self, base_url: str, profile: str, user_agent: str, timeout_seconds: float = 12.0, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.profile = profile
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0)

    def generate_candidates(
        self,
        points: Sequence[GeocodeResult],
        vehicle: VehicleProfile,
        max_alternatives: int = 3,
        blacklist_segments: Sequence[str] | None = None,
    ) -> List[RouteCandidate]:
        payload = self._build_payload(points, vehicle, max_alternatives)
        url = f"{self.base_url}/route"

        def _do_request():
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": self.user_agent},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            raw = _retry_with_backoff(
                _do_request,
                max_retries=self.max_retries,
                breaker=self._breaker,
                label="graphhopper:route",
            )
        except RuntimeError as exc:
            raise RoutingError(str(exc)) from exc
        except Exception as exc:
            raise RoutingError(f"GraphHopper request failed: {exc}") from exc

        paths = raw.get("paths") or []
        if not paths:
            raise RoutingError("GraphHopper returned no paths")

        blacklist = set(blacklist_segments or [])
        candidates: List[RouteCandidate] = []
        for index, path in enumerate(paths, start=1):
            candidate = self._path_to_candidate(path, index, points, vehicle)
            if any(segment.segment_id in blacklist for segment in candidate.segments):
                continue
            candidates.append(candidate)
        return candidates[:max_alternatives]

    def _build_payload(self, points: Sequence[GeocodeResult], vehicle: VehicleProfile, max_alternatives: int) -> Dict[str, Any]:
        return {
            "profile": self.profile,
            "points": [[point.coordinates[1], point.coordinates[0]] for point in points],
            "points_encoded": False,
            "instructions": True,
            "calc_points": True,
            "ch.disable": True,
            "algorithm": "alternative_route",
            "alternative_route.max_paths": max_alternatives,
            "details": ["road_class", "street_name", "max_height", "max_weight", "hazmat", "toll"],
            "custom_model": {
                "priority": [{"if": "road_class == MOTORWAY", "multiply_by": 1.15}],
                "areas": {"type": "FeatureCollection", "features": []},
            },
            "hints": {
                "vehicle_height": vehicle.height_ft * 0.3048,
                "vehicle_weight": vehicle.weight_lb * 0.453592,
                "vehicle_length": vehicle.length_ft * 0.3048,
                "vehicle_axles": vehicle.axles,
                "vehicle_hazmat": vehicle.hazmat,
            },
        }

    def _path_to_candidate(self, path: Dict[str, Any], index: int, points: Sequence[GeocodeResult], vehicle: VehicleProfile) -> RouteCandidate:
        instructions = path.get("instructions") or []
        segments = [self._instruction_to_segment(instruction, seg_index) for seg_index, instruction in enumerate(instructions, start=1)]
        if not segments:
            segments = [
                Segment(
                    segment_id=f"gh-path-{index}-0",
                    name="GraphHopper path",
                    road_class="unknown",
                    distance_miles=round((path.get("distance", 0.0) or 0.0) / 1609.344, 3),
                    source_flags=["graphhopper", "osm"],
                )
            ]
        distance_miles = round((path.get("distance", 0.0) or 0.0) / 1609.344, 3)
        drive_hours = round((path.get("time", 0.0) or 0.0) / 3_600_000, 3)
        return RouteCandidate(
            route_candidate_id=f"gh-route-{index}",
            summary=path.get("description", [f"GraphHopper alternative {index}"])[0],
            distance_miles=distance_miles,
            estimated_drive_time_hours=drive_hours,
            segments=segments,
            source_engine="graphhopper-local",
            raw_payload={"points": [p.matched_name for p in points], "vehicle": vehicle.__dict__, "graphhopper_path": path},
        )

    def _instruction_to_segment(self, instruction: Dict[str, Any], seg_index: int) -> Segment:
        text = instruction.get("text") or f"Instruction {seg_index}"
        distance_miles = round((instruction.get("distance", 0.0) or 0.0) / 1609.344, 3)
        road_class = infer_road_class(text)
        return Segment(
            segment_id=f"gh-seg-{seg_index}-{slugify(text)}",
            name=text,
            road_class=road_class,
            distance_miles=distance_miles,
            hgv_allowed=True,
            hazmat_allowed=True,
            source_tags={"sign": instruction.get("sign"), "interval": instruction.get("interval")},
            source_flags=["graphhopper", "osm"],
        )


def infer_road_class(text: str) -> str:
    normalized = text.lower()
    if any(token in normalized for token in ["i-", "interstate", "motorway", "highway"]):
        return "interstate"
    if any(token in normalized for token in ["residential", "neighborhood"]):
        return "residential"
    if any(token in normalized for token in ["service", "warehouse", "terminal", "depot"]):
        return "service"
    if any(token in normalized for token in ["local", "county road", "industrial"]):
        return "local"
    return "primary"


def slugify(text: str) -> str:
    safe = urllib.parse.quote(text.lower().replace(" ", "-"), safe="-")
    return safe[:48]
