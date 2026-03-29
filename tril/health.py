"""
TRIL Health Check Module
Checks service connectivity and reference data freshness.
Returns aggregated health status for monitoring and MCP discovery.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict

from .config import TRILConfig
from .data_layers import ReferenceDataCatalog
from .versions import summarize_staleness


def check_graphhopper(config: TRILConfig) -> Dict[str, Any]:
    """Check GraphHopper service connectivity."""
    if config.services.router_mode != "graphhopper":
        return {"status": "skipped", "reason": "router_mode is not graphhopper"}

    url = f"{config.services.graphhopper_url}/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": config.services.user_agent})
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            return {"status": "healthy", "http_status": resp.status, "response": body[:200]}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


def check_nominatim(config: TRILConfig) -> Dict[str, Any]:
    """Check Nominatim service connectivity with a known-good query."""
    if config.services.geocoder_mode != "nominatim":
        return {"status": "skipped", "reason": "geocoder_mode is not nominatim"}

    url = f"{config.services.nominatim_url}/search?q=Tobyhanna+PA&format=jsonv2&limit=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": config.services.user_agent})
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if payload:
                return {"status": "healthy", "http_status": resp.status, "result_count": len(payload)}
            return {"status": "degraded", "reason": "query returned empty results"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


def check_reference_data(config: TRILConfig) -> Dict[str, Any]:
    """Check reference data freshness and completeness."""
    catalog = ReferenceDataCatalog(config.data_dir)
    versions = catalog.build_version_summary()
    staleness = summarize_staleness(versions)

    stale_sources = [key for key, info in staleness.items() if info.get("is_stale")]
    missing_sources = [key for key, info in staleness.items() if info.get("status") == "missing"]

    if stale_sources or missing_sources:
        status = "degraded"
    else:
        status = "healthy"

    return {
        "status": status,
        "sources": staleness,
        "stale": stale_sources,
        "missing": missing_sources,
        "stale_after_days": config.stale_after_days,
    }


def health_check(config: TRILConfig | None = None) -> Dict[str, Any]:
    """Run all health checks and return aggregated status."""
    config = config or TRILConfig()
    now = datetime.now(timezone.utc).isoformat()

    checks = {
        "graphhopper": check_graphhopper(config),
        "nominatim": check_nominatim(config),
        "reference_data": check_reference_data(config),
    }

    statuses = [c["status"] for c in checks.values()]
    if any(s == "unhealthy" for s in statuses):
        overall = "unhealthy"
    elif any(s == "degraded" for s in statuses):
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "timestamp": now,
        "service": "tril",
        "node": "hannibal-edge",
        "checks": checks,
    }


if __name__ == "__main__":
    result = health_check()
    print(json.dumps(result, indent=2))
