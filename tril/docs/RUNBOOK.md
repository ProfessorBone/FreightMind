# TRIL Operational Runbook

Host: Hannibal (MacBook Pro M4 Max)
Services: GraphHopper :8989, Nominatim :8080
Workspace: `~/.openclaw/agents/jack-crawford/workspace/tril/`

---

## 1. Startup

### 1a. Verify services are running

```bash
curl -s http://127.0.0.1:8989/health    # expect: OK
curl -s "http://127.0.0.1:8080/search?q=Tobyhanna+PA&format=jsonv2&limit=1" | python3 -m json.tool  # expect: results
```

### 1b. Run health check

```bash
cd ~/.openclaw/agents/jack-crawford/workspace
TRIL_GEOCODER_MODE=nominatim TRIL_ROUTER_MODE=graphhopper python3 -m tril.health
```

All three checks (graphhopper, nominatim, reference_data) should report `healthy`.

### 1c. Run smoke test

```bash
TRIL_GEOCODER_MODE=nominatim TRIL_ROUTER_MODE=graphhopper python3 -m tril.tests.will_graham_integration --live
```

All 11 tests should pass.

### 1d. Start MCP server (if not auto-managed by OpenClaw)

The MCP server is normally launched automatically by OpenClaw when Will Graham calls the tool. For manual testing:

```bash
TRIL_GEOCODER_MODE=nominatim TRIL_ROUTER_MODE=graphhopper python3 -m tril.mcp_server
```

---

## 2. Shutdown

### 2a. Graceful

The MCP server process exits when the client disconnects. No special shutdown needed.

### 2b. Force stop

```bash
pkill -f "python3 -m tril.mcp_server"
```

GraphHopper and Nominatim are separate services — stop them independently if needed.

---

## 3. Emergency Fallback to Stub Mode

If live services are down and Faheem needs routing now:

```bash
export TRIL_GEOCODER_MODE=stub
export TRIL_ROUTER_MODE=stub
```

Or edit `~/.openclaw/openclaw.json` → `tools.mcpServers.tril.env`:

```json
"TRIL_GEOCODER_MODE": "stub",
"TRIL_ROUTER_MODE": "stub"
```

Stub mode uses curated locations only (S9196, DC6080, Tobyhanna PA, Johnstown NY). Routes are deterministic approximations, not real road data.

**Restore live mode** by setting values back to `nominatim` / `graphhopper`.

---

## 4. Troubleshooting

### GraphHopper returns 500 or no paths

1. Check GraphHopper logs: `journalctl -u graphhopper` or container logs
2. Verify the graph was built: check for `graph-cache/` directory in GH data dir
3. Test directly: `curl -X POST http://127.0.0.1:8989/route -H 'Content-Type: application/json' -d '{"profile":"truck","points":[[-75.4174,41.177],[-77.189,40.2]],"points_encoded":false}'`
4. If graph is corrupt, rebuild: re-run the OSM ingest script

### Nominatim returns empty results

1. Check Nominatim is accepting connections: `curl http://127.0.0.1:8080/status`
2. Verify import completed: check for presence of data in Nominatim DB
3. Try a known query: `curl "http://127.0.0.1:8080/search?q=Pennsylvania&format=jsonv2&limit=1"`
4. If the import is incomplete, re-import the OSM extract

### Circuit breaker tripped

If logs show "Circuit breaker open", the service has failed 5+ times consecutively. The breaker resets after 30 seconds. Check the underlying service health.

### Rate limited

If logs show "RATE_LIMITED", the system received 60+ requests in 60 seconds. This is protective — wait for the window to clear. Adjust limits via `TRIL_RATE_LIMIT_MAX` and `TRIL_RATE_LIMIT_WINDOW` env vars.

### Geocoding returns low confidence

Nominatim may return ambiguous results. Check:
- Is the query specific enough? ("Tobyhanna, PA" > "Tobyhanna")
- Is the country code filter working? (bounded to US)
- Consider adding the location to curated locations in `geocoding.py`

### Stale reference data warning

If health check shows `degraded` for reference_data:
1. Check `tril/data/nbi_bridges.json` and `tril/data/state_overlays.json`
2. Compare `published_at` dates to today — stale if older than threshold
3. Refresh by updating the data files and their version metadata

---

## 5. Data Refresh

### OSM extract

1. Download fresh extract from Geofabrik: `https://download.geofabrik.de/north-america/us/`
2. Re-import into GraphHopper (rebuild graph)
3. Re-import into Nominatim
4. Update `osm_extract_date` in `tril/config.py` → `DataVersions`

### NBI bridge data

1. Source: National Bridge Inventory or curated subset
2. Replace `tril/data/nbi_bridges.json`
3. Update version string in `DataVersions`

### State overlays

1. Replace `tril/data/state_overlays.json`
2. Update version string in `DataVersions`

After any data refresh, run the full eval harness:

```bash
python3 -m tril.eval_harness
```

---

## 6. Monitoring

### Check metrics

```python
from tril.metrics import metrics
import json
print(json.dumps(metrics.snapshot(), indent=2))
```

### Review audit logs

```bash
tail -5 tril/logs/validation.jsonl | python3 -m json.tool
```

Each log entry contains:
- `continuum.x-continuum-trace-id` — trace ID for this request
- `cost.elapsed_seconds` — wall clock time
- `cost.geocode_api_calls` / `cost.route_api_calls` — API call counts

### Review metrics log

```bash
tail -1 tril/logs/metrics.jsonl | python3 -m json.tool
```

---

## 7. Configuration Reference

| Env Var | Default | Description |
|---------|---------|-------------|
| `TRIL_GEOCODER_MODE` | `stub` | `stub` or `nominatim` |
| `TRIL_ROUTER_MODE` | `stub` | `stub` or `graphhopper` |
| `TRIL_NOMINATIM_URL` | `http://127.0.0.1:8080` | Nominatim endpoint |
| `TRIL_GRAPHHOPPER_URL` | `http://127.0.0.1:8989` | GraphHopper endpoint |
| `TRIL_GRAPHHOPPER_PROFILE` | `truck` | GH routing profile |
| `TRIL_HTTP_TIMEOUT` | `12` | Request timeout (seconds) |
| `TRIL_HTTP_USER_AGENT` | `TRIL/0.1 ...` | HTTP User-Agent header |
| `TRIL_RATE_LIMIT_MAX` | `60` | Max requests per window |
| `TRIL_RATE_LIMIT_WINDOW` | `60` | Rate limit window (seconds) |
| `TRIL_PRODUCTION_MODE` | `false` | Load production.yaml overrides |
| `CONTINUUM_NODE` | `hannibal-edge` | Node name in audit logs |
