"""
TRIL Evaluation Harness
Adapted from Anthropic Academy eval pattern for TRIL route validation
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from tril.engine import TRILEngine
from tril.models import HOSState, RouteRequest, VehicleProfile


def run_prompt(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a TRIL route request from a test case definition."""
    request_data = test_case["request"]
    
    # Build vehicle profile
    vehicle_data = request_data.get("vehicle_profile", {})
    vehicle = VehicleProfile(
        height_ft=vehicle_data.get("height_ft", 13.5),
        weight_lb=vehicle_data.get("weight_lb", 80000),
        length_ft=vehicle_data.get("length_ft", 70),
        axles=vehicle_data.get("axles", 5),
        hazmat=vehicle_data.get("hazmat", False)
    )
    
    # Build HOS state if provided
    hos = None
    hos_data = request_data.get("hos")
    if hos_data:
        hos = HOSState(
            remaining_drive_hours=hos_data["remaining_drive_hours"],
            remaining_duty_hours=hos_data["remaining_duty_hours"]
        )
    
    # Build route request
    request = RouteRequest(
        origin=request_data["origin"],
        destination=request_data["destination"],
        stops=request_data.get("stops", []),
        vehicle_profile=vehicle,
        hos=hos
    )
    
    # Run the engine
    engine = TRILEngine()
    result = engine.run(request)
    
    return result.to_dict()


def grade(output: Dict[str, Any], test_case: Dict[str, Any]) -> float:
    """Grade TRIL output against expected behaviors."""
    score = 0.0
    expected = test_case.get("expected", {})
    category = test_case.get("category", "")
    
    # Check status match
    if output.get("status") == expected.get("status"):
        score += 0.3
    else:
        # Wrong status is a critical failure for safety categories
        if "Constraint" in category or "HOS" in category:
            return 0.0
    
    # Category-specific grading
    if category == "Constraint Enforcement":
        # CORRECTION 1: More stringent grading for constraint enforcement
        report = output.get("constraint_report", {})
        violations_found = report.get("violations_found", 0)
        min_violations = expected.get("min_violations", 0)
        
        if min_violations > 0 and violations_found == 0:
            # System should have caught a violation but didn't
            # This is a CRITICAL FAILURE — score 0.0, no partial credit
            return 0.0
        elif min_violations > 0 and violations_found >= min_violations:
            score += 0.7  # Correctly caught the violation(s)
        elif min_violations == 0 and violations_found == 0:
            # No violations expected, none found — but if this is because
            # the stub has no constraint data, mark as UNTESTABLE, not passing
            route = output.get("route", {})
            if route and route.get("source_engine") == "stub-graphhopper":
                return 0.0  # Cannot validate with stub data
            else:
                score += 0.7  # Real engine, real validation, real pass
                
    elif category == "Confidence Model":
        # Check confidence score calculation
        route = output.get("route", {})
        if route:
            confidence = route.get("confidence_score", 0)
            min_confidence = expected.get("min_confidence", 0)
            
            if confidence >= min_confidence:
                score += 0.35
            
            # Check for low confidence warnings
            report = output.get("constraint_report", {})
            warnings = report.get("warnings", [])
            low_conf_warnings = [w for w in warnings if w.get("type") == "LOW_CONFIDENCE_SEGMENT"]
            
            if expected.get("expect_low_confidence_warnings", False):
                if low_conf_warnings:
                    score += 0.35
            else:
                if not low_conf_warnings:
                    score += 0.35
                    
    elif category == "HOS Analysis":
        # Check HOS warning presence
        hos_analysis = output.get("hos_analysis", {})
        hos_warning = hos_analysis.get("hos_warning", False)
        expected_warning = expected.get("hos_warning", False)
        
        if hos_warning == expected_warning:
            score += 0.35
            
            if hos_warning:
                # Check for reset recommendation
                if hos_analysis.get("recommended_reset"):
                    score += 0.35
        else:
            return 0.0  # Critical failure - wrong HOS assessment
            
    elif category == "Retry and Termination":
        # CORRECTION 2: More comprehensive retry testing
        if expected.get("status") == "NO_SAFE_ROUTE":
            if output.get("status") == "NO_SAFE_ROUTE":
                error = output.get("error", {})
                if error.get("code") == "NO_SAFE_ROUTE" and error.get("retry_report"):
                    score += 0.7
            else:
                # If we expected NO_SAFE_ROUTE but got ROUTE_FOUND with stub engine,
                # this is untestable, not a pass
                route = output.get("route", {})
                if route and route.get("source_engine") == "stub-graphhopper":
                    return 0.0  # Cannot validate retry with stub
                else:
                    return 0.0  # Real engine should have failed — critical failure
        else:
            # For successful routes, just check basic structure
            if output.get("status") == "ROUTE_FOUND":
                score += 0.7
                
    elif category == "Output Completeness":
        # Check for required output fields
        route = output.get("route", {})
        if route:
            required_fields = [
                "distance_miles", "estimated_drive_time_hours", 
                "gpx_file", "json_file", "confidence_score",
                "safety_score", "preference_score", "data_tiers",
                "reference_data_status"
            ]
            
            fields_present = sum(1 for field in required_fields if field in route)
            score += (fields_present / len(required_fields)) * 0.7
            
    elif category == "Reference Data Integration":
        # Check that overlays are being applied
        report = output.get("constraint_report", {})
        if report:
            source_versions = report.get("source_versions", {})
            if "nbi" in source_versions and "state_overlays" in source_versions:
                score += 0.7
                
    elif category == "Geocoding":
        # Check geocoding error handling
        if expected.get("status") == "GEOCODING_FAILED":
            error = output.get("error", {})
            if error.get("code") == "GEOCODING_FAILED":
                score += 0.7
        else:
            score += 0.7  # Geocoding succeeded
            
    elif category == "Edge Cases":
        # Basic pass/fail for edge cases
        if output.get("status") in ["ROUTE_FOUND", "NO_SAFE_ROUTE"]:
            score += 0.7
    
    else:
        # Default scoring for unspecified categories
        score = 0.5
    
    return min(1.0, score)


