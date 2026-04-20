const ACTIVITY_ICONS = {
  HK: { label: 'Hooks', icon: '⛓', color: 'text-cyber-cyan' },
  AD: { label: 'Arrive Drops', icon: '📋', color: 'text-cyber-amber' },
  LL: { label: 'Live Loads', icon: '📦', color: 'text-blue-400' },
  LU: { label: 'Live Unloads', icon: '📤', color: 'text-cyber-green' },
  LO: { label: 'Lay Overs', icon: '🛏️', color: 'text-cyber-red' },
};

const TIME_ACTIVITIES = {
  WT_hours: { label: 'Wait Time', color: 'bg-cyber-red' },
  BD_hours: { label: 'Break Down', color: 'bg-red-600' },
  RC_hours: { label: 'Road Closure', color: 'bg-blue-600' },
  WE_hours: { label: 'Weather', color: 'bg-indigo-600' },
  TS_hours: { label: 'Training & Surveys', color: 'bg-cyber-amber' },
};

export default function ActivitySummary({ tripMemory }) {
  const latest = tripMemory?.activeDay;
  const previousCompletedDay = tripMemory?.previousCompletedDay;
  if (!latest && !previousCompletedDay) {
    return (
      <div className="panel corner-accents h-full">
        <div className="panel-title">Activity Summary</div>
        <div className="p-4 text-gray-500 text-xs">No data</div>
      </div>
    );
  }

  const acts = latest?.activities || {};
  const tripMiles = tripMemory?.tripMiles || 0;

  // Collect non-zero timed activities
  const timedActivities = Object.entries(TIME_ACTIVITIES)
    .map(([key, meta]) => ({ ...meta, hours: acts[key] || 0, key }))
    .filter((t) => t.hours > 0);

  const maxTimedHours = Math.max(...timedActivities.map((t) => t.hours), 1);

  return (
    <div className="panel corner-accents h-full">
      <div className="panel-title flex items-center justify-between">
        <span>Activity Summary</span>
        <span className="text-[0.6rem] text-gray-500 tracking-normal normal-case font-normal">
          {latest?.date || previousCompletedDay?.date || '—'}
        </span>
      </div>

      <div className="p-4">
        {/* Activity count cards */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          {Object.entries(ACTIVITY_ICONS).map(([key, meta]) => (
            <div
              key={key}
              className="bg-surface-light/60 border border-panel-border rounded p-3 text-center"
            >
              <div className="text-lg mb-1">{meta.icon}</div>
              <div className={`text-2xl font-bold ${meta.color}`}>
                {acts[key] || 0}
              </div>
              <div className="text-[0.55rem] text-gray-500 tracking-wider mt-1">
                {meta.label.toUpperCase()}
              </div>
            </div>
          ))}
        </div>

        {/* Miles */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div className="flex items-center justify-between bg-surface-light/40 border border-panel-border rounded p-3">
            <span className="text-xs text-gray-400 tracking-wider">PREVIOUS DAY MILES</span>
            <span className="text-xl font-bold text-cyber-green glow-green">
              {previousCompletedDay?.miles || '—'}
            </span>
          </div>
          <div className="flex items-center justify-between bg-surface-light/40 border border-panel-border rounded p-3">
            <span className="text-xs text-gray-400 tracking-wider">WORK WEEK MILES</span>
            <span className="text-xl font-bold text-cyber-cyan glow-cyan">
              {tripMiles || '—'}
            </span>
          </div>
        </div>

        {/* Timed activities bars */}
        {timedActivities.length > 0 && (
          <div className="space-y-2">
            <div className="text-[0.55rem] text-gray-500 tracking-wider mb-1">TIMED ACTIVITIES</div>
            {timedActivities.map((t) => (
              <div key={t.key} className="flex items-center gap-2">
                <span className="text-[0.6rem] text-gray-400 w-20 text-right">{t.label}</span>
                <div className="flex-1 bg-surface-light rounded-full h-3 overflow-hidden">
                  <div
                    className={`h-full ${t.color} rounded-full transition-all`}
                    style={{ width: `${Math.max((t.hours / maxTimedHours) * 100, 8)}%` }}
                  />
                </div>
                <span className="text-[0.6rem] text-gray-300 w-12">{t.hours.toFixed(1)}h</span>
              </div>
            ))}
          </div>
        )}

        {/* Source */}
        <div className="mt-3 text-[0.5rem] text-gray-600 text-right tracking-wider">
          SRC: {latest?.source?.toUpperCase().replace(/_/g, ' ') || 'DAILY LOG'}
        </div>
      </div>
    </div>
  );
}
