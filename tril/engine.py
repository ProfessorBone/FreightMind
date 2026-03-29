from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import List

from .confidence import annotate_route_confidence, route_confidence_breakdown, route_confidence_score
from .config import TRILConfig
from .constraints import validate_route
from .data_layers import ReferenceDataCatalog
from .geocoding import GeocodingError, NominatimGeocoder, StubGeocoder, default_curated_locations
from .hos import analyze_hos
from .logging_utils import append_jsonl, audit_record, check_rate_limit, continuum_trace_id, cost_metadata
from .metrics import metrics
from .models import GeocodeResult, RouteCandidate, RouteRequest, RouteResult, RouteScores, ToolError
from .outputs import build_google_maps_link, write_gpx_output, write_json_output
from .routing import GraphHopperLocalClient, StubGraphHopperClient
from .versions import data_staleness_warning, summarize_staleness


class TRILEngine:
    def __init__(self, config: TRILConfig | None = None):
        self.config = config or TRILConfig()
        
        # Service mode switching based on environment configuration
        geocoder_mode = self.config.services.geocoder_mode
        if geocoder_mode == "nominatim":
            self.geocoder = NominatimGeocoder(
                base_url=self.config.services.nominatim_url,
                user_agent=self.config.services.user_agent,
                timeout_seconds=self.config.services.request_timeout_seconds,
                bounded_countries=["us"]
            )
            print(f"[TRIL] Using Nominatim geocoder at {self.config.services.nominatim_url}")
        else:
            self.geocoder = StubGeocoder(default_curated_locations())
            print(f"[TRIL] Using stub geocoder (mode: {geocoder_mode})")
        
        router_mode = self.config.services.router_mode
        if router_mode == "graphhopper":
            self.router = GraphHopperLocalClient(
                base_url=self.config.services.graphhopper_url,
                profile=self.config.services.graphhopper_profile,
                user_agent=self.config.services.user_agent,
                timeout_seconds=self.config.services.request_timeout_seconds
            )
            print(f"[TRIL] Using GraphHopper router at {self.config.services.graphhopper_url}")
        else:
            self.router = StubGraphHopperClient()
            print(f"[TRIL] Using stub router (mode: {router_mode})")
        
        self.reference_data = ReferenceDataCatalog(self.config.data_dir)
        self.reference_versions = self.reference_data.build_version_summary()

    def run(self, request: RouteRequest) -> RouteResult:
        # Continuum governance: rate limiting
        if not check_rate_limit():
            metrics.record_route("RATE_LIMITED", 0.0)
            return RouteResult(
                status="ENGINE_ERROR",
                error=asdict(ToolError(code="RATE_LIMITED", message="Too many requests — try again shortly")),
            )

        # Continuum governance: trace context and cost tracking
        self._trace_id = continuum_trace_id()
        self._start_time = time.monotonic()
        self._geocode_calls = 0
        self._route_calls = 0

        try:
            points = self._geocode_request(request)
            self._geocode_calls = len([request.origin, *request.stops, request.destination])
        except GeocodingError as exc:
            metrics.record_route("GEOCODING_FAILED", time.monotonic() - self._start_time)
            return RouteResult(
                status="GEOCODING_FAILED",
                error=asdict(ToolError(code="GEOCODING_FAILED", message=str(exc), failed_input=exc.failed_input)),
            )

        blacklist: list[str] = []
        retry_log: list[dict] = []
        valid_routes: list[tuple[RouteCandidate, dict, dict, dict]] = []
        least_bad: tuple[RouteCandidate, dict] | None = None

        for attempt in range(1, self.config.max_retry_attempts + 1):
            self._route_calls += 1
            candidates = self.router.generate_candidates(
                points=points,
                vehicle=request.vehicle_profile,
                max_alternatives=self.config.route_alternatives,
                blacklist_segments=blacklist,
            )
            if not candidates:
                break

            for candidate in candidates:
                self.reference_data.apply_reference_overlays(candidate.segments)
                annotate_route_confidence(candidate)
                report = validate_route(candidate, request.vehicle_profile, source_versions=self.reference_versions)
                report_dict = asdict(report)
                retry_log.append({
                    "attempt": attempt,
                    "route_candidate_id": candidate.route_candidate_id,
                    "violations": [asdict(v) for v in report.violations],
                    "warnings": [asdict(w) for w in report.warnings],
                })
                if report.violations_found == 0:
                    scores = self._score_route(candidate)
                    hos_analysis = asdict(analyze_hos(candidate, request.hos, data_dir=self.config.data_dir))
                    valid_routes.append((candidate, asdict(scores), hos_analysis, report_dict))
                else:
                    if least_bad is None or report.violations_found < least_bad[1]["violations_found"]:
                        least_bad = (candidate, report_dict)
                    blacklist.extend(v.segment_id for v in report.violations)

            if valid_routes:
                break

        if not valid_routes:
            error = ToolError(
                code="NO_SAFE_ROUTE",
                message="No validated truck-safe route found within retry limit",
                retry_report={"attempts": len(retry_log), "violations_per_attempt": retry_log},
            )
            payload = RouteResult(status="NO_SAFE_ROUTE", error=asdict(error))
            if least_bad:
                payload.alternatives = [{
                    "route_candidate_id": least_bad[0].route_candidate_id,
                    "summary": least_bad[0].summary,
                    "constraint_report": least_bad[1],
                }]
            metrics.record_route("NO_SAFE_ROUTE", time.monotonic() - self._start_time)
            return payload

        ranked = sorted(valid_routes, key=lambda item: (-item[1]["safety_score"], -item[1]["confidence_score"], -item[1]["preference_score"]))
        top_candidate, top_scores, top_hos, top_report = ranked[0]
        result = RouteResult(
            status="ROUTE_FOUND",
            route=self._route_payload(request, top_candidate, top_scores, points),
            constraint_report=top_report,
            hos_analysis=top_hos,
            alternatives=[self._alternative_payload(candidate, scores, report) for candidate, scores, _, report in ranked[1:]],
        )
        self._write_outputs(request, result, points, top_candidate)
        self._log_validation(request, result)
        metrics.record_route(
            "ROUTE_FOUND",
            time.monotonic() - self._start_time,
            confidence_score=top_scores.get("confidence_score"),
            safety_score=top_scores.get("safety_score"),
            violations_found=top_report.get("violations_found", 0),
        )
        return result

    def _geocode_request(self, request: RouteRequest) -> List[GeocodeResult]:
        return self.geocoder.geocode_many([request.origin, *request.stops, request.destination])

    def _score_route(self, candidate: RouteCandidate) -> RouteScores:
        confidence = route_confidence_score(candidate)
        tiers = route_confidence_breakdown(candidate)
        road_classes = {segment.road_class for segment in candidate.segments}
        preference_bonus = 0.15 if "interstate" in road_classes else 0.0
        urban_penalty = 0.2 if "residential" in road_classes else 0.0
        safety = round(max(0.0, 1.0 - (tiers["tier_4_pct"] / 100.0) - urban_penalty), 4)
        preference = round(max(0.0, min(1.0, 0.7 + preference_bonus - urban_penalty)), 4)
        return RouteScores(confidence_score=confidence, safety_score=safety, preference_score=preference, data_tiers=tiers)

    def _route_payload(self, request: RouteRequest, candidate: RouteCandidate, scores: dict, points: List[GeocodeResult]) -> dict:
        warning = data_staleness_warning(self.config.versions, stale_after_days=self.config.stale_after_days)
        route_slug = self._route_slug(points)
        json_path = self.config.out_dir / f"{route_slug}.json"
        gpx_path = self.config.out_dir / f"{route_slug}.gpx"
        return {
            "route_candidate_id": candidate.route_candidate_id,
            "summary": candidate.summary,
            "origin": request.origin,
            "destination": request.destination,
            "stops": request.stops,
            "distance_miles": candidate.distance_miles,
            "estimated_drive_time_hours": candidate.estimated_drive_time_hours,
            "gpx_file": str(gpx_path),
            "json_file": str(json_path),
            "source_engine": candidate.source_engine,
            "confidence_score": scores["confidence_score"],
            "safety_score": scores["safety_score"],
            "preference_score": scores["preference_score"],
            "data_tiers": scores["data_tiers"],
            "shareable_link": build_google_maps_link(points),
            "data_staleness_warning": warning,
            "reference_data_status": summarize_staleness(self.reference_versions),
            "waypoints": [
                {
                    "input": point.input_text,
                    "matched_name": point.matched_name,
                    "lat": point.coordinates[0],
                    "lon": point.coordinates[1],
                    "confidence": point.confidence,
                }
                for point in points
            ],
            "segments": [
                {
                    "segment_id": segment.segment_id,
                    "name": segment.name,
                    "road_class": segment.road_class,
                    "distance_miles": segment.distance_miles,
                    "confidence_tier": segment.confidence_tier,
                    "source_flags": segment.source_flags,
                }
                for segment in candidate.segments
            ],
        }

    def _alternative_payload(self, candidate: RouteCandidate, scores: dict, report: dict) -> dict:
        return {
            "route_candidate_id": candidate.route_candidate_id,
            "distance_miles": candidate.distance_miles,
            "estimated_drive_time_hours": candidate.estimated_drive_time_hours,
            "confidence_score": scores["confidence_score"],
            "safety_score": scores["safety_score"],
            "preference_score": scores["preference_score"],
            "summary": candidate.summary,
            "constraint_report": report,
        }

    def _write_outputs(self, request: RouteRequest, result: RouteResult, points: List[GeocodeResult], route: RouteCandidate) -> None:
        if result.route is None:
            return
        json_path = Path(result.route["json_file"])
        gpx_path = Path(result.route["gpx_file"])
        write_json_output(json_path, result.to_dict())
        write_gpx_output(gpx_path, json_path.stem, points, route=route)

    def _log_validation(self, request: RouteRequest, result: RouteResult) -> None:
        metadata = {
            "origin": request.origin,
            "destination": request.destination,
            "stops": request.stops,
            "vehicle_profile": asdict(request.vehicle_profile),
            "reference_versions": summarize_staleness(self.reference_versions),
        }
        cost = cost_metadata(
            self._start_time,
            geocode_calls=self._geocode_calls,
            route_calls=self._route_calls,
        )
        append_jsonl(
            self.config.logs_dir / "validation.jsonl",
            audit_record(
                "route_generation",
                result.to_dict(),
                metadata=metadata,
                trace_id=self._trace_id,
                cost=cost,
            ),
        )

    def _route_slug(self, points: List[GeocodeResult]) -> str:
        origin = self._slugify(points[0].matched_name)
        destination = self._slugify(points[-1].matched_name)
        return f"TRIL_{origin}_{destination}"

    def _slugify(self, value: str) -> str:
        return "".join(char if char.isalnum() else "_" for char in value).strip("_")[:80]
