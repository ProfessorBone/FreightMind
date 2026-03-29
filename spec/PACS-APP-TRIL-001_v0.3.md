# CONTINUUM BUILD SPEC — TRUCK ROUTING INTELLIGENCE LAYER (TRIL)

---

## METADATA

| Field             | Value                                    |
|-------------------|------------------------------------------|
| Artifact ID       | PACS-APP-TRIL-001                        |
| Version           | v0.3                                     |
| Status            | DESIGN                                   |
| Owner             | Faheem / Continuum                       |
| Governed By       | Continuum Control Plane                  |
| Execution Runtime | OpenClaw (Will Graham Agent)             |
| Edge Node         | Hannibal (MacBook Pro M4 Max)            |
| Last Updated      | 2026-03-27                               |
| Change Log        | v0.3: Closed 12 structural gaps from v0.2 review. Added data confidence model, geocoding layer, retry/termination strategy, HOS-aware reset recommendation, enriched output schema, Garmin GPX dialect spec, data versioning strategy. Scoped axle usage. Clarified MVP vs deferred boundaries across all layers. |

---

## 0. PURPOSE

Build a truck-safe routing intelligence system that:

- Generates legally compliant routes for CMVs up to 80,000 lb GVW
- Accounts for all physical and regulatory constraints, including vehicle height, vehicle weight, vehicle length, axle configuration, hazmat classification, and truck-restricted roads
- Recommends compliant rest/reset locations when routes exceed remaining Hours of Service
- Learns and adapts to driver-specific preferences over time
- Outputs routes to external navigation systems (Garmin devices, mobile apps, GPX consumers)
- Operates as a governed intelligence layer, not a navigation UI

---

## 1. SYSTEM ROLE (PEAS)

### Performance

- Zero illegal route segments (hard constraint)
- Minimized travel time and distance (soft optimization)
- High alignment with driver preferences
- Deterministic, reproducible route generation
- Transparent data confidence reporting on every route

### Environment

- U.S. road network
- Static constraints: OSM, FHWA National Bridge Inventory, state DOT restricted route data
- Driver state: remaining HOS drive time
- Optional dynamic inputs (traffic, weather — deferred to Phase 2+)

### Actuators

- Route generation
- Route scoring
- Route validation
- Reset location recommendation
- Output generation (GPX, JSON, link formats)

### Sensors

- Trip input (origin, stops, destination)
- Vehicle profile (height, weight, length, axles, hazmat)
- Map data (OSM + supplemental sources)
- Constraint datasets (federal, state, local)
- Driver HOS state (remaining drive hours)
- Historical driver decisions

---

## 2. ARCHITECTURE

---

### Layer 1 — Data Layer

#### Primary Source: OpenStreetMap (OSM)

Provides the road graph and constraint metadata.

Required tags (must be ingested and normalized):

- maxheight — vertical clearance
- maxweight — load limits (gross vehicle weight)
- maxweight:hgv — HGV-specific weight limits where present
- maxlength — vehicle length restrictions
- hgv=* — heavy goods vehicle access permissions
- hazmat=* — hazardous material restrictions
- turn:lanes and junction — used by Layer 3 for turn feasibility (Phase 2)

#### Supplemental Source: FHWA National Bridge Inventory (NBI)

The NBI provides verified bridge clearance data for the entire United States. This is the authoritative fallback when OSM maxheight tags are missing.

Ingestion requirements:

- NBI records must be geocoded and mapped to corresponding OSM road segments
- Where both OSM and NBI provide clearance data, use the MORE RESTRICTIVE value
- NBI data must be refreshed on the same cycle as OSM data (see Section 11)

#### Supplemental Source: State DOT Restricted Route Data

Many states maintain designated truck route networks and restricted roads that are not reliably captured in OSM. The following states are priority for MVP based on Faheem's primary operating corridors:

- Pennsylvania (PennDOT restricted roads)
- New York (NYC truck route network, Parkway system exclusions)
- New Jersey (NJDOT truck restrictions)

