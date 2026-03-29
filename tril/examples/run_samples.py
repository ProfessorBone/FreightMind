from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tril.engine import TRILEngine
from tril.models import HOSState, RouteRequest, VehicleProfile
from tril.outputs import write_json_output


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "tril" / "out"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


SAMPLES = [
    {
        "name": "baseline",
        "request": RouteRequest(origin="S9196", destination="DC6080"),
        "summary_expectation": "ROUTE_FOUND",
    },
    {
        "name": "hos_warning",
        "request": RouteRequest(
            origin="S9196",
            destination="DC6080",
            vehicle_profile=VehicleProfile(hazmat=True),
            hos=HOSState(remaining_drive_hours=3.5, remaining_duty_hours=4.0),
        ),
        "summary_expectation": "Route busts",
    },
]


def run() -> int:
    engine = TRILEngine()
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = []

    for sample in SAMPLES:
        result = engine.run(sample["request"]).to_dict()
        fixture_path = FIXTURE_DIR / f"{sample['name']}.json"
        write_json_output(fixture_path, result)
        text = json.dumps(result, sort_keys=True)
        if sample["summary_expectation"] not in text:
            failures.append(sample["name"])
        print(f"[{sample['name']}] {result['status']}")
        route = result.get("route") or {}
        if route:
            print(f"  json={route.get('json_file')}")
            print(f"  gpx={route.get('gpx_file')}")
        hos = result.get("hos_analysis") or {}
        if hos.get("summary"):
            print(f"  hos={hos['summary']}")

    if failures:
        print(f"FAILED: {', '.join(failures)}")
        return 1

    print("All TRIL samples completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
