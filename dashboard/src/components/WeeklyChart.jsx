import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Line, ComposedChart,
} from 'recharts';
import { getCurrentTripEntries } from '../utils/dataLoader';

export default function WeeklyChart({ activityLog }) {
  if (!activityLog?.length) {
    return (
      <div className="panel corner-accents h-full">
        <div className="panel-title">Trip Activity</div>
        <div className="p-4 text-gray-500 text-xs">No data</div>
      </div>
    );
  }

  // Use current trip entries
  const tripEntries = getCurrentTripEntries(activityLog);

  // Aggregate by date (sum multiple entries per date)
  const byDate = {};
  for (const day of tripEntries) {
    const d = day.date;
    if (!byDate[d]) byDate[d] = { date: d, miles: 0, hooks: 0 };
    byDate[d].miles += day.miles || 0;
    byDate[d].hooks += day.activities?.HK || 0;
  }

  const sorted = Object.values(byDate).sort((a, b) => new Date(a.date) - new Date(b.date));

  const chartData = sorted.map((d) => ({
    date: new Date(d.date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    miles: d.miles,
    hooks: d.hooks,
  }));

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-surface border border-panel-border rounded p-2 text-xs">
        <div className="text-cyber-cyan font-bold mb-1">{label}</div>
        {payload.map((p, i) => (
          <div key={i} style={{ color: p.color }}>
            {p.name}: {p.value}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="panel corner-accents h-full">
      <div className="panel-title">Trip Activity</div>
      <div className="p-4 h-[220px]">
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
          <ComposedChart data={chartData} margin={{ top: 5, right: 5, bottom: 0, left: -15 }}>
            <XAxis
              dataKey="date"
              tick={{ fill: '#6b7280', fontSize: 10 }}
              axisLine={{ stroke: 'rgba(0,240,255,0.15)' }}
              tickLine={false}
            />
            <YAxis
              yAxisId="miles"
              tick={{ fill: '#6b7280', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              yAxisId="hooks"
              orientation="right"
              tick={{ fill: '#6b7280', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar
              yAxisId="miles"
              dataKey="miles"
              name="Miles"
              fill="rgba(0, 240, 255, 0.5)"
              stroke="rgba(0, 240, 255, 0.8)"
              strokeWidth={1}
              radius={[3, 3, 0, 0]}
            />
            <Line
              yAxisId="hooks"
              dataKey="hooks"
              name="Hooks"
              stroke="#ffbf00"
              strokeWidth={2}
              dot={{ fill: '#ffbf00', r: 3 }}
              activeDot={{ r: 5 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