Ingestion approach: State DOT data is published in varying formats (PDF, GIS shapefiles, web databases). For MVP, critical restrictions are encoded as a supplemental constraint overlay — a curated set of road segment IDs with associated restriction flags, maintained manually and version-controlled.

#### Data Normalization Requirements

- Convert all units to U.S. standard: feet for height/length, pounds for weight
- Handle missing tags using the Data Confidence Model (see Section 2.1)

---

### 2.1 — Data Confidence Model

OSM tag completeness varies significantly across the U.S. road network. The system must explicitly classify every road segment by data confidence level and expose that classification in route outputs.

#### Confidence Tiers

**Tier 1 — Verified**: Segment has relevant constraint tags in OSM AND is corroborated by NBI or state DOT data. The system treats these constraints as authoritative.

**Tier 2 — Single Source**: Segment has relevant constraint tags in OSM OR in a supplemental source, but not both. The system treats these constraints as trustworthy but flags them.

**Tier 3 — Inferred**: Segment has no explicit constraint tags, but road classification (e.g., interstate, US highway, state route) provides strong inference. Interstates are inferred as truck-legal unless explicitly restricted. Local and residential roads are inferred as potentially restricted.

**Tier 4 — Unknown**: Segment has no constraint tags, no supplemental data, and road classification does not provide reliable inference. The system MUST flag these segments.

#### Routing Behavior by Tier

- Tier 1 and 2 segments: Route normally, apply constraints as stated
- Tier 3 segments: Route with a configurable penalty weight (default: moderate penalty for non-highway inferred segments)
- Tier 4 segments: Route with a high penalty. If the best available route contains Tier 4 segments, the route is flagged in the output with an explicit warning and the specific segments are identified

#### Route-Level Confidence Score

The overall route confidence score is calculated as the weighted proportion of distance covered by each tier:

    route_confidence = (d_tier1 * 1.0 + d_tier2 * 0.85 + d_tier3 * 0.6 + d_tier4 * 0.2) / total_distance

This score is reported in every route output.

---

### Layer 2 — Routing Engine

#### Geocoding Subsystem

The MCP tool accepts origin, destination, and stops as human-readable strings. These must be geocoded to coordinates before routing.

Geocoding engine: Nominatim (OSM-based, self-hostable, no API key required for local deployment).

Geocoding rules:

- All input strings are geocoded before any routing call
- If geocoding fails (no result or ambiguous result), the system returns an error to Will Graham with the specific input that failed and a request for clarification
- Geocoding results are logged for reproducibility
- For truck stops, fuel stations, and Walmart locations: a curated coordinate database is preferred over live geocoding (see Layer 6)

#### Routing Engine

Primary engine: GraphHopper (self-hosted, open source, supports custom vehicle profiles).

Alternative: OSRM (if GraphHopper proves unsuitable during MVP build).

#### Vehicle Profile (Required Input)

    vehicle:
      height: 13.5       # feet
      weight: 80000      # pounds (GVW)
      length: 70         # feet
      axles: 5
      hazmat: false

#### Routing Rules (MANDATORY)

Routes MUST:

- Exclude edges where maxheight < vehicle.height
- Exclude edges where maxweight < vehicle.weight
- Exclude edges where maxlength < vehicle.length
- Exclude edges where hgv = no or equivalent
- Exclude edges where hazmat restriction applies and vehicle.hazmat = true

Routes SHOULD penalize:

- Residential roads (high penalty)
- Roads with narrow geometry (moderate penalty)
- Sharp turns incompatible with 70ft vehicle length (high penalty — enforced via GraphHopper turn cost model)
- Tier 3 and Tier 4 confidence segments (per Data Confidence Model)

Routes SHOULD prefer:

- Interstates and major highways
- Designated truck routes (state DOT data)
- Roads with Tier 1 or Tier 2 confidence data

#### Route Alternatives

GraphHopper must be configured to return the top 3 alternative routes per request. All three are passed through the Constraint Engine (Layer 3) and scored by the Preference Engine (Layer 4). Will Graham receives all validated alternatives, ranked.

