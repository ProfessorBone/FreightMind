#!/usr/bin/env python3
"""Test the MCP tool interface."""

import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tril.mcp_tool import generate_truck_safe_route


def test_basic_route():
    """Test basic route generation through MCP interface."""
    print("Test 1: Basic Route")
    print("-" * 40)
    
    result = generate_truck_safe_route(
        origin="S9196",
        destination="DC6080",
        vehicle_profile={
            "height_ft": 13.5,
            "weight_lb": 80000,
            "length_ft": 70,
            "axles": 5,
            "hazmat": False
        }
    )
    
    print(f"Status: {result['status']}")
    if result.get('route'):
        route = result['route']
        print(f"Distance: {route.get('distance_miles')} miles")
        print(f"Time: {route.get('estimated_drive_time_hours')} hours")
        print(f"Confidence: {route.get('confidence_score')}")
    print()
    return result['status'] == 'ROUTE_FOUND'


def test_with_hos():
    """Test route with HOS constraints."""
    print("Test 2: Route with HOS")
    print("-" * 40)
    
    result = generate_truck_safe_route(
        origin="S9196",
        destination="DC6080",
        hos={
            "remaining_drive_hours": 2.0,
            "remaining_duty_hours": 10.0
        }
    )
    
    print(f"Status: {result['status']}")
    if result.get('hos_analysis'):
        hos = result['hos_analysis']
        print(f"HOS Warning: {hos.get('hos_warning')}")
        if hos.get('recommended_reset'):
            reset = hos['recommended_reset']
            print(f"Reset Location: {reset.get('location_name')}")
    print()
    return result['status'] == 'ROUTE_FOUND'


def test_geocoding_failure():
    """Test geocoding failure handling."""
    print("Test 3: Geocoding Failure")
    print("-" * 40)
    
    result = generate_truck_safe_route(
        origin="Unknown Place XYZ123",
        destination="DC6080"
    )
    
    print(f"Status: {result['status']}")
    if result.get('error'):
        error = result['error']
        print(f"Error Code: {error.get('code')}")
        print(f"Message: {error.get('message')}")
        print(f"Failed Input: {error.get('failed_input')}")
    print()
    return result['status'] == 'GEOCODING_FAILED'


def test_with_stops():
    """Test route with intermediate stops."""
    print("Test 4: Route with Stops")
    print("-" * 40)
    
    result = generate_truck_safe_route(
        origin="S9196",
        destination="DC6080",
        stops=["Tobyhanna, PA"],
        vehicle_profile={
            "height_ft": 13.5,
            "weight_lb": 80000,
            "length_ft": 70,
            "axles": 5,
            "hazmat": True
        }
    )
    
    print(f"Status: {result['status']}")
    if result.get('route'):
        print(f"Route found with stops")
    print()
    return result['status'] == 'ROUTE_FOUND'


def test_output_schema():
    """Verify output matches MCP spec."""
    print("Test 5: Output Schema Compliance")
    print("-" * 40)
    
    result = generate_truck_safe_route(
        origin="S9196",
        destination="DC6080"
    )
    
    # Check required fields
    assert 'status' in result
    
    if result['status'] == 'ROUTE_FOUND':
        if 'route' in result:
            route = result['route']
            required_route_fields = [
                'distance_miles', 'estimated_drive_time_hours',
                'gpx_file', 'confidence_score', 'safety_score',
                'preference_score', 'data_tiers'
            ]
            for field in required_route_fields:
                assert field in route, f"Missing route field: {field}"
        
        if 'constraint_report' in result:
            report = result['constraint_report']
            assert 'violations_found' in report
            assert 'warnings' in report
            assert 'turn_feasibility_validated' in report
            assert 'turn_feasibility_note' in report
    
    print("Schema validation: PASS")
    print()
    return True


def main():
    """Run all tests."""
    print("\nMCP Tool Interface Tests")
    print("=" * 60)
    
    tests = [
        ("Basic Route", test_basic_route),
        ("Route with HOS", test_with_hos),
        ("Geocoding Failure", test_geocoding_failure),
        ("Route with Stops", test_with_stops),
        ("Output Schema", test_output_schema)
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {name}: PASS\n")
            else:
                failed += 1
                print(f"❌ {name}: FAIL\n")
        except Exception as e:
            failed += 1
            print(f"❌ {name}: ERROR - {e}\n")
    
    print("-" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())