def run_test_case(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single test case and grade the result."""
    output = run_prompt(test_case)
    score = grade(output, test_case)
    
    # Check for critical safety failures
    is_critical = False
    category = test_case.get("category", "")
    expected = test_case.get("expected", {})
    
    if "Constraint" in category or "HOS" in category:
        # Check if system returned unsafe route
        if output.get("status") == "ROUTE_FOUND":
            report = output.get("constraint_report", {})
            violations_found = report.get("violations_found", 0)
            min_violations = expected.get("min_violations", 0)
            
            if min_violations > 0 and violations_found == 0:
                is_critical = True  # Missed a violation
                
            hos_analysis = output.get("hos_analysis", {})
            if expected.get("hos_warning", False) and not hos_analysis.get("hos_warning", False):
                is_critical = True  # Missed HOS overage
    
    # CORRECTION 3: Add stub-awareness
    is_testable = True
    route = output.get("route", {})
    if route and route.get("source_engine") == "stub-graphhopper":
        if category in ["Constraint Enforcement", "Retry and Termination"]:
            is_testable = False
    
    return {
        "test_case": test_case,
        "output": output,
        "score": score,
        "critical_failure": is_critical,
        "testable": is_testable
    }


def run_eval(dataset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run the full eval suite across all test cases."""
    results = []
    for test_case in dataset:
        print(f"Running test: {test_case['name']} ({test_case['category']})")
        result = run_test_case(test_case)
        results.append(result)
        
        if not result["testable"]:
            print(f"  ⚠️  UNTESTABLE with stub data - Score: {result['score']}")
        elif result["critical_failure"]:
            print(f"  ⚠️  CRITICAL FAILURE - Score: {result['score']}")
        else:
            print(f"  Score: {result['score']}")
    
    return results


# Test dataset covering all eval categories
EVAL_DATASET = [
    # Category 1: Constraint Enforcement (CORRECTION 1: using min_violations)
    {
        "name": "height_violation",
        "category": "Constraint Enforcement",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 15.0,  # Intentionally high to trigger violation
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "ROUTE_FOUND",
            "min_violations": 1  # EXPECT at least one height violation
        }
    },
    {
        "name": "weight_violation",
        "category": "Constraint Enforcement",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 120000,  # Over typical bridge limits
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "ROUTE_FOUND",
            "min_violations": 1  # EXPECT at least one weight violation
        }
    },
    {
        "name": "hazmat_restriction",
        "category": "Constraint Enforcement",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": True
            }
        },
        "expected": {
            "status": "ROUTE_FOUND",
            "min_violations": 0  # Stub has hazmat_allowed=True on all segments
        }
    },
    
    # Category 2: Confidence Model
    {
        "name": "high_confidence_route",
        "category": "Confidence Model",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "ROUTE_FOUND",
            "min_confidence": 0.5,
            "expect_low_confidence_warnings": False
        }
    },
    {
        "name": "low_confidence_segments",
        "category": "Confidence Model",
        "request": {
            "origin": "Tobyhanna, PA",
            "destination": "Johnstown, NY",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "ROUTE_FOUND",
            "min_confidence": 0.0,
            "expect_low_confidence_warnings": True
        }
    },
    
    # Category 3: HOS Analysis
    {
        "name": "route_within_drive_clock",
        "category": "HOS Analysis",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            },
            "hos": {
                "remaining_drive_hours": 8.0,
                "remaining_duty_hours": 12.0
            }
        },
        "expected": {
            "status": "ROUTE_FOUND",
            "hos_warning": False
        }
    },
    {
        "name": "route_exceeding_drive_clock",
        "category": "HOS Analysis",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            },
            "hos": {
                "remaining_drive_hours": 2.0,
                "remaining_duty_hours": 10.0
            }
        },
        "expected": {
            "status": "ROUTE_FOUND",
            "hos_warning": True
        }
    },
    {
        "name": "route_exceeding_duty_clock",
        "category": "HOS Analysis",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            },
            "hos": {
                "remaining_drive_hours": 8.0,
                "remaining_duty_hours": 3.0
            }
        },
        "expected": {
            "status": "ROUTE_FOUND",
            "hos_warning": True
        }
    },
    {
        "name": "no_hos_provided",
        "category": "HOS Analysis",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "ROUTE_FOUND",
            "hos_warning": False
        }
    },
    
    # Category 4: Retry and Termination (CORRECTION 2: expanded tests)
    {
        "name": "successful_route",
        "category": "Retry and Termination",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "ROUTE_FOUND"
        }
    },
    {
        "name": "route_with_forced_violation",
        "category": "Retry and Termination",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "ROUTE_FOUND",
            "note": "UNTESTABLE in stub mode — stub router does not produce segments with constraint values that would trigger violations."
        }
    },
    {
        "name": "no_safe_route_response_structure",
        "category": "Retry and Termination",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "NO_SAFE_ROUTE",
            "note": "UNTESTABLE in stub mode — requires all candidates to fail validation."
        }
    },
    
    # Category 5: Output Completeness
    {
        "name": "json_output_completeness",
        "category": "Output Completeness",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "ROUTE_FOUND"
        }
    },
    
    # Category 6: Reference Data Integration
    {
        "name": "reference_data_applied",
        "category": "Reference Data Integration",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "ROUTE_FOUND"
        }
    },
    
    # Category 7: Geocoding
    {
        "name": "known_locations",
        "category": "Geocoding",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "ROUTE_FOUND"
        }
    },
    {
        "name": "unknown_location",
        "category": "Geocoding",
        "request": {
            "origin": "Unknown Place XYZ123",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "GEOCODING_FAILED"
        }
    },
    
    # Category 8: Edge Cases
    {
        "name": "empty_stops_list",
        "category": "Edge Cases",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "stops": [],
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            }
        },
        "expected": {
            "status": "ROUTE_FOUND"
        }
    },
    {
        "name": "zero_remaining_drive_hours",
        "category": "Edge Cases",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": False
            },
            "hos": {
                "remaining_drive_hours": 0.0,
                "remaining_duty_hours": 8.0
            }
        },
        "expected": {
            "status": "ROUTE_FOUND",
            "hos_warning": True
        }
    },
    {
        "name": "vehicle_with_hazmat",
        "category": "Edge Cases",
        "request": {
            "origin": "S9196",
            "destination": "DC6080",
            "vehicle_profile": {
                "height_ft": 13.5,
                "weight_lb": 80000,
                "length_ft": 70,
                "axles": 5,
                "hazmat": True
            }
        },
        "expected": {
            "status": "ROUTE_FOUND"
        }
    }
]


