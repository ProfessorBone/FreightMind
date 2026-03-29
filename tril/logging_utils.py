from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Continuum governance — trace context
# ---------------------------------------------------------------------------

def continuum_trace_id() -> str:
    """Generate a Continuum-compatible trace ID for this request."""
    return f"tril-{uuid.uuid4().hex[:16]}"


def continuum_headers(agent: str = "will-graham", trace_id: str | None = None) -> Dict[str, str]:
    """Build Continuum governance headers for an audit record."""
    return {
        "x-continuum-trace-id": trace_id or continuum_trace_id(),
        "x-continuum-agent": agent,
        "x-continuum-node": os.getenv("CONTINUUM_NODE", "hannibal-edge"),
        "x-continuum-service": "tril",
        "x-continuum-timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple sliding-window rate limiter for MCP tool calls."""

    def __init__(self, max_calls: int = 60, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window = window_seconds
        self._timestamps: list[float] = []

    def check(self) -> bool:
        """Return True if the call is allowed, False if rate-limited."""
        now = time.monotonic()
        cutoff = now - self.window
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        if len(self._timestamps) >= self.max_calls:
            return False
        self._timestamps.append(now)
        return True

    @property
    def remaining(self) -> int:
        now = time.monotonic()
        cutoff = now - self.window
        active = sum(1 for t in self._timestamps if t > cutoff)
        return max(0, self.max_calls - active)


# Module-level rate limiter instance
_rate_limiter = RateLimiter(
    max_calls=int(os.getenv("TRIL_RATE_LIMIT_MAX", "60")),
    window_seconds=float(os.getenv("TRIL_RATE_LIMIT_WINDOW", "60")),
)


def check_rate_limit() -> bool:
    """Check whether the current request is within rate limits."""
    return _rate_limiter.check()


def rate_limit_remaining() -> int:
    return _rate_limiter.remaining


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------

def cost_metadata(start_time: float, geocode_calls: int = 0, route_calls: int = 0) -> Dict[str, Any]:
    """Build cost tracking metadata for a completed request."""
    elapsed = time.monotonic() - start_time
    return {
        "elapsed_seconds": round(elapsed, 3),
        "geocode_api_calls": geocode_calls,
        "route_api_calls": route_calls,
        "estimated_cost_units": geocode_calls + (route_calls * 2),  # routing is heavier
    }


# ---------------------------------------------------------------------------
# Core logging
# ---------------------------------------------------------------------------

def route_hash(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def append_jsonl(log_path: Path, record: Dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")


def audit_record(
    event: str,
    payload: Dict[str, Any],
    metadata: Dict[str, Any] | None = None,
    trace_id: str | None = None,
    agent: str = "will-graham",
    cost: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "route_hash": route_hash(payload),
        "continuum": continuum_headers(agent=agent, trace_id=trace_id),
        "metadata": metadata or {},
        "payload": normalize(payload),
    }
    if cost:
        record["cost"] = cost
    return record



def normalize(value: Any) -> Any:
    if is_dataclass(value):
        return normalize(asdict(value))
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, tuple):
        return [normalize(item) for item in value]
    return value
