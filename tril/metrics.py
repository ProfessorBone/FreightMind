"""
TRIL Operational Metrics
In-process counters for observability. Persists to JSONL on flush.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List


class TRILMetrics:
    """Collects route-level metrics during engine lifetime."""

    def __init__(self):
        self._lock = Lock()
        self._routes_total = 0
        self._routes_success = 0
        self._routes_failed = 0
        self._geocoding_failures = 0
        self._rate_limited = 0
        self._constraint_violations_total = 0
        self._response_times: List[float] = []
        self._confidence_scores: List[float] = []
        self._safety_scores: List[float] = []
        self._status_counts: Dict[str, int] = {}
        self._started_at = time.monotonic()

    # -- recording ----------------------------------------------------------

    def record_route(
        self,
        status: str,
        elapsed_seconds: float,
        confidence_score: float | None = None,
        safety_score: float | None = None,
        violations_found: int = 0,
    ) -> None:
        with self._lock:
            self._routes_total += 1
            self._status_counts[status] = self._status_counts.get(status, 0) + 1
            self._response_times.append(elapsed_seconds)
            self._constraint_violations_total += violations_found

            if status == "ROUTE_FOUND":
                self._routes_success += 1
                if confidence_score is not None:
                    self._confidence_scores.append(confidence_score)
                if safety_score is not None:
                    self._safety_scores.append(safety_score)
            elif status == "GEOCODING_FAILED":
                self._routes_failed += 1
                self._geocoding_failures += 1
            elif status == "RATE_LIMITED":
                self._routes_failed += 1
                self._rate_limited += 1
            else:
                self._routes_failed += 1

    # -- queries ------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Return a point-in-time snapshot of all metrics."""
        with self._lock:
            uptime = time.monotonic() - self._started_at
            p50, p95, p99 = _percentiles(self._response_times, [50, 95, 99])
            conf_p50, conf_p95, _ = _percentiles(self._confidence_scores, [50, 95, 99])
            safety_p50, _, _ = _percentiles(self._safety_scores, [50, 95, 99])

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": round(uptime, 1),
                "routes": {
                    "total": self._routes_total,
                    "success": self._routes_success,
                    "failed": self._routes_failed,
                    "success_rate": round(self._routes_success / self._routes_total, 4) if self._routes_total else 0,
                },
                "status_counts": dict(self._status_counts),
                "errors": {
                    "geocoding_failures": self._geocoding_failures,
                    "rate_limited": self._rate_limited,
                },
                "constraint_violations_total": self._constraint_violations_total,
                "response_time_seconds": {
                    "p50": p50,
                    "p95": p95,
                    "p99": p99,
                    "count": len(self._response_times),
                },
                "confidence_scores": {
                    "p50": conf_p50,
                    "p95": conf_p95,
                    "count": len(self._confidence_scores),
                },
                "safety_scores": {
                    "p50": safety_p50,
                    "count": len(self._safety_scores),
                },
            }

    def flush(self, log_dir: Path) -> Path:
        """Write current snapshot to metrics JSONL and return the path."""
        snap = self.snapshot()
        path = log_dir / "metrics.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snap, default=str) + "\n")
        return path


def _percentiles(values: List[float], pcts: List[int]) -> List[float | None]:
    if not values:
        return [None] * len(pcts)
    s = sorted(values)
    n = len(s)
    result = []
    for p in pcts:
        idx = int(n * p / 100)
        idx = min(idx, n - 1)
        result.append(round(s[idx], 4))
    return result


# Module-level singleton — importable from anywhere
metrics = TRILMetrics()
