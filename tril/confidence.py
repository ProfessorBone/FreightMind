from __future__ import annotations

from typing import Dict, Iterable

from .models import ConstraintWarning, RouteCandidate, Segment


def classify_segment_tier(segment: Segment) -> int:
    flags = set(segment.source_flags)
    if "osm" in flags and ({f for f in flags if f.startswith("overlay:")} or "nbi" in flags):
        return 1
    if "osm" in flags or "nbi" in flags or any(f.startswith("overlay:") for f in flags):
        return 2
    if segment.road_class in {"interstate", "motorway", "trunk", "primary"}:
        return 3
    return 4


def annotate_route_confidence(route: RouteCandidate) -> None:
    for segment in route.segments:
        segment.confidence_tier = classify_segment_tier(segment)


def route_confidence_breakdown(route: RouteCandidate) -> Dict[str, float]:
    total = sum(seg.distance_miles for seg in route.segments) or 1.0
    buckets = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    for segment in route.segments:
        tier = segment.confidence_tier or classify_segment_tier(segment)
        buckets[tier] += segment.distance_miles
    return {
        "tier_1_pct": round((buckets[1] / total) * 100, 2),
        "tier_2_pct": round((buckets[2] / total) * 100, 2),
        "tier_3_pct": round((buckets[3] / total) * 100, 2),
        "tier_4_pct": round((buckets[4] / total) * 100, 2),
    }


def route_confidence_score(route: RouteCandidate) -> float:
    total = sum(seg.distance_miles for seg in route.segments) or 1.0
    weights = {1: 1.0, 2: 0.85, 3: 0.6, 4: 0.2}
    score = 0.0
    for segment in route.segments:
        tier = segment.confidence_tier or classify_segment_tier(segment)
        score += segment.distance_miles * weights[tier]
    return round(score / total, 4)


def confidence_warnings(route: RouteCandidate) -> list[ConstraintWarning]:
    warnings = []
    for segment in route.segments:
        tier = segment.confidence_tier or classify_segment_tier(segment)
        if tier == 4:
            warnings.append(
                ConstraintWarning(
                    type="LOW_CONFIDENCE_SEGMENT",
                    segment_id=segment.segment_id,
                    tier=tier,
                    description=f"No reliable constraint data available for {segment.name}",
                )
            )
    return warnings
