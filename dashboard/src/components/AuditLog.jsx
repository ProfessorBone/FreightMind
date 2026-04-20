const CODE_STYLE = {
  AD: { bg: 'bg-cyber-cyan/15', text: 'text-cyber-cyan', border: 'border-cyber-cyan/30' },
  HK: { bg: 'bg-cyber-amber/15', text: 'text-cyber-amber', border: 'border-cyber-amber/30' },
  LL: { bg: 'bg-cyber-purple/15', text: 'text-cyber-purple', border: 'border-cyber-purple/30' },
  LU: { bg: 'bg-cyber-green/15', text: 'text-cyber-green', border: 'border-cyber-green/30' },
  default: { bg: 'bg-gray-500/15', text: 'text-gray-400', border: 'border-gray-500/30' },
};

export default function AuditLog({ tripMemory }) {
  const activeTrip = tripMemory?.activeTrip;
  const events = activeTrip?.events || [];

  if (!activeTrip) {
    return (
      <div className="panel corner-accents h-full">
        <div className="panel-title">Live Audit Log</div>
        <div className="p-4 text-gray-500 text-xs">No active trip</div>
      </div>
    );
  }

  const sorted = [...events].slice(-10).reverse();

  return (
    <div className="panel corner-accents h-full flex flex-col">
      <div className="panel-title flex items-center justify-between">
        <span>Live Audit Log</span>
        <span className="text-[0.55rem] text-gray-500 tracking-normal normal-case font-normal">
          Trip #{activeTrip.trip_number}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 max-h-[340px]">
        {sorted.length ? sorted.map((event) => {
          const style = CODE_STYLE[event.code] || CODE_STYLE.default;
          return (
            <div key={event.event_id} className="bg-surface-light/40 border border-panel-border rounded p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[0.55rem] text-gray-500">{event.timestamp}</span>
                <span className={`badge ${style.bg} ${style.text} border ${style.border}`}>
                  {event.code}
                </span>
              </div>
              <div className="text-xs text-gray-200 leading-relaxed">
                {event.raw_message || `${event.code} ${event.value}`}
              </div>
              {event.stop_index ? (
                <span className="text-[0.5rem] text-gray-500 mt-1 inline-block">STOP: {event.stop_index}</span>
              ) : null}
            </div>
          );
        }) : <div className="text-gray-500 text-xs">No trip events yet</div>}
      </div>
    </div>
  );
}
