from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import urlencode
from xml.sax.saxutils import escape

from .models import GeocodeResult, RouteCandidate


def canonicalize_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): canonicalize_payload(value) for key, value in sorted(payload.items(), key=lambda item: str(item[0]))}
    if isinstance(payload, list):
        return [canonicalize_payload(value) for value in payload]
    if isinstance(payload, tuple):
        return [canonicalize_payload(value) for value in payload]
    return payload


def build_google_maps_link(points: List[GeocodeResult]) -> str:
    if len(points) < 2:
        return ""
    origin = f"{points[0].coordinates[0]},{points[0].coordinates[1]}"
    destination = f"{points[-1].coordinates[0]},{points[-1].coordinates[1]}"
    waypoints = "|".join(f"{p.coordinates[0]},{p.coordinates[1]}" for p in points[1:-1])
    query = {"api": 1, "origin": origin, "destination": destination}
    if waypoints:
        query["waypoints"] = waypoints
    return "https://www.google.com/maps/dir/?" + urlencode(query)


def write_json_output(path: Path, payload: Dict, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = canonicalize_payload(payload)
    if compact:
        content = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    else:
        content = json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False)
        content += "\n"
    path.write_text(content, encoding="utf-8")


def _iso8601_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_xml_text(value: str, *, max_length: int = 120) -> str:
    return escape((value or "")[:max_length], {'"': '&quot;', "'": '&apos;'})


def write_gpx_output(path: Path, route_name: str, points: List[GeocodeResult], *, route: RouteCandidate | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = _iso8601_now()
    safe_route_name = _safe_xml_text(route_name, max_length=80)
    route_desc = "TRIL route export"
    if route is not None:
        route_desc = f"TRIL route export | {route.summary} | {route.distance_miles:.1f} mi | {route.estimated_drive_time_hours:.2f} hr"
    rtepts = []
    for index, point in enumerate(points[:500], start=1):
        lat, lon = point.coordinates
        rtepts.append(
            "\n".join(
                [
                    f'    <rtept lat="{lat:.6f}" lon="{lon:.6f}">',
                    f"      <name>{_safe_xml_text(point.matched_name, max_length=60)}</name>",
                    f"      <desc>{_safe_xml_text(point.input_text, max_length=100)}</desc>",
                    f"      <sym>{'Flag, Blue' if index in {1, len(points[:500])} else 'Dot'}</sym>",
                    "    </rtept>",
                ]
            )
        )
    trkpts = []
    if route is not None:
        for segment in route.segments[:1000]:
            marker = next((point for point in points if point.matched_name.split(",")[0] in segment.name), None)
            if marker is None:
                marker = points[0]
            lat, lon = marker.coordinates
            trkpts.append(
                "\n".join(
                    [
                        f'        <trkpt lat="{lat:.6f}" lon="{lon:.6f}">',
                        f"          <name>{_safe_xml_text(segment.name, max_length=60)}</name>",
                        f"          <desc>{_safe_xml_text(segment.road_class, max_length=30)} | {segment.distance_miles:.1f} mi</desc>",
                        "        </trkpt>",
                    ]
                )
            )
    content = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="TRIL" xmlns="http://www.topografix.com/GPX/1/1">',
            "  <metadata>",
            f"    <name>{safe_route_name}</name>",
            f"    <desc>{_safe_xml_text(route_desc, max_length=200)}</desc>",
            f"    <time>{timestamp}</time>",
            "  </metadata>",
            f"  <rte><name>{safe_route_name}</name><desc>{_safe_xml_text(route_desc, max_length=200)}</desc>",
            *rtepts,
            "  </rte>",
            "  <trk>",
            f"    <name>{safe_route_name}</name>",
            "    <trkseg>",
            *trkpts,
            "    </trkseg>",
            "  </trk>",
            "</gpx>",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
