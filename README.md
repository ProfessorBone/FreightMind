# FreightMind — Truck Routing Intelligence Layer

A governed, truck-safe routing intelligence system that generates legally compliant routes for commercial motor vehicles up to 80,000 lb GVW, with independent constraint validation, data confidence scoring, and Hours of Service awareness.

FreightMind is not a GPS. It is not a navigation UI. It is a **governed decision system** for route legality, safety, and compliance.

## What It Does

- **Generates truck-legal routes** using OpenStreetMap data through a locally deployed GraphHopper routing engine with a truck-aware profile
- **Validates every route segment independently** against height, weight, length, axle load, HGV prohibition, and hazmat constraints
- **Scores data confidence** using a 4-tier model that explicitly reports how much the system trusts its own data
- **Analyzes Hours of Service compliance** and recommends reset locations (driver-preferred stops, Walmart "Okay Break" locations, general truck parking) when routes exceed available drive time
- **Exports Garmin-compatible GPX files** for transfer to in-cab navigation devices
- **Exposes an MCP tool interface** (`generate_truck_safe_route`) for integration with AI agents via the Model Context Protocol
- **Logs every decision** to an auditable JSONL trail with SHA-256 route hashes and governance trace IDs

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   FreightMind Engine                    │
│                                                         │
│  Layer 1: Data Layer (OSM + NBI + State DOT overlays)  │
│  Layer 2: Routing Engine (GraphHopper) + Geocoding     │
│  Layer 3: Constraint Engine (AUTHORITATIVE)            │
│  Layer 4: Preference Engine (driver-specific)          │
│  Layer 5: HOS Awareness + Reset Recommendations       │
│  Layer 6: Reference Data (curated datasets)            │
│  Layer 7: Output Layer (GPX / JSON / Links)            │
│                                                         │
│  ┌───────────────┐    ┌────────────────────┐           │
│  │  Nominatim    │    │   GraphHopper      │           │
│  │  (Geocoding)  │    │   (Truck Routing)  │           │
│  │  Port 8080    │    │   Port 8989        │           │
│  └───────────────┘    └────────────────────┘           │
└─────────────────────────────────────────────────────────┘
         ▲                        ▲
         │    MCP Tool Interface  │
         └────────┬───────────────┘
                  │
         ┌────────▼────────┐
         │  FreightMind    │
         │  Agent          │
         └─────────────────┘
```

## Key Design Principles

**The Constraint Engine is authoritative.** It operates independently of the routing engine and overrides routing engine assumptions. If the routing engine says a road is passable and the Constraint Engine says it isn't, the Constraint Engine wins.

**The system never returns an unvalidated route.** If it cannot produce a validated route within 5 retry attempts, it returns an explicit `NO_SAFE_ROUTE` failure with violation reports — never a silent pass-through.

**Data confidence is transparent.** Every route output includes a confidence score and a per-tier breakdown showing exactly how much of the route is backed by verified data versus inferred or unknown data.

**HOS is a safety constraint, not a convenience feature.** A route that is physically legal but exceeds the driver's available hours is not a safe route. The system treats fatigue risk with the same authority as bridge clearance.

## Quick Start

### Prerequisites

- Python 3.11+
- Java 17+ (for GraphHopper)
- Docker (for Nominatim)
- ~20GB disk space for OSM data and graph cache

### 1. Deploy Services

```bash
# Download GraphHopper and OSM data
mkdir -p ~/tril-services/{graphhopper,osm-data,logs}
cd ~/tril-services/graphhopper
curl -L -o graphhopper-web-11.0.jar \
  https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/11.0/graphhopper-web-11.0.jar

cd ~/tril-services/osm-data
curl -L -o us-northeast-latest.osm.pbf \
  https://download.geofabrik.de/north-america/us-northeast-latest.osm.pbf

# Start GraphHopper (first run builds the graph — takes 30-90 min)
cd ~/tril-services/graphhopper
java -Xmx8g -jar graphhopper-web-11.0.jar server tril-config.yml

# Start Nominatim via Docker
docker run -d --name tril-nominatim --shm-size=512m \
  -e PBF_PATH=/data/us-northeast-latest.osm.pbf \
  -v ~/tril-services/osm-data:/data:ro \
  -p 8080:8080 --restart unless-stopped \
  mediagis/nominatim:4.4
```

### 2. Configure Environment

```bash
export TRIL_GEOCODER_MODE=nominatim
export TRIL_ROUTER_MODE=graphhopper
export TRIL_NOMINATIM_URL=http://127.0.0.1:8080
export TRIL_GRAPHHOPPER_URL=http://127.0.0.1:8989
export TRIL_GRAPHHOPPER_PROFILE=truck
```

### 3. Generate a Route

**CLI:**
```bash
python -m tril.cli "Tobyhanna, PA" "Carlisle, PA" \
  --remaining-drive-hours 6.5 \
  --remaining-duty-hours 10.0
```

**Python:**
```python
from tril.engine import TRILEngine
from tril.models import RouteRequest, HOSState

engine = TRILEngine()
request = RouteRequest(
    origin="Tobyhanna, PA",
    destination="Carlisle, PA",
    hos=HOSState(remaining_drive_hours=6.5, remaining_duty_hours=10.0)
)
result = engine.run(request)

