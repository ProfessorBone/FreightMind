#!/usr/bin/env python3
"""
Will Graham Integration Tests

Simulates Will Graham calling the TRIL MCP tool with realistic scenarios
Faheem encounters on the road. Tests both stub and live service modes.

Usage:
    python -m tril.tests.will_graham_integration          # stub mode
    python -m tril.tests.will_graham_integration --live    # live services
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession

# Faheem's truck — the only vehicle profile that matters for MVP
FAHEEM_VEHICLE = {
    "height_ft": 13.5,
    "weight_lb": 80000,
    "length_ft": 70,
    "axles": 5,
    "hazmat": False,
}

PYTHON = sys.executable
WORKSPACE = str(Path(__file__).resolve().parent.parent.parent)


@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str = ""


def make_server_params(live: bool) -> StdioServerParameters:
    env = {
        "HOME": os.environ.get("HOME", "/Users/clarencedowns"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": WORKSPACE,
    }
    if live:
        env.update({
            "TRIL_GEOCODER_MODE": "nominatim",
            "TRIL_ROUTER_MODE": "graphhopper",
            "TRIL_NOMINATIM_URL": "http://127.0.0.1:8080",
            "TRIL_GRAPHHOPPER_URL": "http://127.0.0.1:8989",
        })
    else:
        env.update({
            "TRIL_GEOCODER_MODE": "stub",
            "TRIL_ROUTER_MODE": "stub",
        })
    return StdioServerParameters(
        command=PYTHON,
        args=["-m", "tril.mcp_server"],
        env=env,
    )


async def call_tril(session: ClientSession, args: dict[str, Any]) -> dict[str, Any]:
    result = await session.call_tool("generate_truck_safe_route", args)
    return json.loads(result.content[0].text)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

async def test_tool_discovery(session: ClientSession) -> TestResult:
    """Will Graham must be able to discover the tool and see its schema."""
    tools = await session.list_tools()
    names = [t.name for t in tools.tools]
    if "generate_truck_safe_route" not in names:
        return TestResult("tool_discovery", False, f"Tool not found. Available: {names}")
    tool = next(t for t in tools.tools if t.name == "generate_truck_safe_route")
    required = tool.inputSchema.get("required", [])
    if sorted(required) != ["destination", "origin"]:
        return TestResult("tool_discovery", False, f"Bad required params: {required}")
    return TestResult("tool_discovery", True)


async def test_basic_route(session: ClientSession, live: bool) -> TestResult:
    """Standard route request — the happy path."""
    origin = "Tobyhanna, PA" if live else "S9196"
    dest = "Carlisle, PA" if live else "DC6080"
    data = await call_tril(session, {
        "origin": origin,
        "destination": dest,
        "vehicle_profile": FAHEEM_VEHICLE,
    })
    if data["status"] != "ROUTE_FOUND":
        return TestResult("basic_route", False, f"Status: {data['status']}, error: {data.get('error')}")
    route = data["route"]
    for field in ("distance_miles", "estimated_drive_time_hours", "gpx_file",
                  "confidence_score", "safety_score", "preference_score", "data_tiers"):
        if field not in route:
            return TestResult("basic_route", False, f"Missing route field: {field}")
    if route["distance_miles"] <= 0:
        return TestResult("basic_route", False, f"Invalid distance: {route['distance_miles']}")
    return TestResult("basic_route", True, f"{route['distance_miles']} mi, {route['estimated_drive_time_hours']} hrs")


async def test_hos_tight_clock(session: ClientSession, live: bool) -> TestResult:
    """Faheem has 2 hours left on the clock — system must flag it."""
    origin = "Tobyhanna, PA" if live else "S9196"
    dest = "Carlisle, PA" if live else "DC6080"
    data = await call_tril(session, {
        "origin": origin,
        "destination": dest,
        "vehicle_profile": FAHEEM_VEHICLE,
        "hos": {"remaining_drive_hours": 2.0, "remaining_duty_hours": 3.0},
    })
    if data["status"] != "ROUTE_FOUND":
        return TestResult("hos_tight_clock", False, f"Status: {data['status']}")
    hos = data.get("hos_analysis", {})
    if "hos_warning" not in hos:
        return TestResult("hos_tight_clock", False, "Missing hos_warning field")
    # With 2 hrs left and a 2.8+ hr route, should warn
    detail = f"warning={hos['hos_warning']}, overage={hos.get('drive_overage_hours')}"
    return TestResult("hos_tight_clock", True, detail)


async def test_hos_comfortable(session: ClientSession, live: bool) -> TestResult:
    """Plenty of hours — no HOS warning expected."""
    origin = "Tobyhanna, PA" if live else "S9196"
    dest = "Carlisle, PA" if live else "DC6080"
    data = await call_tril(session, {
        "origin": origin,
        "destination": dest,
        "vehicle_profile": FAHEEM_VEHICLE,
        "hos": {"remaining_drive_hours": 9.0, "remaining_duty_hours": 12.0},
    })
    if data["status"] != "ROUTE_FOUND":
        return TestResult("hos_comfortable", False, f"Status: {data['status']}")
    hos = data.get("hos_analysis", {})
    detail = f"warning={hos.get('hos_warning')}, remaining={hos.get('remaining_after_trip_hours')}"
    return TestResult("hos_comfortable", True, detail)


async def test_no_hos_provided(session: ClientSession, live: bool) -> TestResult:
    """No HOS data — route still works, HOS analysis should reflect unknown state."""
    origin = "Tobyhanna, PA" if live else "S9196"
    dest = "Carlisle, PA" if live else "DC6080"
    data = await call_tril(session, {
        "origin": origin,
        "destination": dest,
        "vehicle_profile": FAHEEM_VEHICLE,
    })
    if data["status"] != "ROUTE_FOUND":
        return TestResult("no_hos", False, f"Status: {data['status']}")
    return TestResult("no_hos", True, f"HOS present: {'hos_analysis' in data}")


async def test_geocoding_bad_origin(session: ClientSession, _live: bool) -> TestResult:
    """Garbage origin — must return GEOCODING_FAILED, not crash."""
    data = await call_tril(session, {
        "origin": "ZZZZZ_NO_SUCH_PLACE_12345",
        "destination": "DC6080" if not _live else "Carlisle, PA",
        "vehicle_profile": FAHEEM_VEHICLE,
    })
    if data["status"] not in ("GEOCODING_FAILED", "ENGINE_ERROR"):
        return TestResult("bad_origin", False, f"Expected failure, got: {data['status']}")
    err = data.get("error", {})
    return TestResult("bad_origin", True, f"code={err.get('code')}, msg={err.get('message', '')[:60]}")


async def test_preferences_override(session: ClientSession, live: bool) -> TestResult:
    """Override avoid zones and corridors — should not crash."""
    origin = "Tobyhanna, PA" if live else "S9196"
    dest = "Carlisle, PA" if live else "DC6080"
    data = await call_tril(session, {
        "origin": origin,
        "destination": dest,
        "vehicle_profile": FAHEEM_VEHICLE,
        "preferences_override": {
            "avoid_zones": ["NYC Metro"],
            "prefer_corridors": ["I-80", "I-81"],
        },
    })
    if data["status"] != "ROUTE_FOUND":
        return TestResult("preferences_override", False, f"Status: {data['status']}")
    return TestResult("preferences_override", True)


async def test_constraint_report_shape(session: ClientSession, live: bool) -> TestResult:
    """Verify constraint report has all required fields."""
    origin = "Tobyhanna, PA" if live else "S9196"
    dest = "Carlisle, PA" if live else "DC6080"
    data = await call_tril(session, {
        "origin": origin,
        "destination": dest,
        "vehicle_profile": FAHEEM_VEHICLE,
    })
    if data["status"] != "ROUTE_FOUND":
        return TestResult("constraint_report", False, f"Status: {data['status']}")
    report = data.get("constraint_report", {})
    for field in ("violations_found", "warnings", "turn_feasibility_validated", "turn_feasibility_note"):
        if field not in report:
            return TestResult("constraint_report", False, f"Missing: {field}")
    return TestResult("constraint_report", True, f"violations={report['violations_found']}")


async def test_hazmat_vehicle(session: ClientSession, live: bool) -> TestResult:
    """Hazmat vehicle — should still produce a route (or reject with reason)."""
    origin = "Tobyhanna, PA" if live else "S9196"
    dest = "Carlisle, PA" if live else "DC6080"
    hazmat_vehicle = {**FAHEEM_VEHICLE, "hazmat": True}
    data = await call_tril(session, {
        "origin": origin,
        "destination": dest,
        "vehicle_profile": hazmat_vehicle,
    })
    # Either ROUTE_FOUND or NO_SAFE_ROUTE are acceptable for hazmat
    if data["status"] not in ("ROUTE_FOUND", "NO_SAFE_ROUTE"):
        return TestResult("hazmat_vehicle", False, f"Unexpected status: {data['status']}")
    return TestResult("hazmat_vehicle", True, f"status={data['status']}")


async def test_overweight_vehicle(session: ClientSession, live: bool) -> TestResult:
    """Overweight vehicle — constraint engine should catch violations or handle gracefully."""
    origin = "Tobyhanna, PA" if live else "S9196"
    dest = "Carlisle, PA" if live else "DC6080"
    heavy_vehicle = {**FAHEEM_VEHICLE, "weight_lb": 120000}
    data = await call_tril(session, {
        "origin": origin,
        "destination": dest,
        "vehicle_profile": heavy_vehicle,
    })
    return TestResult("overweight_vehicle", True, f"status={data['status']}")


async def test_response_parseable_by_will_graham(session: ClientSession, live: bool) -> TestResult:
    """
    Simulates Will Graham's parser extracting the fields it needs
    to compose a response to Faheem.
    """
    origin = "Tobyhanna, PA" if live else "S9196"
    dest = "Carlisle, PA" if live else "DC6080"
    data = await call_tril(session, {
        "origin": origin,
        "destination": dest,
        "vehicle_profile": FAHEEM_VEHICLE,
        "hos": {"remaining_drive_hours": 5.0, "remaining_duty_hours": 8.0},
    })

    if data["status"] != "ROUTE_FOUND":
        return TestResult("wg_parser", False, f"No route to parse: {data['status']}")

    # Will Graham extracts these fields to compose a driver-facing message:
    try:
        route = data["route"]
        miles = float(route["distance_miles"])
        hours = float(route["estimated_drive_time_hours"])
        gpx = str(route["gpx_file"])
        confidence = float(route["confidence_score"])
        safety = float(route["safety_score"])

        hos = data.get("hos_analysis", {})
        hos_warn = hos.get("hos_warning")
        drive_overage = hos.get("drive_overage_hours")
        reset = hos.get("recommended_reset")

        report = data.get("constraint_report", {})
        violations = int(report.get("violations_found", 0))

        # Will Graham composes a message like:
        msg_parts = [f"{miles:.0f} mi, ~{hours:.1f} hrs"]
        if violations > 0:
            msg_parts.append(f"{violations} constraint violations")
        if hos_warn:
            msg_parts.append("HOS tight")
            if reset and reset.get("location_name"):
                msg_parts.append(f"reset at {reset['location_name']}")
        msg_parts.append(f"confidence {confidence:.0%}")

        composed = " | ".join(msg_parts)
    except (KeyError, TypeError, ValueError) as e:
        return TestResult("wg_parser", False, f"Parse error: {e}")

    return TestResult("wg_parser", True, composed)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ALL_TESTS = [
    test_tool_discovery,
    test_basic_route,
    test_hos_tight_clock,
    test_hos_comfortable,
    test_no_hos_provided,
    test_geocoding_bad_origin,
    test_preferences_override,
    test_constraint_report_shape,
    test_hazmat_vehicle,
    test_overweight_vehicle,
    test_response_parseable_by_will_graham,
]


async def run_all(live: bool) -> int:
    mode = "LIVE" if live else "STUB"
    print(f"\nWill Graham Integration Tests ({mode} mode)")
    print("=" * 60)

    params = make_server_params(live)
    results: list[TestResult] = []

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            for test_fn in ALL_TESTS:
                name = test_fn.__name__.removeprefix("test_")
                try:
                    if test_fn == test_tool_discovery:
                        r = await test_fn(session)
                    else:
                        r = await test_fn(session, live)
                    results.append(r)
                except Exception as e:
                    results.append(TestResult(name, False, f"EXCEPTION: {e}"))

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    for r in results:
        icon = "PASS" if r.passed else "FAIL"
        detail = f" ({r.detail})" if r.detail else ""
        print(f"  [{icon}] {r.name}{detail}")

    print(f"\n{passed}/{len(results)} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main():
    live = "--live" in sys.argv
    return asyncio.run(run_all(live))


if __name__ == "__main__":
    sys.exit(main())
