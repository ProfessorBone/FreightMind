from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from .engine import TRILEngine
from .models import HOSState, RouteRequest, VehicleProfile
from .outputs import write_json_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TRIL route generator")
    parser.add_argument("origin")
    parser.add_argument("destination")
    parser.add_argument("--stop", action="append", default=[], help="Intermediate stop. Repeat for multiple stops.")
    parser.add_argument("--height-ft", type=float, default=13.5)
    parser.add_argument("--weight-lb", type=float, default=80000.0)
    parser.add_argument("--length-ft", type=float, default=70.0)
    parser.add_argument("--axles", type=int, default=5)
    parser.add_argument("--hazmat", action="store_true")
    parser.add_argument("--remaining-drive-hours", type=float)
    parser.add_argument("--remaining-duty-hours", type=float)
    parser.add_argument("--json-out", type=Path, help="Write canonical JSON result to this path.")
    parser.add_argument("--gpx-out", type=Path, help="Write GPX route export to this path.")
    parser.add_argument("--compact-json", action="store_true", help="Emit compact canonical JSON when used with --json-out.")
    parser.add_argument("--print-summary", action="store_true", help="Print operator-focused text summary instead of raw JSON.")
    parser.add_argument("--no-write-defaults", action="store_true", help="Do not write default tril/out artifacts from engine output.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    hos = None
    if (args.remaining_drive_hours is None) ^ (args.remaining_duty_hours is None):
        parser.error("Provide both --remaining-drive-hours and --remaining-duty-hours together.")
    if args.remaining_drive_hours is not None and args.remaining_duty_hours is not None:
        hos = HOSState(args.remaining_drive_hours, args.remaining_duty_hours)

    request = RouteRequest(
        origin=args.origin,
        destination=args.destination,
        stops=args.stop,
        vehicle_profile=VehicleProfile(
            height_ft=args.height_ft,
            weight_lb=args.weight_lb,
            length_ft=args.length_ft,
            axles=args.axles,
            hazmat=args.hazmat,
        ),
        hos=hos,
    )
    engine = TRILEngine()
    result = engine.run(request)

    if args.json_out:
        write_json_output(args.json_out, result.to_dict(), compact=args.compact_json)
    if args.gpx_out and result.route:
        source_gpx = Path(result.route["gpx_file"])
        args.gpx_out.parent.mkdir(parents=True, exist_ok=True)
        if source_gpx.exists():
            shutil.copyfile(source_gpx, args.gpx_out)

    if args.no_write_defaults and result.route:
        default_json = Path(result.route["json_file"])
        default_gpx = Path(result.route["gpx_file"])
        if default_json.exists():
            default_json.unlink()
        if default_gpx.exists():
            default_gpx.unlink()

    if args.print_summary:
        print(render_summary(result.to_dict()))
        return

    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))



def render_summary(payload: dict) -> str:
    if payload["status"] != "ROUTE_FOUND":
        error = payload.get("error") or {}
        return f"{payload['status']}: {error.get('message', 'Unknown failure')}"

    route = payload["route"] or {}
    hos = payload.get("hos_analysis") or {}
    warnings = (payload.get("constraint_report") or {}).get("warnings") or []
    lines = [
        f"TRIL route: {route.get('summary', 'Unnamed route')}",
        f"Distance/time: {route.get('distance_miles')} mi / {route.get('estimated_drive_time_hours')} hr",
        f"Scores: safety {route.get('safety_score')} | confidence {route.get('confidence_score')} | preference {route.get('preference_score')}",
        f"Link: {route.get('shareable_link')}",
        f"HOS: {hos.get('summary', 'n/a')}",
    ]
    if warnings:
        lines.append(f"Warnings: {len(warnings)} constraint-confidence warning(s)")
    if route.get("gpx_file"):
        lines.append(f"GPX: {route['gpx_file']}")
    if route.get("json_file"):
        lines.append(f"JSON: {route['json_file']}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