print(f"Status: {result.status}")
print(f"Distance: {result.route['distance_miles']} miles")
print(f"Confidence: {result.route['confidence_score']}")
print(f"HOS Warning: {result.hos_analysis['hos_warning']}")
```

**MCP Tool (for AI agent integration):**
```python
from tril.mcp_tool import generate_truck_safe_route

result = generate_truck_safe_route(
    origin="Tobyhanna, PA",
    destination="Carlisle, PA",
    vehicle_profile={"height_ft": 13.5, "weight_lb": 80000, "length_ft": 70, "axles": 5},
    hos={"remaining_drive_hours": 6.5, "remaining_duty_hours": 10.0}
)
```

### Example Output

```
Status: ROUTE_FOUND
Distance: 146.375 miles
Drive time: 2.854 hours
Confidence: 0.85
Engine: graphhopper-local

HOS Warning: True
Summary: Route busts drive clock. Drive over by 1.35h, duty over by 0.35h.
         Stage a reset before Walmart Supercenter - Carlisle, PA.
```

## Tech Stack

- **Python 3.11+** — control, orchestration, constraint engine, MCP interface
- **GraphHopper 11.0** — open source routing engine (Java, self-hosted)
- **Nominatim** — open source geocoding (Docker, self-hosted)
- **OpenStreetMap** — road network data (Geofabrik regional extracts)
- **FHWA National Bridge Inventory** — supplemental bridge clearance data
- **MCP (Model Context Protocol)** — AI agent tool integration

## Testing

```bash
# Run eval harness (stub mode)
python -m tril.eval_harness

# Run production validation (103 test cases)
python -m tril.tests.production_validation          # stub mode (50 tests)
python -m tril.tests.production_validation --live    # live mode (53 tests)

# Run Will Graham integration tests
python -m tril.tests.will_graham_integration         # stub mode (11 tests)
python -m tril.tests.will_graham_integration --live   # live mode (11 tests)

# Health check
python -c "from tril.health import check_all; print(check_all())"
```

## Project Structure

```
tril/
├── engine.py           # Core orchestration — geocode → route → validate → score → output
├── models.py           # Data models (RouteRequest, RouteResult, Segment, Violation, etc.)
├── config.py           # Runtime configuration with env-var switching (stub ↔ live)
├── geocoding.py        # Nominatim adapter + stub geocoder
├── routing.py          # GraphHopper adapter + stub router
├── constraints.py      # Independent constraint engine (AUTHORITATIVE)
├── confidence.py       # 4-tier data confidence model and scoring
├── hos.py              # Hours of Service analysis + reset recommendations
├── data_layers.py      # NBI + state DOT reference data overlay system
├── outputs.py          # GPX (Garmin-compatible) + JSON + Google Maps link generation
├── mcp_tool.py         # MCP tool wrapper (generate_truck_safe_route)
├── mcp_server.py       # MCP stdio server for AI agent integration
├── health.py           # Service health checks
├── metrics.py          # Operational metrics tracking
├── logging_utils.py    # Audit logging with SHA-256 route hashing
├── versions.py         # Data versioning and staleness detection
├── cli.py              # Command-line interface
├── eval_harness.py     # Evaluation framework (adapted from Anthropic Academy pattern)
├── data/               # Reference datasets (NBI, state overlays, Walmart Okay Breaks)
├── deployment/         # Deployment configs and documentation
├── docs/               # Operational runbook
├── tests/              # Integration and production validation tests
├── scripts/            # Deployment and maintenance scripts
├── examples/           # Sample routes and fixtures
├── logs/               # Validation audit logs (gitignored)
└── out/                # Generated route outputs (gitignored)
```

## Specification

FreightMind is built against a formal engineering specification: [PACS-APP-TRIL-001 v0.3](spec/PACS-APP-TRIL-001_v0.3.md). The spec defines the 7-layer architecture, data confidence model, constraint validation rules, retry/termination strategy, HOS awareness logic, output formats, MCP tool interface, and governance principles.

## Part of Continuum

FreightMind is a component of the **Continuum** multi-agent architecture — a governed AI system where specialized agents handle distinct operational domains under centralized oversight. Within Continuum:

- **Jack Crawford** is the governance agent that oversees system integrity
- **Will Graham** is the trucking operations agent that calls FreightMind to generate routes
- **FreightMind** is the routing intelligence layer that Will Graham relies on for legally compliant, truck-safe route decisions

The system communicates via the Model Context Protocol (MCP) and operates on a hub-and-spoke model with edge deployment capability.

## About the Author

Built by **Faheem** — an OTR truck driver for Walmart Private Fleet and AI engineering student at Johns Hopkins University (Agentic AI Certificate Program). FreightMind was designed from real operational experience driving an 80,000 lb, 70-foot, 13'6" tractor-trailer across the Northeast US corridor (Maine to North Carolina, west to Ohio).

This system exists because commercial truck routing is a safety-critical domain where existing tools fall short. Consumer GPS doesn't understand truck constraints. Commercial routing tools don't expose their reasoning. FreightMind is built on the principle that a routing system for trucks should be transparent about what it knows, honest about what it doesn't know, and governed by the same safety standards that apply to the driver behind the wheel.

## License

MIT License — see [LICENSE](LICENSE) for details.
