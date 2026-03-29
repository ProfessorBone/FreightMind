from __future__ import annotations

from .confidence import confidence_warnings
from .models import ConstraintReport, RouteCandidate, SourceVersionSummary, ValidationTrace, VehicleProfile, Violation


LIMIT_FIELDS = (
    "maxheight_ft",
    "maxweight_lb",
    "maxlength_ft",
    "max_axle_weight_lb",
)


def validate_route(
    route: RouteCandidate,
    vehicle: VehicleProfile,
    source_versions: dict[str, SourceVersionSummary] | None = None,
) -> ConstraintReport:
    violations: list[Violation] = []
    traces: list[ValidationTrace] = []
    version_map = {key: summary.__dict__ for key, summary in (source_versions or {}).items()}

    for segment in route.segments:
        trace = ValidationTrace(
            segment_id=segment.segment_id,
            segment_name=segment.name,
            applied_sources=list(segment.source_flags),
            matched_reference_ids=_matched_reference_ids(segment),
            applied_limits={field: getattr(segment, field) for field in LIMIT_FIELDS if getattr(segment, field) is not None},
            source_age_days={
                key: summary.age_days
                for key, summary in (source_versions or {}).items()
                if key == "nbi" or key == "state_overlays"
            },
            stale_sources=[
                key
                for key, summary in (source_versions or {}).items()
                if summary.stale_after_days is not None and summary.age_days is not None and summary.age_days > summary.stale_after_days
            ],
        )

        if segment.maxheight_ft is not None and segment.maxheight_ft < vehicle.height_ft:
            violations.append(Violation("HEIGHT_VIOLATION", segment.segment_id, segment.maxheight_ft, vehicle.height_ft, f"{segment.name} height below vehicle"))
            trace.notes.append("Vehicle height exceeds applied segment clearance")
        if segment.maxweight_lb is not None and segment.maxweight_lb < vehicle.weight_lb:
            violations.append(Violation("WEIGHT_VIOLATION", segment.segment_id, segment.maxweight_lb, vehicle.weight_lb, f"{segment.name} weight below vehicle"))
            trace.notes.append("Vehicle gross weight exceeds posted segment limit")
        if segment.maxlength_ft is not None and segment.maxlength_ft < vehicle.length_ft:
            violations.append(Violation("LENGTH_VIOLATION", segment.segment_id, segment.maxlength_ft, vehicle.length_ft, f"{segment.name} length below vehicle"))
            trace.notes.append("Vehicle overall length exceeds applied segment limit")
        if segment.hgv_allowed is False:
            violations.append(Violation("HGV_PROHIBITED", segment.segment_id, None, None, f"{segment.name} prohibits HGV traffic"))
            trace.notes.append("Segment prohibits truck/HGV traffic")
        if vehicle.hazmat and segment.hazmat_allowed is False:
            violations.append(Violation("HAZMAT_VIOLATION", segment.segment_id, None, None, f"{segment.name} restricts hazmat"))
            trace.notes.append("Hazmat-restricted segment encountered")
        if segment.max_axle_weight_lb is not None:
            estimated_axle_load = (vehicle.weight_lb / max(vehicle.axles, 1)) * 1.10
            if estimated_axle_load > segment.max_axle_weight_lb:
                violations.append(Violation("AXLE_WEIGHT_VIOLATION", segment.segment_id, segment.max_axle_weight_lb, estimated_axle_load, f"{segment.name} axle load exceeded"))
                trace.notes.append("Estimated axle load exceeds applied segment limit")

        if not trace.notes:
            trace.notes.append("No segment-level hard constraint violations detected")
        traces.append(trace)

    return ConstraintReport(
        violations_found=len(violations),
        violations=violations,
        warnings=confidence_warnings(route),
        validation_trace=traces,
        source_versions=version_map,
    )



def _matched_reference_ids(segment) -> dict[str, str]:
    matches: dict[str, str] = {}
    nbi_tag = segment.source_tags.get("nbi") if isinstance(segment.source_tags, dict) else None
    state_tag = segment.source_tags.get("state_overlay") if isinstance(segment.source_tags, dict) else None
    if isinstance(nbi_tag, dict) and nbi_tag.get("structure_id"):
        matches["nbi_structure_id"] = str(nbi_tag["structure_id"])
    if isinstance(state_tag, dict) and state_tag.get("corridor_id"):
        matches["state_corridor_id"] = str(state_tag["corridor_id"])
    return matches
