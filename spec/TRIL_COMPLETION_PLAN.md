# TRIL COMPLETION PLAN — Path to MVP

Date: 2026-03-29
Target: Operational truck-safe routing on Hannibal for Will Graham

## Overview

This plan closes all gaps required for MVP deployment of TRIL. Tasks are organized in dependency order across 5 waves, with each wave having a clear validation gate before proceeding.

Total Estimated Duration: **8-10 days** of focused development

---

## WAVE 1 — Safety and Correctness (Days 1-2)

**Goal**: Fix the service switching mechanism so the system can use real or stub services based on configuration.

### Task 1.1: Implement Service Mode Switching
**Files**: `tril/engine.py`
**Changes**:
- Modify `TRILEngine.__init__()` to check `config.services.geocoder_mode` and `router_mode`
- If mode == "nominatim", instantiate NominatimGeocoder
- If mode == "graphhopper", instantiate GraphHopperLocalClient
- Keep stub services as fallback when mode == "stub"
**Verifies**: GAP-003
**Test**: Set env vars and confirm correct service instantiation
**Dependencies**: None

### Task 1.2: Add Walmart Reset Data Integration
**Files**: `tril/hos.py`
**Changes**:
- Load `walmart_okay_breaks.json` in HOS module
- Replace hardcoded RESET_CANDIDATES with data from JSON
- Implement location filtering by distance from route
**Verifies**: GAP-008
**Test**: HOS eval tests should find appropriate Walmart resets
**Dependencies**: None

### Task 1.3: Load Driver Preferences from YAML
**Files**: `tril/config.py`, create `tril/data/driver_preferences.yaml`
**Changes**:
- Create YAML file with avoid_zones, preferred_corridors, preferred_stops
- Add preference loading method to TRILConfig
- Override hardcoded defaults with YAML values if file exists
**Verifies**: GAP-010
**Test**: Preference scoring reflects loaded configuration
**Dependencies**: None

**VALIDATION GATE**: Run eval harness. All currently passing tests must still pass. Service switching must be proven to work.

---

## WAVE 2 — Spec Compliance (Days 3-4)

**Goal**: Ensure all interfaces match specification exactly, preparing for integration.

### Task 2.1: Create MCP Tool Wrapper
**Files**: Create `tril/mcp_tool.py`
**Changes**:
- Implement `generate_truck_safe_route` function matching spec interface
- Convert MCP input format to RouteRequest
- Convert RouteResult to MCP output format
- Handle all error cases with proper MCP error responses
**Verifies**: GAP-005
**Test**: Call tool with various inputs, verify output schema
**Dependencies**: Task 1.1

### Task 2.2: Add Deployment Configuration
**Files**: Create `tril/deployment/README.md`, `tril/deployment/config.env.example`
**Changes**:
- Document all environment variables
- Provide example configuration for Hannibal
- Include systemd service files for GraphHopper and Nominatim
- Add startup validation checklist
**Verifies**: Documentation for GAP-006, GAP-007
**Test**: Follow documentation to configure services
**Dependencies**: None

### Task 2.3: Improve Constraint Test Data
**Files**: `tril/routing.py` (StubGraphHopperClient)
**Changes**:
- Add realistic constraint values to stub segments
- Include segments that violate common constraints
- Add variety of confidence tiers to stub routes
**Verifies**: Enables testing of GAP-001, GAP-002
**Test**: Constraint Enforcement eval tests improve scores
**Dependencies**: None

**VALIDATION GATE**: MCP tool can be called with spec-compliant interface. Stub mode Constraint Enforcement tests achieve >50% pass rate.

---

## WAVE 3 — Live Infrastructure (Days 5-7)

**Goal**: Deploy and integrate real routing and geocoding services.

### Task 3.1: Deploy GraphHopper on Hannibal
**Files**: System deployment, not code
**Changes**:
- Install Java runtime
- Download GraphHopper 
- Configure for truck profile
- Start service on port 8989
- Verify health endpoint
**Verifies**: GAP-006
**Test**: curl http://localhost:8989/health returns 200
**Dependencies**: None