---

### Layer 3 — Constraint Engine (AUTHORITATIVE)

This layer has final authority over route legality. It operates independently of the routing engine and overrides routing engine assumptions.

#### Purpose

Guarantee legal compliance and physical feasibility for every route segment.

#### Segment-Level Validation

    for each road_segment in route:
        if segment.maxheight < vehicle.height:
            reject_segment -> flag_reason("HEIGHT_VIOLATION", segment_id, segment.maxheight)
        if segment.maxweight < vehicle.weight:
            reject_segment -> flag_reason("WEIGHT_VIOLATION", segment_id, segment.maxweight)
        if segment.maxlength < vehicle.length:
            reject_segment -> flag_reason("LENGTH_VIOLATION", segment_id, segment.maxlength)
        if segment.hazmat_restricted and vehicle.hazmat:
            reject_segment -> flag_reason("HAZMAT_VIOLATION", segment_id)
        if segment.hgv_prohibited:
            reject_segment -> flag_reason("HGV_PROHIBITED", segment_id)

#### Axle-Aware Weight Validation

Bridge weight postings frequently specify per-axle limits in addition to gross weight limits. Where per-axle data is available (from NBI or state sources):

    if segment.has_axle_weight_limit:
        estimated_axle_load = vehicle.weight / vehicle.axles  # simplified; MVP approximation
        if estimated_axle_load > segment.max_axle_weight:
            reject_segment -> flag_reason("AXLE_WEIGHT_VIOLATION", segment_id)

Note: This is a simplified model. True axle load distribution depends on cargo placement and vehicle configuration. Phase 2 may accept a detailed axle weight array. For MVP, the uniform distribution approximation with a 10% safety margin is acceptable.

#### Sequence-Level Validation (Phase 2)

Turn-angle feasibility at intersections is a sequence-level constraint. A 70-foot vehicle cannot execute turns that are individually legal on each approach segment but physically impossible at the junction.

Phase 2 scope:

- Extract junction geometry from OSM (turn:lanes, node angles)
- Calculate minimum turning radius requirement for vehicle length
- Reject junction transitions where turn angle exceeds feasibility threshold

MVP mitigation: GraphHopper's truck profile applies turn cost penalties based on vehicle dimensions. This provides partial coverage. The Constraint Engine does NOT independently validate turn feasibility in MVP — this is a known limitation that must be documented in route output.

#### Constraint Categories (Summary)

1. Height clearance (bridge, tunnel, overpass)
2. Gross vehicle weight
3. Per-axle weight (where data available)
4. Vehicle length
5. Hazmat restrictions
6. HGV prohibitions (road-level, zone-level)
7. Turn feasibility (Phase 2)

---

### 3.1 — Retry Strategy and Termination

When the Constraint Engine rejects a route, the system must have a defined recovery path.

#### Retry Logic

1. On rejection, the Constraint Engine returns the specific failing segment IDs and violation types
2. The failing segments are added to a per-request blacklist
3. GraphHopper is re-queried with the blacklist applied as additional edge exclusions
4. The new route is re-validated by the Constraint Engine

#### Termination Conditions

- Maximum retry count: 5 attempts per route request
- If all 5 attempts are rejected, the system returns a NO_SAFE_ROUTE response
- The NO_SAFE_ROUTE response includes: all violation reports from all attempts, the "least bad" route (fewest violations) with violations explicitly flagged, and a recommendation to the driver to consult a commercial routing atlas or contact dispatch

#### Critical Rule

The system NEVER returns an unvalidated route. If it cannot produce a validated route within the retry limit, it returns an explicit failure rather than a silent pass-through.

---

### Layer 4 — Preference Learning Engine

#### Purpose

Adapt routing to Faheem-specific driving behavior and preferences.

#### MVP Scope (Manual Configuration)

