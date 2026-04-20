import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { getCurrentTripEntries } from '../utils/dataLoader';

const TRACKED_TIME_TYPES = {
  WT_hours: { label: 'Wait Time', color: '#ff3b3b' },
  BD_hours: { label: 'Break Down', color: '#ff6b35' },
  RC_hours: { label: 'Road Closure', color: '#00f0ff' },
  WE_hours: { label: 'Weather', color: '#6366f1' },
  TS_hours: { label: 'Training & Surveys', color: '#ffbf00' },
};

export default function TrackedTimePanel({ activityLog }) {
  if (!activityLog?.length) {
    return (
      <div className="panel corner-accents h-full">
        <div className="panel-title">Tracked Time Events</div>
        <div className="p-4 text-gray-500 text-xs">No data</div>
      </div>
    );
  }

  // Use current trip entries instead of last 7 days
  const tripEntries = getCurrentTripEntries(activityLog);

  // Aggregate by date
  const byDate = {};
  for (const day of tripEntries) {
    const d = day.date;
    if (!byDate[d]) byDate[d] = { date: d, activities: {} };
    const acts = day.activities || {};
    for (const key of Object.keys(TRACKED_TIME_TYPES)) {
      byDate[d].activities[key] = (byDate[d].activities[key] || 0) + (acts[key] || 0);
    }
  }

  const sorted = Object.values(byDate).sort((a, b) => new Date(a.date) - new Date(b.date));

  // Sum across trip days
  const totals = {};
  let grandTotal = 0;
  for (const day of sorted) {
    for (const [key, val] of Object.entries(day.activities)) {
      totals[key] = (totals[key] || 0) + val;
      grandTotal += val;
    }
  }

  const pieData = Object.entries(TRACKED_TIME_TYPES)
    .filter(([key]) => (totals[key] || 0) > 0)
    .map(([key, meta]) => ({
      name: meta.label,
      value: Math.round((totals[key] || 0) * 100) / 100,
      color: meta.color,
    }));

  // Days with >1 hour wait time
  const highWaitDays = sorted.filter((d) => (d.activities.WT_hours || 0) > 1);

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-surface border border-panel-border rounded p-2 text-xs">
        <div style={{ color: payload[0].payload.color }} className="font-bold">
          {payload[0].name}: {payload[0].value}h
        </div>
      </div>
    );
  };

  return (
    <div className="panel corner-accents h-full">
      <div className="panel-title">Tracked Time Events — Trip</div>
      <div className="p-4">
        {pieData.length === 0 ? (
          <div className="text-center text-gray-500 text-xs py-8">No tracked time events this trip</div>
        ) : (
          <div className="flex items-center gap-4">
            <div className="w-[140px] h-[140px]">
              <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={35}
                    outerRadius={60}
                    paddingAngle={3}
                    dataKey="value"
                    stroke="none"
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 space-y-1.5">
              {pieData.map((d) => (
                <div key={d.name} className="flex items-center gap-2 text-xs">
                  <div className="w-2 h-2 rounded-full" style={{ background: d.color }} />
                  <span className="text-gray-400 flex-1">{d.name}</span>
                  <span className="text-gray-200 font-bold">{d.value}h</span>
                </div>
              ))}
              <div className="border-t border-panel-border pt-1.5 mt-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-400">Total</span>
                  <span className="text-cyber-cyan font-bold">{grandTotal.toFixed(1)}h</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {highWaitDays.length > 0 && (
          <div className="mt-3 pt-3 border-t border-panel-border">
            <div className="text-[0.55rem] text-cyber-red tracking-wider mb-1 glow-red">
              HIGH WAIT DAYS ({'>'}1h)
            </div>
            {highWaitDays.map((d) => (
              <div key={d.date} className="flex items-center justify-between text-xs py-0.5">
                <span className="text-gray-400">{d.date}</span>
                <span className="text-cyber-red font-bold">{d.activities.WT_hours?.toFixed(1)}h</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
