import { useState, useMemo } from 'react';

const BREAK_COLORS = {
  break: { bg: 'bg-cyber-green/15', text: 'text-cyber-green', border: 'border-cyber-green/30', label: 'BREAK OK' },
  no_break: { bg: 'bg-cyber-red/15', text: 'text-cyber-red', border: 'border-cyber-red/30', label: 'NO BREAK' },
  unknown: { bg: 'bg-gray-500/15', text: 'text-gray-400', border: 'border-gray-500/30', label: 'UNKNOWN' },
};

const TYPE_STYLES = {
  store: { color: 'text-cyber-cyan', bg: 'bg-cyber-cyan/15', border: 'border-cyber-cyan/30', label: 'STORE' },
  dc: { color: 'text-cyber-purple', bg: 'bg-cyber-purple/15', border: 'border-cyber-purple/30', label: 'DC' },
  vendor: { color: 'text-cyber-amber', bg: 'bg-cyber-amber/15', border: 'border-cyber-amber/30', label: 'VENDOR' },
};

function getSiteType(site) {
  if (site._source === 'vendor') return 'vendor';
  if (site.store_id?.startsWith('DC')) return 'dc';
  return 'store';
}

// All DCs are okay breaks — override unknown/missing break_status for DC sites
function resolveBreakStatus(site) {
  if (site._source === 'vendor') return site.break_status || 'unknown';
  if (site.store_id?.startsWith('DC')) return 'break';
  return site.break_status || 'unknown';
}

function getSiteId(site) {
  return site._source === 'vendor' ? site.vendor_id : site.store_id;
}

function normalizeSites(stores, vendors) {
  const normalized = [];
  if (stores?.length) {
    for (const s of stores) {
      normalized.push({ ...s, _source: 'store', _id: s.store_id });
    }
  }
  if (vendors?.length) {
    for (const v of vendors) {
      normalized.push({ ...v, _source: 'vendor', _id: v.vendor_id });
    }
  }
  return normalized;
}

function filterSites(sites, query) {
  if (!query) return sites;
  const q = query.toLowerCase();
  return sites.filter((site) => {
    const id = getSiteId(site) || '';
    const name = site.name || '';
    const city = site.location?.city || '';
    const state = site.location?.state || '';
    const address = site.location?.address || '';
    return (
      id.toLowerCase().includes(q) ||
      name.toLowerCase().includes(q) ||
      city.toLowerCase().includes(q) ||
      state.toLowerCase().includes(q) ||
      address.toLowerCase().includes(q)
    );
  });
}

function prioritizeCurrentTripSites(sites, tripMemory) {
  const activeTrip = tripMemory?.activeTrip;
  const stopIds = new Set(activeTrip?.stops || []);
  if (!stopIds.size) return sites;

  const prioritized = [...sites].sort((a, b) => {
    const aId = getSiteId(a);
    const bId = getSiteId(b);
    const aMatch = stopIds.has(aId) ? 1 : 0;
    const bMatch = stopIds.has(bId) ? 1 : 0;
    if (aMatch !== bMatch) return bMatch - aMatch;
    return String(aId).localeCompare(String(bId));
  });

  return prioritized;
}

function DetailRow({ label, value }) {
  if (!value) return null;
  return (
    <div style={{ display: 'flex', gap: 8, padding: '2px 0' }}>
      <span className="text-gray-500" style={{ fontSize: '0.55rem', minWidth: 64, flexShrink: 0, letterSpacing: '0.05em' }}>
        {label}
      </span>
      <span className="text-gray-300" style={{ fontSize: '0.6rem', lineHeight: 1.5 }}>
        {value}
      </span>
    </div>
  );
}