### Task 3.2: Ingest OSM Data into GraphHopper
**Files**: Create `tril/scripts/ingest_osm.sh`
**Changes**:
- Download regional OSM extract from Geofabrik
- Import into GraphHopper with truck profile
- Build routing graph
- Verify graph statistics
**Verifies**: GAP-004
**Test**: GraphHopper reports correct region coverage
**Dependencies**: Task 3.1

### Task 3.3: Deploy Nominatim on Hannibal
**Files**: System deployment
**Changes**:
- Install Nominatim or use Docker container
- Import same regional OSM extract
- Configure for local queries only
- Start service on port 8080
**Verifies**: GAP-007
**Test**: Geocode "Tobyhanna, PA" returns correct coordinates
**Dependencies**: Task 3.2 (same OSM data)

### Task 3.4: Test Live Service Integration
**Files**: Create `tril/scripts/smoke_test.py`
**Changes**:
- Set environment variables for live services
- Run a test route request
- Verify real segments with constraint data
- Check confidence tiers are realistic
**Verifies**: GAP-001, GAP-002, GAP-003 working together
**Test**: Generate route with actual road segments
**Dependencies**: Tasks 3.1, 3.2, 3.3, 1.1

### Task 3.5: Validate Real Constraint Enforcement
**Files**: `tril/eval_harness.py`
**Changes**:
- Add test cases with known real-world constraints
- Test route between locations with known low bridges
- Test route with actual weight-restricted roads
**Verifies**: GAP-009 (retry logic with real violations)
**Test**: Constraint Enforcement eval tests achieve 100% pass rate
**Dependencies**: Task 3.4

**VALIDATION GATE**: Live services operational. Constraint Enforcement evaluation achieves 100% pass rate with real data.

---

## WAVE 4 — Integration (Days 8-9)

**Goal**: Connect TRIL to Will Graham agent and Continuum governance.

### Task 4.1: Register MCP Tool with OpenClaw
**Files**: Update OpenClaw configuration (outside TRIL)
**Changes**:
- Add generate_truck_safe_route to MCP server configuration
- Point to tril.mcp_tool module
- Configure tool permissions and rate limits
**Verifies**: GAP-005 deployment
**Test**: Will Graham can discover and call the tool
**Dependencies**: Task 2.1

### Task 4.2: Create Will Graham Integration Test
**Files**: Create `tril/tests/will_graham_integration.py`
**Changes**:
- Simulate Will Graham calling MCP tool
- Test various vehicle profiles and HOS states
- Verify response format matches Will Graham's parser
- Test error handling for invalid inputs
**Verifies**: Section 4 (Will Graham Integration)
**Test**: End-to-end flow from Will Graham to GPX output
**Dependencies**: Task 4.1

### Task 4.3: Add Continuum Governance Hooks
**Files**: `tril/logging_utils.py`, `tril/engine.py`
**Changes**:
- Add Continuum trace headers to audit logs
- Implement rate limiting checks
- Add cost tracking metadata
- Report to Continuum metrics endpoint
**Verifies**: Governance integration
**Test**: Routes generate appropriate audit trails
**Dependencies**: None

### Task 4.4: Production Configuration
**Files**: `tril/config.py`, create `tril/data/production.yaml`
**Changes**:
- Set production defaults (real services, strict validation)
- Configure production logging levels
- Set appropriate timeouts and retries
- Lock down file permissions
**Verifies**: Production readiness
**Test**: System runs with production configuration
**Dependencies**: Tasks 3.1-3.5

**VALIDATION GATE**: Will Graham successfully generates truck-safe route via MCP tool. Audit logs capture complete governance trail.

---

## WAVE 5 — Hardening (Day 10)

**Goal**: Ensure system reliability and observability.

