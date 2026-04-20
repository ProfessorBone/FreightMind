# WILL_GRAHAM_CONGESTION_MEMORY.md

Congestion Seed Memory — Will Graham

- Host: Hannibal
- Runtime: OpenClaw
- Governing Agent: Jack Crawford
- Operator: Faheem
- Version: 1.0.0
- Status: ACTIVE
- Priority: P1

---

## Purpose

This file stores recurring congestion and route-friction observations for use in route intelligence.

These are operational observations, not universal truth.

---

## Seed Observations

### CG-001
- area: Philadelphia corridors
- day_type: weekday
- time_window: 14:30-17:30
- impact_level: high
- notes:
  - Philly weekday afternoon should be treated as a materially different routing context.
  - A route that looks shorter on paper may be worse for a tractor-trailer during this window.

### CG-002
- area: dense urban / small-city street approaches
- day_type: any
- time_window: variable
- impact_level: medium_to_high
- notes:
  - Short city-street connectors often create stop-and-go friction disproportionate to the nominal mileage saved.
  - For Faheem's truck profile, big-road preference should usually win unless there is a strong reason otherwise.

### CG-003
- area: North Jersey urban approach zones
- day_type: weekday
- time_window: business hours
- impact_level: medium_to_high
- notes:
  - Treat urban North Jersey approaches as likely friction zones until more specific route memory is populated.

---

### CG-004
- area: I-476 South → I-76 East through Philadelphia metro
- day_type: weekday
- time_window: 07:00-09:30, 15:00-18:30
- impact_level: high
- notes:
  - This corridor is the primary route from I-78 East to South New Jersey.
  - Consistently painful during morning and evening commute windows.
  - No operator-identified bypass exists yet for this stretch.
  - Will Graham should surface a congestion warning any time this route is recommended during weekday peak windows.
  - Flag: no_bypass_identified — route intelligence on this corridor is still developing.
- source: operator_memory
- last_updated: 2026-03-28

### CG-005
- area: US Route 1 & 9 (NJ, near I-78 junction)
- day_type: any
- time_window: all hours
- impact_level: high
- notes:
  - US 1 & 9 is structurally congested — not just a peak-hour problem.
  - Heavy red lights, stop-and-go traffic, not operationally suitable for a tractor-trailer.
  - GPS frequently routes through this segment from I-78 East toward Linden, NJ area.
  - Operator always overrides to I-95 NJ Turnpike South instead.
  - Treat any GPS route through US 1 & 9 in this zone as a red flag regardless of time of day.
- source: operator_memory
- last_updated: 2026-03-28

## Next Population Targets

Priority additions:
- named Philly segments
- named North Jersey segments
- weekday vs weekend differences
- known painful approach roads
- congestion notes tied to specific stores/vendors