function SiteCard({ site, isExpanded, onToggle }) {
  const siteType = getSiteType(site);
  const typeStyle = TYPE_STYLES[siteType];
  const siteId = getSiteId(site);
  const breakStyle = site._source !== 'vendor'
    ? BREAK_COLORS[resolveBreakStatus(site)] || BREAK_COLORS.unknown
    : null;

  const city = site.location?.city || '';
  const state = site.location?.state || '';
  const loc = [city, state].filter(Boolean).join(', ');

  const stringNotes = (site.notes || []).filter((n) => typeof n === 'string');
  const phone = stringNotes.find((n) => n.startsWith('Phone:'))?.replace('Phone: ', '');
  const displayNotes = stringNotes.filter((n) => !n.startsWith('Phone:'));
  const address = site.location?.address;
  const lastUpdated = site.last_updated
    ? new Date(site.last_updated).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : null;

  return (
    <div
      className="bg-surface-light/40 border border-panel-border rounded cursor-pointer hover:border-cyber-cyan/40 transition-colors"
      onClick={onToggle}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px' }}>
        <span className={`badge ${typeStyle.bg} ${typeStyle.color} border ${typeStyle.border}`}>
          {typeStyle.label}
        </span>
        <span className={`text-xs font-bold ${typeStyle.color}`} style={{ minWidth: 48 }}>
          {siteId}
        </span>
        <span className="text-xs text-gray-500 flex-1 truncate">
          click for details
        </span>
        {breakStyle && (
          <span className={`badge ${breakStyle.bg} ${breakStyle.text} border ${breakStyle.border}`}>
            {breakStyle.label}
          </span>
        )}
        <svg
          width="12" height="12" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          className="text-gray-500 flex-shrink-0"
          style={{
            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease',
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {isExpanded && (
        <div style={{ padding: '0 12px 10px', borderTop: '1px solid rgba(0, 240, 255, 0.1)', paddingTop: 10 }}>
          {/* Detail fields */}
          {site.name && loc && <DetailRow label="LOCATION" value={loc} />}
          {!site.name && !loc ? null : null}
          {address && <DetailRow label="ADDRESS" value={address} />}
          {phone && <DetailRow label="PHONE" value={phone} />}
          {site.store_type && <DetailRow label="TYPE" value={site.store_type.replace(/_/g, ' ')} />}
          {site.vendor_type && <DetailRow label="TYPE" value={site.vendor_type.replace(/_/g, ' ')} />}
          {lastUpdated && <DetailRow label="UPDATED" value={lastUpdated} />}

          {/* Notes */}
          {displayNotes.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div className="text-gray-500" style={{ fontSize: '0.55rem', letterSpacing: '0.05em', marginBottom: 4 }}>
                NOTES
              </div>
              {displayNotes.map((note, i) => (
                <div
                  key={i}
                  className="text-gray-300"
                  style={{
                    fontSize: '0.6rem',
                    lineHeight: 1.6,
                    padding: '3px 0 3px 10px',
                    borderLeft: '2px solid rgba(0, 240, 255, 0.15)',
                    marginBottom: 2,
                  }}
                >
                  {note}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function StoreIntel({ stores, vendors, tripMemory }) {
  const [expanded, setExpanded] = useState(null);
  const [search, setSearch] = useState('');

  const allSites = useMemo(() => normalizeSites(stores, vendors), [stores, vendors]);
  const filtered = useMemo(() => {
    const visible = filterSites(allSites, search);
    return prioritizeCurrentTripSites(visible, tripMemory);
  }, [allSites, search, tripMemory]);

  return (
    <div className="panel corner-accents h-full flex flex-col">
      <div className="panel-title flex items-center justify-between">
        <span>Site Intelligence</span>
        <span className="text-[0.55rem] text-gray-500 tracking-normal normal-case font-normal">
          {filtered.length}{filtered.length !== allSites.length ? ` / ${allSites.length}` : ''} sites
        </span>
      </div>

      {/* Search bar */}
      <div style={{ padding: '8px 8px 4px' }}>
        <input
          type="text"
          placeholder="Search by ID, name, city, state..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: '100%',
            background: 'rgba(10, 18, 30, 0.6)',
            border: '1px solid rgba(0, 240, 255, 0.2)',
            borderRadius: 3,
            padding: '6px 10px',
            fontSize: '0.65rem',
            color: '#e0e8f0',
            outline: 'none',
            letterSpacing: '0.03em',
            boxSizing: 'border-box',
          }}
          onFocus={(e) => { e.target.style.borderColor = 'rgba(0, 240, 255, 0.5)'; }}
          onBlur={(e) => { e.target.style.borderColor = 'rgba(0, 240, 255, 0.2)'; }}
        />
      </div>

      {/* Site list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5" style={{ maxHeight: 340 }}>
        {filtered.length === 0 ? (
          <div className="text-gray-500 text-xs p-2">No matching sites</div>
        ) : (
          filtered.map((site) => {
            const id = site._id;
            return (
              <SiteCard
                key={id}
                site={site}
                isExpanded={expanded === id}
                onToggle={() => setExpanded(expanded === id ? null : id)}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