For MVP, preferences are encoded as a static configuration file — not learned from data. The preference file is a YAML document maintained by Faheem and version-controlled with the system.

    preferences:
      avoid_zones:
        - label: "NYC Metro"
          penalty: 0.95
          bounding_box: [40.4, -74.3, 41.0, -73.7]
        - label: "DC Beltway"
          penalty: 0.7
          bounding_box: [38.7, -77.3, 39.1, -76.8]

      preferred_corridors:
        - label: "I-81 Shenandoah"
          bonus: 0.3
          road_refs: ["I-81"]
        - label: "I-78/I-80 PA"
          bonus: 0.2
          road_refs: ["I-78", "I-80"]

      preferred_stops:
        - label: "Pilot Flying J"
          type: fuel
        - label: "Love's Travel Stop"
          type: fuel
        - label: "Walmart Okay Break"
          type: reset
          source: "curated_walmart_list"

      avoid_patterns:
        - type: "tight_urban_turns"
          penalty: 0.6

#### Scoring Function

    route_score = (
        base_efficiency_score
        + sum(corridor_bonuses)
        - sum(zone_penalties)
        - sum(pattern_penalties)
        + preference_stop_proximity
    )

#### Deferred (Phase 2+)

- Automated preference learning from accepted/rejected route history
- ML-based preference model trained on historical driver decisions
- Dynamic preference adjustment based on time of day, day of week

---

### Layer 5 — Hours of Service (HOS) Awareness

#### Purpose

Ensure that no route is delivered to the driver without accounting for remaining legal drive time, and recommend compliant reset locations when the route exceeds available hours.

#### MVP Scope

The system accepts remaining drive time as an input parameter. It does NOT integrate with an ELD device in MVP — the driver (or Will Graham, from driver input) provides the value.

#### Input

    hos:
      remaining_drive_hours: 6.5
      remaining_duty_hours: 10.0

#### Logic

    if route.estimated_drive_time > hos.remaining_drive_hours:
        trigger_reset_recommendation(route, hos.remaining_drive_hours)

#### Reset Recommendation Engine

When a route exceeds remaining drive time, the system identifies the optimal point along the route to take a 10-hour reset, using the following priority stack:

