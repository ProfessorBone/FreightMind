#!/usr/bin/env python3
"""
TRIL Production Validation Suite
50+ test cases covering real-world scenarios from Faheem's routes.

Calls generate_truck_safe_route directly (no MCP overhead).
MCP transport was already validated in will_graham_integration.py.

Usage:
    python -m tril.tests.production_validation              # stub mode
    python -m tril.tests.production_validation --live        # live services
    python -m tril.tests.production_validation --live --json # JSON output
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add workspace to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tril.mcp_tool import generate_truck_safe_route

# Faheem's truck
FAHEEM = {
    "height_ft": 13.5,
    "weight_lb": 80000,
    "length_ft": 70,
    "axles": 5,
    "hazmat": False,
}


@dataclass
class Case:
    name: str
    category: str
    args: dict[str, Any]
    checks: list[str] = field(default_factory=list)


@dataclass
class Result:
    name: str
    category: str
    passed: bool
    checks_passed: int = 0
    checks_total: int = 0
    detail: str = ""
    elapsed: float = 0.0


# ---------------------------------------------------------------------------
# Check functions — each returns (passed: bool, detail: str)
# ---------------------------------------------------------------------------

def chk_status_found(d): return d["status"] == "ROUTE_FOUND", f"status={d['status']}"
def chk_status_route_or_rejected(d): return d["status"] in ("ROUTE_FOUND", "NO_SAFE_ROUTE"), f"status={d['status']}"
def chk_status_not_crash(d): return d["status"] in ("ROUTE_FOUND", "NO_SAFE_ROUTE", "ENGINE_ERROR", "GEOCODING_FAILED"), f"status={d['status']}"
def chk_status_geocode_fail(d): return d["status"] == "GEOCODING_FAILED", f"status={d['status']}"
def chk_has_route(d): return d.get("route") is not None, "route present" if d.get("route") else "no route"
def chk_distance_positive(d): v = d.get("route", {}).get("distance_miles", 0); return v > 0, f"dist={v}"
def chk_time_positive(d): v = d.get("route", {}).get("estimated_drive_time_hours", 0); return v > 0, f"time={v}"
def chk_gpx_path(d): g = d.get("route", {}).get("gpx_file", ""); return g.endswith(".gpx"), f"gpx={'ok' if g.endswith('.gpx') else g}"
def chk_confidence_above_zero(d): c = d.get("route", {}).get("confidence_score", 0); return c > 0, f"conf={c}"
def chk_safety_above_half(d): s = d.get("route", {}).get("safety_score", 0); return s >= 0.5, f"safety={s}"
def chk_has_constraint_report(d): return "violations_found" in d.get("constraint_report", {}), "cr present"
def chk_zero_violations(d): v = d.get("constraint_report", {}).get("violations_found", -1); return v == 0, f"violations={v}"
def chk_has_hos(d): return "hos_analysis" in d, "hos present"
def chk_hos_warning_true(d): w = d.get("hos_analysis", {}).get("hos_warning"); return w is True, f"warn={w}"
def chk_hos_warning_false(d): w = d.get("hos_analysis", {}).get("hos_warning"); return w is False, f"warn={w}"
def chk_has_data_tiers(d): return "tier_1_pct" in d.get("route", {}).get("data_tiers", {}), "tiers present"
def chk_error_present(d): return d.get("error") is not None, "error present"
def chk_error_has_code(d): c = d.get("error", {}).get("code", ""); return bool(c), f"code={c}"

def chk_wg_parseable(d):
    try:
        r = d["route"]; float(r["distance_miles"]); float(r["estimated_drive_time_hours"])
        str(r["gpx_file"]); float(r["confidence_score"]); float(r["safety_score"])
        return True, "parseable"
    except (KeyError, TypeError, ValueError) as e:
        return False, f"parse error: {e}"


CHECK_REGISTRY = {fn.__name__: fn for fn in [
    chk_status_found, chk_status_route_or_rejected, chk_status_not_crash, chk_status_geocode_fail, chk_has_route, chk_distance_positive,
    chk_time_positive, chk_gpx_path, chk_confidence_above_zero, chk_safety_above_half,
    chk_has_constraint_report, chk_zero_violations, chk_has_hos, chk_hos_warning_true,
    chk_hos_warning_false, chk_has_data_tiers, chk_error_present, chk_error_has_code,
    chk_wg_parseable,
]}

# Standard check suites
ROUTE_OK = ["chk_status_found", "chk_has_route", "chk_distance_positive", "chk_time_positive",
            "chk_gpx_path", "chk_confidence_above_zero", "chk_has_constraint_report", "chk_has_hos"]
ROUTE_FULL = ROUTE_OK + ["chk_safety_above_half", "chk_has_data_tiers", "chk_wg_parseable"]


# ---------------------------------------------------------------------------
# Test cases — 50+ covering all categories
# ---------------------------------------------------------------------------

def o(live: bool, stub_val: str, live_val: str) -> str:
    return live_val if live else stub_val


def build_cases(live: bool) -> list[Case]:
    cases = [
        # === BASIC ROUTING (10) ===
        Case("basic_route", "Basic Routing",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM}, ROUTE_FULL),
        Case("reverse_route", "Basic Routing",
             {"origin": o(live, "DC6080", "Carlisle, PA"), "destination": o(live, "S9196", "Tobyhanna, PA"),
              "vehicle_profile": FAHEEM}, ROUTE_OK),
        Case("short_route", "Basic Routing",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "S9196", "Stroudsburg, PA"),
              "vehicle_profile": FAHEEM}, ["chk_status_found"]),
        Case("default_vehicle", "Basic Routing",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA")},
             ROUTE_OK),
        Case("with_stops", "Basic Routing",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Harrisburg, PA"),
              "stops": [o(live, "Tobyhanna, PA", "Scranton, PA")],
              "vehicle_profile": FAHEEM}, ["chk_status_not_crash"]),
        Case("empty_stops_list", "Basic Routing",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "stops": [], "vehicle_profile": FAHEEM}, ROUTE_OK),
        Case("long_distance", "Basic Routing",
             {"origin": o(live, "S9196", "Tobyhanna, PA"),
              "destination": o(live, "DC6080", "Pittsburgh, PA"),
              "vehicle_profile": FAHEEM}, ["chk_status_found", "chk_has_route"]),
        Case("same_origin_dest", "Basic Routing",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "S9196", "Tobyhanna, PA"),
              "vehicle_profile": FAHEEM}, ["chk_status_found"]),
        Case("no_vehicle_profile", "Basic Routing",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA")},
             ["chk_status_found", "chk_has_route"]),
        Case("explicit_axles", "Basic Routing",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": {**FAHEEM, "axles": 6}}, ROUTE_OK),

        # === HOS SCENARIOS (10) ===
        Case("hos_plenty_of_time", "HOS Analysis",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "hos": {"remaining_drive_hours": 10.0, "remaining_duty_hours": 13.0}},
             ROUTE_OK + ["chk_hos_warning_false"]),
        Case("hos_tight_drive_clock", "HOS Analysis",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "hos": {"remaining_drive_hours": 1.5, "remaining_duty_hours": 10.0}},
             ["chk_status_found", "chk_has_hos", "chk_hos_warning_true"]),
        Case("hos_tight_duty_clock", "HOS Analysis",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "hos": {"remaining_drive_hours": 8.0, "remaining_duty_hours": 2.0}},
             ["chk_status_found", "chk_has_hos", "chk_hos_warning_true"]),
        Case("hos_zero_drive", "HOS Analysis",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "hos": {"remaining_drive_hours": 0.0, "remaining_duty_hours": 5.0}},
             ["chk_status_found", "chk_has_hos", "chk_hos_warning_true"]),
        Case("hos_zero_duty", "HOS Analysis",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "hos": {"remaining_drive_hours": 5.0, "remaining_duty_hours": 0.0}},
             ["chk_status_found", "chk_has_hos", "chk_hos_warning_true"]),
        Case("hos_exactly_enough", "HOS Analysis",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "hos": {"remaining_drive_hours": 5.0, "remaining_duty_hours": 7.0}},
             ["chk_status_found", "chk_has_hos"]),
        Case("hos_both_zero", "HOS Analysis",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "hos": {"remaining_drive_hours": 0.0, "remaining_duty_hours": 0.0}},
             ["chk_status_found", "chk_has_hos", "chk_hos_warning_true"]),
        Case("hos_not_provided", "HOS Analysis",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM},
             ["chk_status_found", "chk_has_hos", "chk_hos_warning_false"]),
        Case("hos_high_remaining", "HOS Analysis",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "hos": {"remaining_drive_hours": 11.0, "remaining_duty_hours": 14.0}},
             ["chk_status_found", "chk_has_hos", "chk_hos_warning_false"]),
        Case("hos_reset_recommendation", "HOS Analysis",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "hos": {"remaining_drive_hours": 2.0, "remaining_duty_hours": 3.0}},
             ["chk_status_found", "chk_has_hos", "chk_hos_warning_true"]),

        # === VEHICLE CONFIGURATIONS (8) ===
        Case("standard_truck", "Vehicle Config",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM}, ROUTE_OK),
        Case("hazmat_vehicle", "Vehicle Config",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": {**FAHEEM, "hazmat": True}}, ["chk_status_found"]),
        Case("tall_vehicle", "Vehicle Config",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": {**FAHEEM, "height_ft": 14.5}}, ["chk_status_found"]),
        Case("overweight_vehicle", "Vehicle Config",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": {**FAHEEM, "weight_lb": 120000}}, ["chk_status_route_or_rejected"]),
        Case("long_vehicle", "Vehicle Config",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": {**FAHEEM, "length_ft": 80}}, ["chk_status_route_or_rejected"]),
        Case("light_vehicle", "Vehicle Config",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": {**FAHEEM, "weight_lb": 40000}}, ROUTE_OK),
        Case("short_vehicle", "Vehicle Config",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": {**FAHEEM, "height_ft": 10.0}}, ROUTE_OK),
        Case("many_axles", "Vehicle Config",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": {**FAHEEM, "axles": 7}}, ROUTE_OK),

        # === GEOCODING (7) ===
        Case("geocode_known_dc", "Geocoding",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM}, ROUTE_OK),
        Case("geocode_known_store", "Geocoding",
             {"origin": o(live, "S9196", "Tobyhanna, PA"),
              "destination": o(live, "DC6080", "Scranton, PA"),
              "vehicle_profile": FAHEEM}, ["chk_status_found"]),
        Case("geocode_garbage_origin", "Geocoding",
             {"origin": "ZZZZZ_NOWHERE_12345",
              "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM},
             ["chk_status_geocode_fail", "chk_error_present", "chk_error_has_code"]),
        Case("geocode_garbage_dest", "Geocoding",
             {"origin": o(live, "S9196", "Tobyhanna, PA"),
              "destination": "QQQQQ_NONEXISTENT_99999",
              "vehicle_profile": FAHEEM},
             ["chk_status_geocode_fail", "chk_error_present"]),
        Case("geocode_empty_string", "Geocoding",
             {"origin": "", "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM},
             ["chk_status_geocode_fail"]),
        Case("geocode_numeric_code", "Geocoding",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM}, ["chk_status_found"]),
        Case("geocode_city_state", "Geocoding",
             {"origin": o(live, "Tobyhanna, PA", "Tobyhanna, PA"),
              "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM}, ["chk_status_found"]),

        # === PREFERENCES (5) ===
        Case("override_avoid_nyc", "Preferences",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "preferences_override": {"avoid_zones": ["NYC Metro"]}}, ROUTE_OK),
        Case("override_prefer_i80", "Preferences",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "preferences_override": {"prefer_corridors": ["I-80", "I-81"]}}, ROUTE_OK),
        Case("override_both", "Preferences",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "preferences_override": {"avoid_zones": ["DC Beltway"], "prefer_corridors": ["I-78"]}}, ROUTE_OK),
        Case("override_empty", "Preferences",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "preferences_override": {}}, ROUTE_OK),
        Case("no_preferences", "Preferences",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM}, ROUTE_OK),

        # === CONSTRAINT ENFORCEMENT (5) ===
        Case("constraint_standard_truck", "Constraints",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM},
             ["chk_status_found", "chk_has_constraint_report", "chk_zero_violations"]),
        Case("constraint_report_fields", "Constraints",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM},
             ["chk_status_found", "chk_has_constraint_report"]),
        Case("constraint_overweight", "Constraints",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": {**FAHEEM, "weight_lb": 120000}},
             ["chk_status_route_or_rejected"]),
        Case("constraint_hazmat", "Constraints",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": {**FAHEEM, "hazmat": True}},
             ["chk_status_found", "chk_has_constraint_report"]),
        Case("constraint_tall_truck", "Constraints",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": {**FAHEEM, "height_ft": 15.0}},
             ["chk_status_route_or_rejected"]),

        # === OUTPUT COMPLETENESS (5) ===
        Case("output_route_fields", "Output Completeness",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM}, ROUTE_FULL),
        Case("output_constraint_report", "Output Completeness",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM}, ["chk_has_constraint_report"]),
        Case("output_hos_analysis", "Output Completeness",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM,
              "hos": {"remaining_drive_hours": 5.0, "remaining_duty_hours": 8.0}},
             ["chk_has_hos"]),
        Case("output_gpx_file", "Output Completeness",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM}, ["chk_gpx_path"]),
        Case("output_wg_parseable", "Output Completeness",
             {"origin": o(live, "S9196", "Tobyhanna, PA"), "destination": o(live, "DC6080", "Carlisle, PA"),
              "vehicle_profile": FAHEEM}, ["chk_wg_parseable"]),
    ]

    # Add live-only geocoding cases
    if live:
        cases.extend([
            Case("live_geocode_address", "Geocoding (Live)",
                 {"origin": "659 Main Street, Tobyhanna, PA 18466", "destination": "Carlisle, PA",
                  "vehicle_profile": FAHEEM}, ["chk_status_found", "chk_has_route"]),
            Case("live_geocode_zip", "Geocoding (Live)",
                 {"origin": "Tobyhanna, PA", "destination": "17013",
                  "vehicle_profile": FAHEEM}, ["chk_status_found"]),
            Case("live_geocode_city_only", "Geocoding (Live)",
                 {"origin": "Scranton", "destination": "Harrisburg",
                  "vehicle_profile": FAHEEM}, ["chk_status_found"]),
        ])

    return cases


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_case(case: Case) -> Result:
    t0 = time.monotonic()
    try:
        data = generate_truck_safe_route(**case.args)
    except Exception as e:
        return Result(case.name, case.category, False, 0, len(case.checks),
                      f"EXCEPTION: {e}", time.monotonic() - t0)

    passed = 0
    details = []
    for check_name in case.checks:
        fn = CHECK_REGISTRY.get(check_name)
        if not fn:
            details.append(f"{check_name}=UNKNOWN")
            continue
        ok, detail = fn(data)
        if ok:
            passed += 1
        else:
            details.append(f"{check_name}={detail}")

    all_ok = passed == len(case.checks)
    elapsed = time.monotonic() - t0
    detail_str = "; ".join(details) if details else "all checks passed"
    return Result(case.name, case.category, all_ok, passed, len(case.checks), detail_str, elapsed)


def run_all(live: bool) -> list[Result]:
    # Set env before importing engine
    if live:
        os.environ["TRIL_GEOCODER_MODE"] = "nominatim"
        os.environ["TRIL_ROUTER_MODE"] = "graphhopper"
    else:
        os.environ["TRIL_GEOCODER_MODE"] = "stub"
        os.environ["TRIL_ROUTER_MODE"] = "stub"

    mode = "LIVE" if live else "STUB"
    cases = build_cases(live)
    print(f"\nTRIL Production Validation ({mode} mode) — {len(cases)} test cases")
    print("=" * 70)

    results: list[Result] = []
    for case in cases:
        r = run_case(case)
        results.append(r)

    return results


def print_results(results: list[Result]) -> dict:
    categories: dict[str, list[Result]] = {}
    for r in results:
        categories.setdefault(r.category, []).append(r)

    total_pass = 0
    total_fail = 0

    for cat, cat_results in categories.items():
        cat_pass = sum(1 for r in cat_results if r.passed)
        cat_fail = len(cat_results) - cat_pass
        total_pass += cat_pass
        total_fail += cat_fail
        print(f"\n  [{cat}] {cat_pass}/{len(cat_results)} passed")
        for r in cat_results:
            icon = "PASS" if r.passed else "FAIL"
            checks = f"{r.checks_passed}/{r.checks_total}"
            elapsed = f"{r.elapsed:.2f}s" if r.elapsed > 0.01 else "<10ms"
            line = f"    [{icon}] {r.name} ({checks} checks, {elapsed})"
            if not r.passed:
                line += f" -- {r.detail}"
            print(line)

    total = total_pass + total_fail
    print(f"\n{'=' * 70}")
    print(f"TOTAL: {total_pass}/{total} passed, {total_fail} failed")

    return {
        "total": total,
        "passed": total_pass,
        "failed": total_fail,
        "pass_rate": round(total_pass / total, 4) if total else 0,
        "categories": {
            cat: {"passed": sum(1 for r in rs if r.passed), "total": len(rs)}
            for cat, rs in categories.items()
        },
        "failures": [
            {"name": r.name, "category": r.category, "detail": r.detail}
            for r in results if not r.passed
        ],
    }


def main():
    live = "--live" in sys.argv
    json_out = "--json" in sys.argv

    results = run_all(live)
    summary = print_results(results)

    if json_out:
        out_path = Path(__file__).parent / "production_validation_results.json"
        out_path.write_text(json.dumps(summary, indent=2))
        print(f"\nJSON results: {out_path}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