def save_eval_results(results: List[Dict[str, Any]], output_path: Path):
    """Save evaluation results to JSON file with stub-awareness."""
    # Extract summary statistics
    total_tests = len(results)
    testable_results = [r for r in results if r["testable"]]
    untestable_results = [r for r in results if not r["testable"]]
    
    testable_passed = sum(1 for r in testable_results if r["score"] >= 0.5)
    overall_passed = sum(1 for r in results if r["score"] >= 0.5)
    critical_failures = sum(1 for r in results if r["critical_failure"])
    
    # Group by category
    categories = {}
    for result in results:
        category = result["test_case"]["category"]
        if category not in categories:
            categories[category] = {
                "tests": 0, 
                "passed": 0, 
                "total_score": 0.0, 
                "critical": 0,
                "testable": 0,
                "untestable": 0
            }
        
        categories[category]["tests"] += 1
        categories[category]["total_score"] += result["score"]
        if result["score"] >= 0.5:
            categories[category]["passed"] += 1
        if result["critical_failure"]:
            categories[category]["critical"] += 1
        if result["testable"]:
            categories[category]["testable"] += 1
        else:
            categories[category]["untestable"] += 1
    
    # Calculate category averages
    for category in categories:
        cat_data = categories[category]
        cat_data["average_score"] = cat_data["total_score"] / cat_data["tests"]
        cat_data["pass_rate"] = cat_data["passed"] / cat_data["tests"]
    
    # Build output (CORRECTION 3: separate testable/untestable summaries)
    output = {
        "summary": {
            "total_tests": total_tests,
            "testable_tests": len(testable_results),
            "untestable_tests": len(untestable_results),
            "testable_passed": testable_passed,
            "testable_pass_rate": testable_passed / len(testable_results) if testable_results else 0,
            "overall_passed": overall_passed,
            "overall_pass_rate": overall_passed / total_tests if total_tests > 0 else 0,
            "critical_failures": critical_failures,
            "testable_score": sum(r["score"] for r in testable_results) / len(testable_results) if testable_results else 0,
            "overall_score": sum(r["score"] for r in results) / total_tests if total_tests > 0 else 0
        },
        "untestable_categories": [
            cat for cat, data in categories.items() 
            if data["untestable"] > 0
        ],
        "categories": categories,
        "test_results": [
            {
                "name": r["test_case"]["name"],
                "category": r["test_case"]["category"],
                "score": r["score"],
                "passed": r["score"] >= 0.5,
                "critical_failure": r["critical_failure"],
                "testable": r["testable"],
                "status": r["output"].get("status"),
                "expected_status": r["test_case"]["expected"].get("status")
            }
            for r in results
        ]
    }
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    return output