**Priority 1 — Driver Preferred Stops**: Locations from the Preference Engine (Layer 4) that fall within the driveable window. This includes preferred truck stops (Pilot, Love's, etc.).

**Priority 2 — Walmart Okay Break Locations**: Walmart stores where overnight parking is permitted for CMVs. These are maintained as a curated dataset (see Layer 6). "Okay Break" is the internal term for Walmart locations that allow driver resets.

**Priority 3 — General Truck Parking**: Public rest areas and truck stops along the route corridor that are not in the driver's preference list but are legally available for overnight parking.

#### Reset Recommendation Output

When a reset is recommended, the route output includes:

    {
      "hos_warning": true,
      "remaining_drive_hours": 6.5,
      "route_drive_time_hours": 8.2,
      "overage_hours": 1.7,
      "recommended_reset": {
        "location_name": "Walmart Supercenter - Carlisle, PA",
        "location_type": "okay_break",
        "distance_from_origin_miles": 312,
        "drive_time_to_reset_hours": 5.8,
        "coordinates": [40.2012, -77.1890],
        "post_reset_remaining_miles": 211
      },
      "alternative_resets": [
        {
          "location_name": "Pilot Travel Center - Harrisburg, PA",
          "location_type": "preferred_stop",
          "distance_from_origin_miles": 295,
          "drive_time_to_reset_hours": 5.5
        }
      ]
    }

#### Deferred (Phase 2+)

- ELD integration for automatic HOS state ingestion
- 30-minute break compliance tracking
- 70-hour/8-day cycle tracking
- Predictive HOS planning for multi-day routes

---

### Layer 6 — Reference Data Layer

#### Purpose

Maintain curated, version-controlled datasets that supplement OSM and support the Preference and HOS engines.

#### Datasets

**Walmart Okay Break List**: Curated list of Walmart store locations that permit overnight CMV parking. Fields: store ID, name, address, coordinates, parking confirmed date, any known restrictions (time limits, specific lot areas).

Source: Compiled from driver community knowledge, Walmart corporate communications, and verified by Faheem's direct experience. This list is maintained manually and updated as conditions change.

**Preferred Truck Stops**: Curated coordinates and metadata for fuel stops, rest areas, and service locations that Faheem regularly uses or prefers.

**State DOT Restriction Overlays**: Per-state restriction data encoded as segment-level constraint flags (see Layer 1).

#### Data Format

All reference datasets are stored as JSON files, version-controlled alongside the system code, and loaded at system startup.

---

### Layer 7 — Output Layer

#### Supported Formats

**1. GPX (PRIMARY — Garmin Target)**

Target device: Garmin dezl series (trucking GPS).

GPX requirements:

- Use rte (route) elements, not trk (track) elements — Garmin devices recalculate tracks but follow routes
- Maximum 200 route points (rtept) per file — Garmin devices may truncate beyond this
- Route point names must be 30 characters or fewer
- Include name and desc elements at the route level
- Coordinate precision: 6 decimal places
- File naming convention: TRIL_{origin}_{destination}_{YYYYMMDD}.gpx

**2. JSON (INTERNAL)**

Used by OpenClaw, Will Graham, and Continuum governance. Contains full route data, constraint validation results, confidence scores, HOS analysis, and preference scores. This is the canonical route representation.

**3. Shareable Links (CONVENIENCE)**

Google Maps URL with waypoints. Explicitly marked as NON-AUTHORITATIVE — for human review and sharing only. Google Maps does not respect truck constraints.

---

## 3. MCP TOOL INTERFACE

### Tool Name

generate_truck_safe_route

### Input Schema

    {
      "origin": "string (address, city, or place name)",
      "destination": "string (address, city, or place name)",
      "stops": ["string (optional intermediate stops)"],
      "vehicle_profile": {
        "height_ft": 13.5,
        "weight_lb": 80000,
        "length_ft": 70,
        "axles": 5,
        "hazmat": false
      },
      "hos": {
        "remaining_drive_hours": 6.5,
        "remaining_duty_hours": 10.0
      },
      "preferences_override": {
        "avoid_zones": ["optional additional zones"],
        "prefer_corridors": ["optional additional corridors"]
      }
    }

### Output Schema

    {
      "status": "ROUTE_FOUND | NO_SAFE_ROUTE | GEOCODING_FAILED",
      "route": {
        "distance_miles": 523,
        "estimated_drive_time_hours": 8.2,
        "gpx_file": "path/to/TRIL_Tobyhanna_Charlotte_20260327.gpx",
        "confidence_score": 0.91,
        "safety_score": 0.98,
        "preference_score": 0.85,
        "data_tiers": {
          "tier_1_pct": 62,
          "tier_2_pct": 24,
          "tier_3_pct": 12,
          "tier_4_pct": 2
        }
      },
      "constraint_report": {
        "violations_found": 0,
        "warnings": [
          {
            "type": "LOW_CONFIDENCE_SEGMENT",
            "segment_id": "way/123456",
            "tier": 4,
            "description": "No clearance data available for bridge on SR-309"
          }
        ],
        "turn_feasibility_validated": false,
        "turn_feasibility_note": "Sequence-level turn validation not available in MVP. GraphHopper truck profile provides partial coverage."
      },
      "hos_analysis": {
        "hos_warning": true,
        "remaining_drive_hours": 6.5,
        "route_drive_time_hours": 8.2,
        "overage_hours": 1.7,
        "recommended_reset": {
          "location_name": "Walmart Supercenter - Carlisle, PA",
          "location_type": "okay_break",
          "distance_from_origin_miles": 312,
          "drive_time_to_reset_hours": 5.8,
          "coordinates": [40.2012, -77.1890],
          "post_reset_remaining_miles": 211
        },
        "alternative_resets": []
      },
      "alternatives": [
        {
          "rank": 2,
          "distance_miles": 541,
          "estimated_drive_time_hours": 8.5,
          "confidence_score": 0.94,
          "safety_score": 0.99,
          "preference_score": 0.72,
          "summary": "I-81 corridor, longer but higher confidence data"
        }
      ],
      "error": {
        "code": "GEOCODING_FAILED | NO_SAFE_ROUTE | ENGINE_ERROR",
        "message": "string",
        "failed_input": "string (the specific input that caused failure)",
        "retry_report": {
          "attempts": 5,
          "violations_per_attempt": []
        }
      }
    }

---

## 4. WILL GRAHAM INTEGRATION

### Execution Flow

1. Driver provides trip details to Will Graham (origin, destination, stops, HOS state)
2. Will Graham constructs the MCP tool call with vehicle profile (from stored config) and HOS parameters
3. Will Graham calls generate_truck_safe_route
4. TRIL geocodes all location inputs
5. TRIL generates up to 3 alternative routes via GraphHopper
6. Constraint Engine validates all alternatives (with retry on failure)
7. Preference Engine scores all validated alternatives
8. HOS engine analyzes each route against remaining drive time
9. TRIL returns ranked routes with full analysis to Will Graham
10. Will Graham presents to driver: top route summary, GPX file, safety assessment, HOS recommendation (if applicable), and flags any warnings or low-confidence segments

### Will Graham Response Template

    ROUTE: {origin} -> {destination}
    DISTANCE: {miles} mi | TIME: {hours}h {minutes}m
    CONFIDENCE: {score} | SAFETY: {score}

    [if hos_warning]
    HOS ALERT: Route exceeds remaining drive time by {overage} hours.
    RECOMMENDED RESET: {reset_location} ({reset_type})
      -> {drive_time_to_reset} hours from origin
      -> {post_reset_remaining} miles remaining after reset
    [end]

    [if warnings]
    WARNINGS:
      {warning descriptions}
    [end]

    GPX file ready for Garmin transfer.
    {alternative_count} alternative routes available on request.

---

## 5. VALIDATION SYSTEM (MANDATORY)

### Dual Validation Model

- Pass 1: Routing engine internal constraints (GraphHopper truck profile)
- Pass 2: Independent Constraint Engine (Layer 3) — AUTHORITATIVE

### Rule

If ANY discrepancy exists between Pass 1 and Pass 2: the Constraint Engine verdict prevails. Route is rejected and re-routed per the retry strategy (Section 3.1).

### Validation Logging

Every validation pass is logged with: timestamp, route hash, segment count, violation count, violation details, confidence tier distribution, and pass/fail verdict. Logs are retained for governance audit and preference learning (Phase 2).

---

## 6. RESOURCE AND DEPLOYMENT SPEC

### Hardware Target

Hannibal — MacBook Pro M4 Max

- RAM: Sufficient for GraphHopper in-memory graph
- Storage: Requires approximately 15-20 GB for US OSM extract + GraphHopper graph cache + supplemental data

### MVP Data Scope

For MVP, scope the OSM data extract to the Northeast + Mid-Atlantic + Southeast corridor: Maine to Florida, east of the Mississippi River. This covers Faheem's primary operating territory and reduces graph build time and storage requirements.

Full continental US expansion is Phase 2.

### Deployment Architecture

- GraphHopper: Runs as a local Java process on Hannibal (Docker optional but not required for single-instance deployment)
- TRIL application layer: Python, invoked by OpenClaw as an MCP tool
- Reference data: JSON files in the TRIL project directory, version-controlled via Git
- GPX output: Written to a designated output directory, accessible to Will Graham for delivery

### Resource Allocation

- GraphHopper heap: 8 GB recommended for regional extract
- TRIL Python process: Minimal (< 500 MB)
- Disk: 20 GB reserved for map data, graph cache, and reference datasets

---

## 7. DATA VERSIONING STRATEGY

### OSM Data

- Update cycle: Monthly (download fresh regional extract from Geofabrik)
- GraphHopper graph rebuild required after each OSM update
- Each OSM extract is tagged with download date in the filename
- The system logs which OSM extract version was used for every route generated

### NBI Data

- Update cycle: Annually (NBI publishes annual updates)
- Interim updates applied manually when specific bridge changes are reported

### State DOT Data

- Update cycle: As-needed, manually maintained
- Each update is version-controlled with a changelog entry

### Walmart Okay Break List

- Update cycle: As-needed, based on driver reports and community updates
- Each update is version-controlled

### Staleness Warning

If the OSM data extract is more than 60 days old, the system appends a staleness warning to every route output:

    "data_staleness_warning": "Map data is {N} days old. Consider updating for most current restrictions."

---

## 8. TECH STACK

- Python 3.11+ — control, orchestration, constraint engine, MCP tool interface
- GraphHopper — routing engine (Java, self-hosted)
- Nominatim — geocoding (self-hosted or API)
- OpenStreetMap — primary road network data (Geofabrik regional extracts)
- FHWA NBI — supplemental bridge clearance data
- Docker — optional, for GraphHopper containerization
- GPXpy — GPX file generation (Python library)
- OpenClaw — MCP runtime (Node.js, on Hannibal)
- Git — version control for reference data and configuration

---

## 9. MVP SCOPE

### INCLUDED (Phase 1)

- OSM regional extract ingestion (East of Mississippi)
- GraphHopper setup with custom truck vehicle profile
- NBI bridge clearance data integration
- Geocoding via Nominatim
- Constraint Engine: height, weight, length, HGV prohibition, hazmat
- Axle weight validation (simplified uniform distribution model)
- Data Confidence Model (4-tier classification and scoring)
- Retry strategy with 5-attempt termination
- HOS awareness with reset recommendation (manual input)
- Walmart Okay Break curated dataset
- Preference Engine (static YAML configuration, manual)
- GPX export (Garmin dezl compatible)
- JSON output (full analysis)
- MCP tool interface (generate_truck_safe_route)
- Will Graham integration
- Validation logging
- Data versioning and staleness warnings

### EXCLUDED (Phase 2+)

- Real-time traffic integration
- Weather integration
- Full continental US data scope
- ML-based preference learning
- ELD/HOS automatic integration
- 30-minute break and 70-hour cycle tracking
- Sequence-level turn feasibility validation
- Advanced hazard prediction
- Mobile app or UI of any kind
- Multi-driver profile support

---

## 10. GOVERNANCE PRINCIPLE (NON-NEGOTIABLE)

TRIL is NOT a GPS.
TRIL is NOT a UI.
TRIL is NOT a map application.

TRIL is a governed decision system for route legality, safety, and compliance.

Every route output includes a complete audit trail: data sources used, confidence assessment, constraint validation results, and known limitations. The driver always has the information needed to make an informed decision.

---

## 11. CRITICAL INSIGHTS

### Vehicle Length Changes Everything

Vehicle length is not a secondary constraint. It affects turning radius feasibility, ramp access, urban navigability, and route class viability. If length is not enforced, the system is unsafe and invalid.

### Data Completeness Is the Core Challenge

The routing engine is a solved problem. The constraint data is not. The system's real value — and its real risk — lives in the Data Confidence Model. A routing engine with perfect algorithms and incomplete data produces confidently wrong routes. The confidence scoring system exists to make the boundaries of the system's knowledge explicit to the driver.

### HOS Is a Safety Constraint, Not a Convenience Feature

A route that is physically legal but exceeds the driver's available hours is not a safe route. The system treats HOS as a first-class constraint, not an afterthought, because fatigue kills.

---

## 12. NEXT STEP

This spec is buildable. The next move:

**Option A — BUILD**: Install GraphHopper on Hannibal, load regional OSM extract, stand up Nominatim, generate the first real truck-safe GPX file.

**Option B — HARDEN**: Create Tool Authorization Registry entry for generate_truck_safe_route, define observability metrics, integrate with Continuum governance and Jack Crawford oversight.

**Option C — DATA FIRST**: Start with the Walmart Okay Break list and state DOT restriction overlays — the curated datasets that no routing engine provides out of the box. Build the data foundation before the routing logic.
