const IMPACT_COLORS = {
  high: { bg: 'bg-cyber-red/15', text: 'text-cyber-red', border: 'border-cyber-red/30', dot: 'bg-cyber-red' },
  medium_to_high: { bg: 'bg-cyber-amber/15', text: 'text-cyber-amber', border: 'border-cyber-amber/30', dot: 'bg-cyber-amber' },
  medium: { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/30', dot: 'bg-yellow-400' },
  low: { bg: 'bg-cyber-green/15', text: 'text-cyber-green', border: 'border-cyber-green/30', dot: 'bg-cyber-green' },
  unknown: { bg: 'bg-gray-500/15', text: 'text-gray-400', border: 'border-gray-500/30', dot: 'bg-gray-400' },
};

export default function CongestionMemory({ congestion }) {
  if (!congestion?.length) {
    return (
      <div className="panel corner-accents h-full">
        <div className="panel-title">Congestion Memory</div>
        <div className="p-4 text-gray-500 text-xs">No data</div>
      </div>
    );
  }

  return (
    <div className="panel corner-accents h-full flex flex-col">
      <div className="panel-title flex items-center justify-between">
        <span>Congestion Memory</span>
        <span className="text-[0.55rem] text-gray-500 tracking-normal normal-case font-normal">
          {congestion.length} entries
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 max-h-[340px]">
        {congestion.map((entry) => {
          const impact = IMPACT_COLORS[entry.impactLevel] || IMPACT_COLORS.unknown;
          return (
            <div
              key={entry.id}
              className={`${impact.bg} border ${impact.border} rounded p-3`}
            >
              <div className="flex items-start justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-[0.6rem] font-bold text-cyber-cyan">{entry.id}</span>
                  <span className={`badge ${impact.bg} ${impact.text} border ${impact.border}`}>
                    {entry.impactLevel.replace(/_/g, ' ').toUpperCase()}
                  </span>
                </div>
              </div>
              <div className="text-xs text-gray-200 font-medium mb-1">{entry.area}</div>
              <div className="flex items-center gap-4 text-[0.6rem] text-gray-400">
                <span>🕐 {entry.timeWindow}</span>
                <span>📅 {entry.dayType}</span>
              </div>
              {entry.notes?.length > 0 && (
                <div className="mt-2 space-y-0.5">
                  {entry.notes.slice(0, 2).map((note, i) => (
                    <div key={i} className="text-[0.55rem] text-gray-400 leading-relaxed">
                      {note}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
