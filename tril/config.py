from __future__ import annotations

import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DataVersions:
    osm_extract_date: str = "2026-03-27"
    nbi_version: str = "nbi-2026.03-midatlantic-demo"
    state_overlay_version: str = "state-overlays-2026.03-tristate-demo"
    walmart_breaks_version: str = "manual-v1"


@dataclass
class ServiceEndpoints:
    geocoder_mode: str = field(default_factory=lambda: os.getenv("TRIL_GEOCODER_MODE", "stub"))
    router_mode: str = field(default_factory=lambda: os.getenv("TRIL_ROUTER_MODE", "stub"))
    nominatim_url: str = field(default_factory=lambda: os.getenv("TRIL_NOMINATIM_URL", "http://127.0.0.1:8080"))
    graphhopper_url: str = field(default_factory=lambda: os.getenv("TRIL_GRAPHHOPPER_URL", "http://127.0.0.1:8989"))
    graphhopper_profile: str = field(default_factory=lambda: os.getenv("TRIL_GRAPHHOPPER_PROFILE", "truck"))
    user_agent: str = field(default_factory=lambda: os.getenv("TRIL_HTTP_USER_AGENT", "TRIL/0.1 (+local Hannibal runtime)"))
    request_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("TRIL_HTTP_TIMEOUT", "12")))


@dataclass
class OSMIngestionConfig:
    extracts_dirname: str = "extracts"
    graph_dirname: str = "graphhopper"
    import_plan_file: str = "osm_ingestion_sources.json"
    nominatim_import_style_file: str = "nominatim.import.style"


@dataclass
class TRILConfig:
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
    max_retry_attempts: int = 5
    stale_after_days: int = 60
    route_alternatives: int = 3
    preferred_corridors: List[str] = field(default_factory=lambda: ["I-81", "I-78", "I-80"])
    avoid_zones: List[str] = field(default_factory=lambda: ["NYC Metro", "DC Beltway"])
    preferred_stop_labels: List[str] = field(default_factory=lambda: ["Pilot Flying J", "Love's Travel Stop"])
    driver_preferences: Optional[Dict[str, Any]] = None
    versions: DataVersions = field(default_factory=DataVersions)
    services: ServiceEndpoints = field(default_factory=ServiceEndpoints)
    osm_ingestion: OSMIngestionConfig = field(default_factory=OSMIngestionConfig)
    
    def __post_init__(self):
        """Load production config and driver preferences if available."""
        if os.getenv("TRIL_PRODUCTION_MODE", "").lower() == "true":
            self._load_production_config()
        self._load_driver_preferences()

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / "logs"

    @property
    def out_dir(self) -> Path:
        return self.base_dir / "out"

    @property
    def extracts_dir(self) -> Path:
        return self.data_dir / self.osm_ingestion.extracts_dirname

    @property
    def graph_dir(self) -> Path:
        return self.data_dir / self.osm_ingestion.graph_dirname

    @property
    def osm_ingestion_plan_path(self) -> Path:
        return self.data_dir / self.osm_ingestion.import_plan_file
    
    def _load_driver_preferences(self):
        """Load driver preferences from YAML file if it exists."""
        preferences_path = self.data_dir / "driver_preferences.yaml"
        
        if preferences_path.exists():
            try:
                with preferences_path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                
                if data and "preferences" in data:
                    prefs = data["preferences"]
                    
                    # Override defaults with YAML values
                    if "avoid_zones" in prefs:
                        self.avoid_zones = [zone.get("label", "") for zone in prefs["avoid_zones"]]
                    
                    if "preferred_corridors" in prefs:
                        corridors = []
                        for corridor in prefs["preferred_corridors"]:
                            if "road_refs" in corridor:
                                corridors.extend(corridor["road_refs"])
                        if corridors:
                            self.preferred_corridors = corridors
                    
                    if "preferred_stops" in prefs:
                        self.preferred_stop_labels = [stop.get("label", "") for stop in prefs["preferred_stops"]]
                    
                    # Store full preferences for advanced use
                    self.driver_preferences = prefs
                    
                    print(f"[TRIL] Loaded driver preferences from {preferences_path}")
            except (yaml.YAMLError, KeyError) as e:
                print(f"[TRIL] Warning: Failed to load driver preferences: {e}")
                # Keep defaults on error

    def _load_production_config(self):
        """Apply production.yaml overrides when TRIL_PRODUCTION_MODE=true."""
        production_path = self.data_dir / "production.yaml"
        if not production_path.exists():
            print("[TRIL] Warning: Production mode set but production.yaml not found")
            return

        try:
            with production_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                return

            # Apply service overrides (env vars still take precedence)
            svc = data.get("services", {})
            if not os.getenv("TRIL_GEOCODER_MODE"):
                self.services.geocoder_mode = svc.get("geocoder_mode", self.services.geocoder_mode)
            if not os.getenv("TRIL_ROUTER_MODE"):
                self.services.router_mode = svc.get("router_mode", self.services.router_mode)
            self.services.request_timeout_seconds = svc.get(
                "request_timeout_seconds", self.services.request_timeout_seconds
            )
            self.services.user_agent = svc.get("user_agent", self.services.user_agent)

            # Apply engine overrides
            eng = data.get("engine", {})
            self.max_retry_attempts = eng.get("max_retry_attempts", self.max_retry_attempts)
            self.route_alternatives = eng.get("route_alternatives", self.route_alternatives)
            self.stale_after_days = eng.get("stale_after_days", self.stale_after_days)

            print(f"[TRIL] Production config loaded from {production_path}")
        except (yaml.YAMLError, KeyError) as e:
            print(f"[TRIL] Warning: Failed to load production config: {e}")
