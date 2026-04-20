import YAML from 'yaml';

const DATA_BASE = '/data';
const WILL_MEMORY_BASE = 'will-memory';
const HAZMAT_MEMORY_BASE = 'hazmat-memory';

async function fetchText(path) {
  try {
    const res = await fetch(`${DATA_BASE}/${path}?t=${Date.now()}`);
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

async function fetchYaml(path) {
  const text = await fetchText(path);
  if (!text) return null;
  try {
    return YAML.parse(text);
  } catch {
    return null;
  }
}

export async function loadActivityLog() {
  const data = await fetchYaml('DAILY_ACTIVITY_LOG.yaml');
  if (!data?.days) return [];
  return data.days.sort((a, b) => new Date(a.date) - new Date(b.date));
}

export async function loadDailyNotes() {
  const data = await fetchYaml('DAILY_NOTES.yaml');
  if (!data?.notes) return [];
  return data.notes;
}

export async function loadStoreDatabase() {
  const data = await fetchYaml('STORE_DATABASE.yaml');
  if (!data?.stores) return [];
  return data.stores;
}

export async function loadVendorDatabase() {
  const data = await fetchYaml('VENDOR_DATABASE.yaml');
  if (!data?.vendors) return [];
  return data.vendors;
}

export async function loadCongestionMemory() {
  const text = await fetchText('WILL_GRAHAM_CONGESTION_MEMORY.md');
  if (!text) return [];
  const entries = [];
  const blocks = text.split(/### CG-/);
  for (let i = 1; i < blocks.length; i++) {
    const block = blocks[i];
    const idMatch = block.match(/^(\d+)/);
    const id = idMatch ? `CG-${idMatch[1]}` : `CG-${i}`;
    const area = block.match(/area:\s*(.+)/)?.[1]?.trim() || 'Unknown';
    const timeWindow = block.match(/time_window:\s*(.+)/)?.[1]?.trim() || 'Variable';
    const impactLevel = block.match(/impact_level:\s*(.+)/)?.[1]?.trim() || 'unknown';
    const dayType = block.match(/day_type:\s*(.+)/)?.[1]?.trim() || 'any';
    const noteLines = [];
    const noteMatches = block.matchAll(/^\s+-\s+(.+)$/gm);
    for (const m of noteMatches) {
      if (!m[1].match(/^(area|day_type|time_window|impact_level|source|last_updated|status):/)) {
        noteLines.push(m[1]);
      }
    }
    entries.push({ id, area, timeWindow, impactLevel, dayType, notes: noteLines });
  }
  return entries;
}

export async function loadFieldLog() {
  const text = await fetchText('WILL_GRAHAM_ROUTE_FIELD_LOG.md');
  if (!text) return [];
  const entries = [];
  const blocks = text.split(/### FN-/);
  for (let i = 1; i < blocks.length; i++) {
    const block = blocks[i];
    const idMatch = block.match(/^(\d+)/);
    const id = idMatch ? `FN-${idMatch[1]}` : `FN-${i}`;
    const dateMatch = block.match(/(\d{4}-\d{2}-\d{2})/);
    const date = dateMatch?.[1] || '';
    const route = block.match(/route:\s*(.+)/)?.[1]?.trim() || '';
    const status = block.match(/status:\s*(.+)/)?.[1]?.trim() || 'PENDING';
    entries.push({ id, date, route, status });
  }
  return entries;
}

export async function loadHeartbeat() {
  const text = await fetchText('HEARTBEAT.md');
  if (!text) return { status: 'UNKNOWN', raw: '' };
  const isTemplate = text.includes('Keep this file empty') || text.trim().length < 50;
  return {
    status: isTemplate ? 'STANDBY' : 'ACTIVE',
    raw: text,
  };
}

async function fetchJson(path) {
  try {
    const res = await fetch(`${DATA_BASE}/${path}?t=${Date.now()}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Get entries belonging to the current trip from the activity log.
 * If the most recent entry has a trip_number, gather all entries with that trip_number.
 * If no trip_number, take the last 5 entries with non-null miles.
 */
export function getCurrentTripEntries(activityLog) {
  if (!activityLog?.length) return [];

  const sorted = [...activityLog].sort((a, b) => new Date(a.date) - new Date(b.date));
  const lastEntry = sorted[sorted.length - 1];

  if (lastEntry.trip_number) {
    return sorted.filter((d) => d.trip_number === lastEntry.trip_number);
  }

  // No trip_number — take the last 5 non-null-miles entries
  const withMiles = sorted.filter((d) => d.miles != null && d.miles > 0);
  return withMiles.slice(-5);
}

export async function loadTripMemory() {
  // Try will-memory JSON system first (graceful fallback if missing)
  const manifest = await fetchJson(`${WILL_MEMORY_BASE}/index.json`);
  if (manifest) {
    // Will-memory exists — use the original logic
    const recentTrips = Array.isArray(manifest.recentTrips)
      ? manifest.recentTrips.filter(Boolean)
      : [];

    let activeTrip = null;
    if (manifest.activeTripNumber) {
      activeTrip = await fetchJson(`${WILL_MEMORY_BASE}/trips/${manifest.activeTripNumber}.json`);
    }

    const activityDays = [];
    if (Array.isArray(manifest.activityDayFiles)) {
      for (const fileName of manifest.activityDayFiles) {
        const day = await fetchJson(`${WILL_MEMORY_BASE}/daily-activities/${fileName}`);
        if (day) activityDays.push(day);
      }
    }

    activityDays.sort((a, b) => new Date(a.date) - new Date(b.date));

    const lastEntry = activityDays[activityDays.length - 1];
    const activeDay = lastEntry || null;
    const previousCompletedDay = activityDays.length >= 2 ? activityDays[activityDays.length - 2] : null;
    const tripMiles = activityDays.reduce((sum, day) => sum + (day.miles || 0), 0);

    return { activeTrip, recentTrips, activityDays, activeDay, previousCompletedDay, tripMiles };
  }

  // Fallback: derive from DAILY_ACTIVITY_LOG.yaml
  const activityLog = await loadActivityLog();
  if (!activityLog.length) {
    return { activeTrip: null, recentTrips: [], activityDays: [], activeDay: null, previousCompletedDay: null, tripMiles: 0 };
  }

  // activeDay: most recent entry in the log regardless of source
  const activeDay = activityLog[activityLog.length - 1] || null;

  // previousCompletedDay: most recent completed entry with miles (day_recap or pay_activity_recap)
  const completedSources = new Set(['day_recap', 'pay_activity_recap']);
  const completedWithMiles = activityLog.filter(
    (d) => completedSources.has(d.source) && d.miles != null && d.miles > 0
  );
  const previousCompletedDay = completedWithMiles.length
    ? completedWithMiles[completedWithMiles.length - 1]
    : null;

  // tripMiles: sum of miles for the current trip
  const tripEntries = getCurrentTripEntries(activityLog);
  const tripMiles = tripEntries.reduce((sum, day) => sum + (day.miles || 0), 0);

  return {
    activeTrip: null,
    recentTrips: [],
    activityDays: activityLog,
    activeDay,
    previousCompletedDay,
    tripMiles,
  };
}

export async function loadHazmatMemory() {
  const manifest = await fetchJson(`${HAZMAT_MEMORY_BASE}/hazmat_case_index.json`);
  if (!manifest) return { activeCase: null, recentCases: [] };

  const recentCases = Array.isArray(manifest.recentCases)
    ? manifest.recentCases.filter(Boolean)
    : [];

  let activeCase = null;
  if (manifest.activeCaseId) {
    activeCase = await fetchJson(`${HAZMAT_MEMORY_BASE}/hazmat-cases/${manifest.activeCaseId}.json`);
  }

  return { activeCase, recentCases };
}

export async function loadAllData() {
  const [activityLog, dailyNotes, stores, vendors, congestion, fieldLog, heartbeat, tripMemory, hazmatMemory] =
    await Promise.all([
      loadActivityLog(),
      loadDailyNotes(),
      loadStoreDatabase(),
      loadVendorDatabase(),
      loadCongestionMemory(),
      loadFieldLog(),
      loadHeartbeat(),
      loadTripMemory(),
      loadHazmatMemory(),
    ]);
  return { activityLog, dailyNotes, stores, vendors, congestion, fieldLog, heartbeat, tripMemory, hazmatMemory };
}
