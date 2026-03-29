# TRIL

Truck Routing Intelligence Layer scaffold for Will Graham on Hannibal.

## Status

This directory contains an implementation-oriented MVP scaffold aligned to the TRIL blueprint.

Built here:
- config model
- route request / response schemas
- geocoding abstraction
- GraphHopper client abstraction
- constraint engine
- retry / termination flow
- confidence model
- HOS / reset analysis
- hardened JSON / GPX output builders
- validation logging
- reference data catalog / overlay application
- data version / staleness support
- CLI entrypoint
- sample end-to-end harness

## Notes

This scaffold is designed to run with Python standard library only.
External services are abstracted behind adapters so the system can be wired to:
- Nominatim
- GraphHopper
- NBI overlay data
- state DOT overlays

## Layout

- `config.py` — runtime and data configuration
- `models.py` — request/response structures
- `geocoding.py` — geocoder interface + stub implementation
- `routing.py` — routing engine interface + stub GraphHopper client
- `constraints.py` — independent constraint engine
- `confidence.py` — segment tiers + route confidence scoring
- `hos.py` — HOS and reset recommendation logic
- `outputs.py` — canonical JSON / hardened GPX / link output helpers
- `data_layers.py` — NBI + state overlay loading / application
- `logging_utils.py` — audit logging
- `versions.py` — source versioning and staleness checks
- `engine.py` — orchestration flow
- `cli.py` — command-line entrypoint
- `data/` — placeholder reference datasets
- `logs/` — validation log output
- `out/` — generated route outputs
- `examples/run_samples.py` — sample harness for reproducible runs

## CLI quick start

Basic route:

```bash
python3 -m tril.cli S9196 DC6080 --print-summary
```

Route with HOS clocks:

```bash
python3 -m tril.cli S9196 DC6080 \
  --remaining-drive-hours 3.5 \
  --remaining-duty-hours 4.0 \
  --print-summary
```

Write canonical outputs to custom paths:

```bash
python3 -m tril.cli S9196 DC6080 \
  --json-out tril/out/sample.json \
  --gpx-out tril/out/sample.gpx \
  --compact-json
```

## Output behavior

### JSON

- Canonical key ordering for stable diffs and fixtures.
- UTF-8 output with trailing newline in pretty mode.
- Route payload now includes selected candidate id, waypoint list, and segment summary.

### GPX

- XML escaping for route and waypoint names.
- Metadata name/description/timestamp included.
- Route points preserved up to 500 waypoints.
- Track section added for operator-visible segment context.

### HOS

- Reports both drive and duty clocks.
- Includes projected remaining time if the route is run now.
- Adds a concise operator summary string for CLI surfaces.
- Picks a reset recommendation plus alternates when the route would bust clock.

## End-to-end examples

Run the bundled harness:

```bash
python3 tril/examples/run_samples.py
```

That script prints a short pass/fail summary and refreshes fixture outputs under `tril/out/`.