### Task 5.1: Add Health Check Endpoints
**Files**: Create `tril/health.py`
**Changes**:
- Check GraphHopper connectivity
- Check Nominatim connectivity
- Verify reference data freshness
- Return aggregated health status
**Verifies**: GAP-012
**Test**: Health endpoint accurately reflects service state
**Dependencies**: Wave 3 completion

### Task 5.2: Implement Timeout and Retry Logic
**Files**: `tril/geocoding.py`, `tril/routing.py`
**Changes**:
- Add configurable timeouts to all external calls
- Implement exponential backoff for transient failures
- Add circuit breaker for repeated failures
- Log all retry attempts
**Verifies**: GAP-013
**Test**: System handles service timeouts gracefully
**Dependencies**: None

### Task 5.3: Add Operational Metrics
**Files**: Create `tril/metrics.py`
**Changes**:
- Count successful/failed routes
- Track response times
- Monitor constraint violation rates
- Track confidence score distribution
**Verifies**: Observability
**Test**: Metrics accurately reflect system behavior
**Dependencies**: None

### Task 5.4: Create Runbook
**Files**: Create `tril/docs/RUNBOOK.md`
**Changes**:
- Startup procedures
- Shutdown procedures
- Common troubleshooting steps
- Data refresh procedures
- Emergency fallback to stub mode
**Verifies**: Operational readiness
**Test**: Operators can follow runbook successfully
**Dependencies**: All previous tasks

### Task 5.5: Final Validation Suite
**Files**: `tril/eval_harness.py`, create `tril/tests/production_validation.py`
**Changes**:
- Add 50+ real-world test cases
- Include edge cases from Faheem's actual routes
- Test all vehicle configurations
- Verify all constraint types
**Verifies**: System correctness
**Test**: 100% pass rate on all categories
**Dependencies**: All previous tasks

**VALIDATION GATE**: All evaluation categories achieve 100% pass rate. Health checks confirm all services operational. Runbook validated by dry run.

---

## Success Criteria for MVP

1. ✅ Constraint Enforcement eval: 100% pass rate
2. ✅ HOS Analysis eval: 100% pass rate  
3. ✅ Live GraphHopper generating real routes
4. ✅ Live Nominatim geocoding arbitrary addresses
5. ✅ Will Graham successfully calls generate_truck_safe_route
6. ✅ GPX files load correctly on Garmin dezl
7. ✅ Audit logs capture full validation trail
8. ✅ System handles service failures gracefully
9. ✅ Reference data less than 60 days old
10. ✅ Runbook enables operator to maintain system

## Risk Mitigations

**Risk**: GraphHopper performs poorly with large graph
- **Mitigation**: Start with smaller Northeast region, expand after validation

**Risk**: Real-world constraints more complex than expected  
- **Mitigation**: Constraint Engine is extensible, can add new validation rules

**Risk**: Nominatim geocoding ambiguous
- **Mitigation**: Expand curated locations, add geocoding confidence thresholds

**Risk**: Integration with Will Graham fails
- **Mitigation**: MCP interface fully specified, can debug with mock agent

## Timeline Summary

- **Days 1-2**: Safety fixes and compliance updates (Wave 1)
- **Days 3-4**: Interface compliance and documentation (Wave 2)  
- **Days 5-7**: Infrastructure deployment and validation (Wave 3)
- **Days 8-9**: Integration with Will Graham (Wave 4)
- **Day 10**: Hardening and final validation (Wave 5)

**Total Duration**: 10 days to production-ready MVP

## Next Action

**START WITH**: Task 1.1 (Service Mode Switching)

This is the keystone change that enables all subsequent testing and validation. Once services can be switched between stub and live modes, the entire system becomes testable and deployable.

## Conclusion

TRIL is a well-architected system that needs infrastructure deployment more than code changes. The Constraint Engine is solid, the data model is complete, and the validation system is robust. 

The critical path is clear: Deploy services → Ingest data → Validate safety → Integrate with Will Graham → Harden for production.

With focused execution, TRIL can be protecting Faheem on the roads within 10 days.