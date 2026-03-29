from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from .models import HOSAnalysis, HOSState, ResetRecommendation, RouteCandidate


def load_walmart_resets(data_dir: Path) -> List[ResetRecommendation]:
    """Load Walmart Okay Break locations from JSON data."""
    walmart_path = data_dir / "walmart_okay_breaks.json"
    
    # Fallback to hardcoded if file doesn't exist
    if not walmart_path.exists():
        return [
            ResetRecommendation(
                location_name="Pilot Travel Center - Carlisle, PA",
                location_type="truck_stop",
                distance_from_origin_miles=154.2,
                drive_time_to_reset_hours=3.1,
                coordinates=(40.2012, -77.1890),
                post_reset_remaining_miles=80.8,
            ),
            ResetRecommendation(
                location_name="Love's Travel Stop - Hamburg, PA",
                location_type="truck_stop",
                distance_from_origin_miles=118.4,
                drive_time_to_reset_hours=2.4,
                coordinates=(40.5556, -76.0001),
                post_reset_remaining_miles=116.6,
            ),
        ]
    
    try:
        with walmart_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        resets = []
        
        # Add Walmart locations from JSON
        for record in data.get("records", []):
            if isinstance(record.get("coordinates"), list) and len(record["coordinates"]) >= 2:
                resets.append(
                    ResetRecommendation(
                        location_name=record.get("location_name", "Walmart"),
                        location_type=record.get("location_type", "okay_break"),
                        distance_from_origin_miles=0.0,  # Would be calculated based on route
                        drive_time_to_reset_hours=0.0,   # Would be calculated based on route
                        coordinates=tuple(record["coordinates"][:2]),
                        post_reset_remaining_miles=0.0,  # Would be calculated based on route
                    )
                )
        
        # Add some additional known truck stops (these would come from driver preferences in real system)
        resets.extend([
            ResetRecommendation(
                location_name="Pilot Travel Center - Carlisle, PA",
                location_type="preferred_stop",
                distance_from_origin_miles=154.2,
                drive_time_to_reset_hours=3.1,
                coordinates=(40.2012, -77.1890),
                post_reset_remaining_miles=80.8,
            ),
            ResetRecommendation(
                location_name="Love's Travel Stop - Hamburg, PA",
                location_type="preferred_stop",
                distance_from_origin_miles=118.4,
                drive_time_to_reset_hours=2.4,
                coordinates=(40.5556, -76.0001),
                post_reset_remaining_miles=116.6,
            ),
        ])
        
        return resets
        
    except (json.JSONDecodeError, KeyError) as e:
        # Fall back to hardcoded on parse error
        return [
            ResetRecommendation(
                location_name="Pilot Travel Center - Carlisle, PA",
                location_type="truck_stop",
                distance_from_origin_miles=154.2,
                drive_time_to_reset_hours=3.1,
                coordinates=(40.2012, -77.1890),
                post_reset_remaining_miles=80.8,
            ),
            ResetRecommendation(
                location_name="Love's Travel Stop - Hamburg, PA",
                location_type="truck_stop",
                distance_from_origin_miles=118.4,
                drive_time_to_reset_hours=2.4,
                coordinates=(40.5556, -76.0001),
                post_reset_remaining_miles=116.6,
            ),
        ]


def analyze_hos(route: RouteCandidate, hos: Optional[HOSState], data_dir: Optional[Path] = None) -> HOSAnalysis:
    if hos is None:
        return HOSAnalysis(summary="No HOS state supplied; reset analysis skipped")

    route_drive_time = route.estimated_drive_time_hours
    route_duty_time = round(route_drive_time + 0.5, 2)
    drive_overage = round(max(0.0, route_drive_time - hos.remaining_drive_hours), 2)
    duty_overage = round(max(0.0, route_duty_time - hos.remaining_duty_hours), 2)
    projected_drive = round(hos.remaining_drive_hours - route_drive_time, 2)
    projected_duty = round(hos.remaining_duty_hours - route_duty_time, 2)
    hos_warning = drive_overage > 0 or duty_overage > 0

    if not hos_warning:
        return HOSAnalysis(
            hos_warning=False,
            remaining_drive_hours=hos.remaining_drive_hours,
            remaining_duty_hours=hos.remaining_duty_hours,
            route_drive_time_hours=route_drive_time,
            route_duty_time_hours=route_duty_time,
            projected_drive_hours_remaining=projected_drive,
            projected_duty_hours_remaining=projected_duty,
            overage_hours=0.0,
            duty_overage_hours=0.0,
            summary=(
                f"Route fits current clocks. Drive slack {projected_drive:.2f}h, "
                f"duty slack {projected_duty:.2f}h."
            ),
        )

    # Load reset candidates from data
    if data_dir is None:
        data_dir = Path(__file__).parent / "data"
    
    reset_candidates = load_walmart_resets(data_dir)
    
    primary_reset = _pick_reset(route, hos, reset_candidates)
    alternatives = [candidate for candidate in reset_candidates if candidate.location_name != primary_reset.location_name][:2]
    trigger = "drive" if drive_overage >= duty_overage else "duty"
    
    return HOSAnalysis(
        hos_warning=True,
        remaining_drive_hours=hos.remaining_drive_hours,
        remaining_duty_hours=hos.remaining_duty_hours,
        route_drive_time_hours=route_drive_time,
        route_duty_time_hours=route_duty_time,
        projected_drive_hours_remaining=projected_drive,
        projected_duty_hours_remaining=projected_duty,
        overage_hours=drive_overage,
        duty_overage_hours=duty_overage,
        summary=(
            f"Route busts {trigger} clock. "
            f"Drive over by {drive_overage:.2f}h, duty over by {duty_overage:.2f}h. "
            f"Stage a reset before {primary_reset.location_name}."
        ),
        recommended_reset=primary_reset,
        alternative_resets=alternatives,
    )


def _pick_reset(route: RouteCandidate, hos: HOSState, reset_candidates: List[ResetRecommendation]) -> ResetRecommendation:
    target_drive_window = max(hos.remaining_drive_hours - 0.3, 0.0)
    
    # Priority order: okay_break > preferred_stop > truck_stop
    priority_order = {"okay_break": 1, "preferred_stop": 2, "truck_stop": 3}
    
    # Sort candidates by priority and then by whether they fit in drive window
    sorted_candidates = sorted(
        reset_candidates,
        key=lambda c: (
            priority_order.get(c.location_type, 4),
            abs(c.drive_time_to_reset_hours - target_drive_window) if c.drive_time_to_reset_hours > 0 else float('inf')
        )
    )
    
    # Find best candidate that fits in window
    for candidate in sorted_candidates:
        if candidate.drive_time_to_reset_hours > 0 and candidate.drive_time_to_reset_hours <= target_drive_window + 0.5:
            return candidate
    
    # If none fit, return the highest priority one
    return sorted_candidates[0] if sorted_candidates else reset_candidates[0]