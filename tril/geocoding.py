from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterable, List, Sequence

from .models import GeocodeResult

logger = logging.getLogger("tril.geocoding")


class GeocodingError(Exception):
    def __init__(self, message: str, failed_input: str):
        super().__init__(message)
        self.failed_input = failed_input


# ---------------------------------------------------------------------------
# Circuit breaker — shared across geocoding and routing
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Simple circuit breaker: opens after N consecutive failures, resets after cooldown."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown_seconds
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.cooldown:
            # Half-open: allow one attempt through
            return False
        return True

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._opened_at = time.monotonic()

    def reset(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None


def _retry_with_backoff(
    fn,
    max_retries: int = 3,
    base_delay: float = 0.5,
    breaker: CircuitBreaker | None = None,
    label: str = "request",
):
    """Call fn() with exponential backoff. Respects circuit breaker if provided."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        if breaker and breaker.is_open:
            raise RuntimeError(f"Circuit breaker open for {label} — service unavailable")
        try:
            result = fn()
            if breaker:
                breaker.record_success()
            return result
        except Exception as exc:
            last_exc = exc
            if breaker:
                breaker.record_failure()
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning("[%s] attempt %d/%d failed (%s), retrying in %.1fs", label, attempt, max_retries, exc, delay)
                time.sleep(delay)
            else:
                logger.error("[%s] all %d attempts failed: %s", label, max_retries, exc)
    raise last_exc  # type: ignore[misc]


class StubGeocoder:
    def __init__(self, curated: Dict[str, GeocodeResult] | None = None):
        self.curated = curated or {}

    def geocode_one(self, text: str) -> GeocodeResult:
        key = text.strip()
        if key in self.curated:
            return self.curated[key]
        raise GeocodingError("Unable to geocode input with local stub geocoder", key)

    def geocode_many(self, texts: Iterable[str]) -> List[GeocodeResult]:
        return [self.geocode_one(text) for text in texts]


class NominatimGeocoder:
    def __init__(
        self,
        base_url: str,
        user_agent: str,
        timeout_seconds: float = 12.0,
        bounded_countries: Sequence[str] | None = None,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.bounded_countries = list(bounded_countries or ["us"])
        self.max_retries = max_retries
        self._breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0)

    def geocode_one(self, text: str) -> GeocodeResult:
        query = {
            "q": text,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
        }
        if self.bounded_countries:
            query["countrycodes"] = ",".join(self.bounded_countries)

        url = f"{self.base_url}/search?{urllib.parse.urlencode(query)}"

        def _do_request():
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            payload = _retry_with_backoff(
                _do_request,
                max_retries=self.max_retries,
                breaker=self._breaker,
                label=f"nominatim:{text[:40]}",
            )
        except RuntimeError as exc:
            raise GeocodingError(str(exc), text) from exc
        except Exception as exc:
            raise GeocodingError(f"Nominatim request failed: {exc}", text) from exc

        if not payload:
            raise GeocodingError("Nominatim returned no matches", text)

        match = payload[0]
        try:
            lat = float(match["lat"])
            lon = float(match["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise GeocodingError("Nominatim response missing coordinates", text) from exc

        confidence = _confidence_from_importance(match.get("importance"))
        return GeocodeResult(
            input_text=text,
            matched_name=match.get("display_name", text),
            coordinates=(lat, lon),
            confidence=confidence,
        )

    def geocode_many(self, texts: Iterable[str]) -> List[GeocodeResult]:
        return [self.geocode_one(text) for text in texts]


def _confidence_from_importance(value: object) -> float:
    try:
        importance = float(value)
    except (TypeError, ValueError):
        return 0.7
    return round(max(0.3, min(0.99, importance)), 4)


def default_curated_locations() -> Dict[str, GeocodeResult]:
    return {
        "DC6080": GeocodeResult("DC6080", "DC6080 Tobyhanna, PA", (41.1770, -75.4174), 0.99),
        "S9196": GeocodeResult("S9196", "S9196 Johnstown, NY", (43.0209, -74.3671), 0.99),
        "S4153": GeocodeResult("S4153", "S4153 Old Bridge, NJ", (40.3913, -74.3402), 0.99),
        "Tobyhanna, PA": GeocodeResult("Tobyhanna, PA", "Tobyhanna, PA", (41.1770, -75.4174), 0.95),
        "Johnstown, NY": GeocodeResult("Johnstown, NY", "Johnstown, NY", (43.0067, -74.3701), 0.95),
    }