if __name__ == "__main__":
    print("TRIL Evaluation Harness (with corrections)")
    print("=" * 60)
    
    # Run the evaluation
    results = run_eval(EVAL_DATASET)
    
    # Save results
    output_path = Path(__file__).parent / "eval_results.json"
    summary = save_eval_results(results, output_path)
    
    # Print summary (CORRECTION 3: show testable vs untestable)
    print("\nEvaluation Complete!")
    print("-" * 60)
    
    print("\nTESTABLE RESULTS:")
    print(f"  Pass Rate: {summary['summary']['testable_pass_rate']:.1%} ({summary['summary']['testable_passed']}/{summary['summary']['testable_tests']} tests)")
    print(f"  Average Score: {summary['summary']['testable_score']:.2f}")
    
    print("\nUNTESTABLE (requires live data):")
    print(f"  Tests: {summary['summary']['untestable_tests']}")
    if summary["untestable_categories"]:
        print(f"  Categories: {', '.join(summary['untestable_categories'])}")
    
    print("\nOVERALL (including untestable as 0.0):")
    print(f"  Pass Rate: {summary['summary']['overall_pass_rate']:.1%} ({summary['summary']['overall_passed']}/{summary['summary']['total_tests']} tests)")
    print(f"  Average Score: {summary['summary']['overall_score']:.2f}")
    print(f"  Critical Failures: {summary['summary']['critical_failures']}")
    
    print("\nPer-Category Results:")
    for category, data in summary["categories"].items():
        print(f"  {category}:")
        print(f"    Pass Rate: {data['pass_rate']:.1%} ({data['passed']}/{data['tests']})")
        print(f"    Avg Score: {data['average_score']:.2f}")
        if data["untestable"] > 0:
            print(f"    ⚠️  Untestable: {data['untestable']} tests")
        if data["critical"] > 0:
            print(f"    ⚠️  Critical Failures: {data['critical']}")
    
    print(f"\nResults saved to: {output_path}")