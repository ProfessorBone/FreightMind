"""
MCP Tool Interface for TRIL
Exposes generate_truck_safe_route tool to Will Graham via OpenClaw
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .engine import TRILEngine
from .models import HOSState, PreferencesOverride, RouteRequest, VehicleProfile


def generate_truck_safe_route(
    origin: str,
    destination: str,
    stops: Optional[List[str]] = None,
    vehicle_profile: Optional[Dict[str, Any]] = None,
    hos: Optional[Dict[str, Any]] = None,
    preferences_override: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate a truck-safe route with constraint validation.
    
    This is the MCP tool interface for Will Graham to call TRIL.
    
    Args:
        origin: Starting location (address, city, or place name)
        destination: Ending location (address, city, or place name)
        stops: Optional intermediate stops
        vehicle_profile: Vehicle dimensions and characteristics
        hos: Hours of Service state
        preferences_override: Optional preference overrides
    
    Returns:
        Route result with status, route details, constraints, and HOS analysis
    """
    
    # Build vehicle profile from input
    if vehicle_profile:
        vehicle = VehicleProfile(
            height_ft=vehicle_profile.get("height_ft", 13.5),
            weight_lb=vehicle_profile.get("weight_lb", 80000),
            length_ft=vehicle_profile.get("length_ft", 70),
            axles=vehicle_profile.get("axles", 5),
            hazmat=vehicle_profile.get("hazmat", False)
        )
    else:
        vehicle = VehicleProfile()  # Use defaults
    
    # Build HOS state if provided
    hos_state = None
    if hos and "remaining_drive_hours" in hos and "remaining_duty_hours" in hos:
        hos_state = HOSState(
            remaining_drive_hours=hos["remaining_drive_hours"],
            remaining_duty_hours=hos["remaining_duty_hours"]
        )
    
    # Build preferences override if provided
    prefs = PreferencesOverride()
    if preferences_override:
        if "avoid_zones" in preferences_override:
            prefs.avoid_zones = preferences_override["avoid_zones"]
        if "prefer_corridors" in preferences_override:
            prefs.prefer_corridors = preferences_override["prefer_corridors"]
    
    # Build the route request
    request = RouteRequest(
        origin=origin,
        destination=destination,
        stops=stops or [],
        vehicle_profile=vehicle,
        hos=hos_state,
        preferences_override=prefs
    )
    
    # Run the TRIL engine
    try:
        engine = TRILEngine()
        result = engine.run(request)
        output = result.to_dict()
        
        # Transform output to match MCP spec exactly
        mcp_output = {
            "status": output["status"]
        }
        
        # Add route details if found
        if output.get("route"):
            route = output["route"]
            mcp_output["route"] = {
                "distance_miles": route.get("distance_miles"),
                "estimated_drive_time_hours": route.get("estimated_drive_time_hours"),
                "gpx_file": route.get("gpx_file"),
                "confidence_score": route.get("confidence_score"),
                "safety_score": route.get("safety_score"),
                "preference_score": route.get("preference_score"),
                "data_tiers": route.get("data_tiers", {})
            }
        
        # Add constraint report if present
        if output.get("constraint_report"):
            report = output["constraint_report"]
            mcp_output["constraint_report"] = {
                "violations_found": report.get("violations_found", 0),
                "warnings": report.get("warnings", []),
                "turn_feasibility_validated": report.get("turn_feasibility_validated", False),
                "turn_feasibility_note": report.get("turn_feasibility_note", "")
            }
        
        # Add HOS analysis if present
        if output.get("hos_analysis"):
            hos_data = output["hos_analysis"]
            mcp_output["hos_analysis"] = hos_data
        
        # Add alternatives if present
        if output.get("alternatives"):
            alternatives = []
            for idx, alt in enumerate(output["alternatives"], start=2):
                alternatives.append({
                    "rank": idx,
                    "distance_miles": alt.get("distance_miles"),
                    "estimated_drive_time_hours": alt.get("estimated_drive_time_hours"),
                    "confidence_score": alt.get("confidence_score"),
                    "safety_score": alt.get("safety_score"),
                    "preference_score": alt.get("preference_score"),
                    "summary": alt.get("summary", f"Alternative route {idx}")
                })
            mcp_output["alternatives"] = alternatives
        
        # Add error details if present
        if output.get("error"):
            mcp_output["error"] = output["error"]
        
        return mcp_output
        
    except Exception as e:
        # Return error response on any exception
        return {
            "status": "ENGINE_ERROR",
            "error": {
                "code": "ENGINE_ERROR",
                "message": str(e),
                "failed_input": f"{origin} -> {destination}"
            }
        }


# MCP Tool Registration Metadata
MCP_TOOL_DEFINITION = {
    "name": "generate_truck_safe_route",
    "description": "Generate a legally compliant truck route with constraint validation and HOS analysis",
    "input_schema": {
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Starting location (address, city, or place name)"
            },
            "destination": {
                "type": "string",
                "description": "Ending location (address, city, or place name)"
            },
            "stops": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional intermediate stops"
            },
            "vehicle_profile": {
                "type": "object",
                "properties": {
                    "height_ft": {"type": "number", "default": 13.5},
                    "weight_lb": {"type": "number", "default": 80000},
                    "length_ft": {"type": "number", "default": 70},
                    "axles": {"type": "integer", "default": 5},
                    "hazmat": {"type": "boolean", "default": False}
                }
            },
            "hos": {
                "type": "object",
                "properties": {
                    "remaining_drive_hours": {"type": "number"},
                    "remaining_duty_hours": {"type": "number"}
                }
            },
            "preferences_override": {
                "type": "object",
                "properties": {
                    "avoid_zones": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "prefer_corridors": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        },
        "required": ["origin", "destination"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["ROUTE_FOUND", "NO_SAFE_ROUTE", "GEOCODING_FAILED", "ENGINE_ERROR"]
            },
            "route": {"type": "object"},
            "constraint_report": {"type": "object"},
            "hos_analysis": {"type": "object"},
            "alternatives": {"type": "array"},
            "error": {"type": "object"}
        }
    }
}