export default function TripMemoryPanel({ tripMemory }) {
  const activeTrip = tripMemory?.activeTrip;
  const recentTrips = tripMemory?.recentTrips || [];

  return (
    <div className="panel corner-accents h-full flex flex-col">
      <div className="panel-title flex items-center justify-between">
        <span>Will Graham Memory</span>
        <span className="text-[0.55rem] text-gray-500 tracking-normal normal-case font-normal">
          {activeTrip ? `Trip #${activeTrip.trip_number}` : 'No active trip'}
        </span>
      </div>

      <div className="p-4 flex flex-col gap-4">
        {activeTrip ? (
          <>
            <div className="bg-surface-light/40 border border-panel-border rounded p-3">
              <div className="text-[0.55rem] text-gray-500 tracking-wider mb-1">ACTIVE TRIP</div>
              <div className="text-cyber-cyan text-lg font-bold">#{activeTrip.trip_number}</div>
              <div className="text-[0.65rem] text-gray-400 mt-1">
                {activeTrip.date || 'Unknown date'} · {activeTrip.status || 'active'}
              </div>
              <div className="text-[0.6rem] text-gray-500 mt-2">
                Current stop: {activeTrip.current_stop_index ?? '—'}
              </div>
            </div>

            <div>
              <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">STOPS</div>
              <div className="space-y-2">
                {(activeTrip.stops || []).length ? activeTrip.stops.map((stop, idx) => {
                  const stopNumber = idx + 1;
                  const isCurrent = activeTrip.current_stop_index === stopNumber;
                  return (
                    <div
                      key={`${activeTrip.trip_number}-${stop}-${stopNumber}`}
                      className={`border rounded px-3 py-2 text-xs ${isCurrent ? 'border-cyber-cyan text-cyber-cyan bg-cyber-cyan/10' : 'border-panel-border text-gray-300 bg-surface-light/30'}`}
                    >
                      <span className="text-gray-500 mr-2">{stopNumber}.</span>
                      {stop}
                      {isCurrent && <span className="ml-2 text-[0.55rem]">CURRENT</span>}
                    </div>
                  );
                }) : (
                  <div className="text-xs text-gray-500">No stops stored.</div>
                )}
              </div>
            </div>

            <div>
              <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">RECENT EVENTS</div>
              <div className="space-y-2 max-h-[180px] overflow-y-auto">
                {(activeTrip.events || []).slice(-6).reverse().map((event) => (
                  <div key={event.event_id} className="bg-surface-light/30 border border-panel-border rounded px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-cyber-amber text-xs font-bold">{event.code}</span>
                      <span className="text-[0.55rem] text-gray-500">{event.timestamp}</span>
                    </div>
                    <div className="text-xs text-gray-300 mt-1">
                      Value: {event.value}{event.stop_index ? ` · Stop ${event.stop_index}` : ''}
                    </div>
                    {event.raw_message && (
                      <div className="text-[0.55rem] text-gray-500 mt-1">{event.raw_message}</div>
                    )}
                  </div>
                ))}
                {!activeTrip.events?.length && <div className="text-xs text-gray-500">No events stored.</div>}
              </div>
            </div>
          </>
        ) : (
          <div className="text-xs text-gray-500">No trip memory loaded yet.</div>
        )}

        <div>
          <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">RECENT TRIPS</div>
          <div className="space-y-2">
            {recentTrips.length ? recentTrips.slice(0, 5).map((trip) => (
              <div key={trip.trip_number} className="bg-surface-light/20 border border-panel-border rounded px-3 py-2 text-xs flex items-center justify-between gap-2">
                <div>
                  <div className="text-gray-200 font-semibold">#{trip.trip_number}</div>
                  <div className="text-[0.55rem] text-gray-500">{trip.date || 'Unknown date'}</div>
                </div>
                <div className="text-[0.55rem] text-gray-400">{trip.events?.length || 0} events</div>
              </div>
            )) : (
              <div className="text-xs text-gray-500">No recent trips found.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
