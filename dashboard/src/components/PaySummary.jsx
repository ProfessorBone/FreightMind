export default function PaySummary({ tripMemory }) {
  const previousDayPay = tripMemory?.previousDayPay || null;
  const tripPay = tripMemory?.tripPay || 0;
  const tripEntries = tripMemory?.activityDays || [];

  // Get current trip entries — same logic as dataLoader.getCurrentTripEntries
  const sorted = [...tripEntries].sort((a, b) => new Date(a.date) - new Date(b.date));
  const lastEntry = sorted[sorted.length - 1];

  let currentTripDays = [];
  if (lastEntry?.trip_number) {
    currentTripDays = sorted.filter((d) => d.trip_number === lastEntry.trip_number);
  } else {
    const withPay = sorted.filter((d) => d.pay != null && d.pay > 0);
    currentTripDays = withPay.slice(-5);
  }

  const tripStart = currentTripDays[0]?.date || null;
  const tripEnd = currentTripDays[currentTripDays.length - 1]?.date || null;
  const daysWithPay = currentTripDays.filter((d) => d.pay != null && d.pay > 0);
  const daysLogged = currentTripDays.length;

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    return new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  };

  const formatPay = (amount) => {
    if (amount == null || amount === 0) return '—';
    return `$${Number(amount).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  return (
    <div className="panel corner-accents h-full flex flex-col">
      <div className="panel-title flex items-center justify-between">
        <span>Pay Summary</span>
        {tripStart && (
          <span className="text-[0.6rem] text-gray-500 tracking-normal normal-case font-normal">
            {formatDate(tripStart)}{tripEnd && tripEnd !== tripStart ? ` — ${formatDate(tripEnd)}` : ''}
          </span>
        )}
      </div>

      <div className="p-4 flex flex-col gap-3">

        {/* Previous Day Pay */}
        <div className="bg-surface-light/40 border border-panel-border rounded p-3">
          <div className="text-[0.55rem] text-gray-500 tracking-wider mb-1">PREVIOUS DAY PAY</div>
          <div className="text-2xl font-bold text-cyber-green glow-green">
            {formatPay(previousDayPay)}
          </div>
          {previousDayPay == null && (
            <div className="text-[0.55rem] text-gray-600 mt-1">
              Tell Will Graham your pay after each shift
            </div>
          )}
        </div>

        {/* Trip Total Pay */}
        <div className="bg-surface-light/40 border border-panel-border rounded p-3">
          <div className="text-[0.55rem] text-gray-500 tracking-wider mb-1">TRIP TOTAL PAY</div>
          <div className="text-2xl font-bold text-cyber-cyan glow-cyan">
            {tripPay > 0 ? formatPay(tripPay) : '—'}
          </div>
          <div className="text-[0.55rem] text-gray-600 mt-1">
            {daysWithPay.length} of {daysLogged} day{daysLogged !== 1 ? 's' : ''} logged
          </div>
        </div>

        {/* Daily Pay Breakdown */}
        {daysWithPay.length > 0 && (
          <div>
            <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">DAILY BREAKDOWN</div>
            <div className="space-y-1.5">
              {currentTripDays.map((day) => (
                <div
                  key={day.date + (day.trip_number || '')}
                  className="flex items-center justify-between"
                >
                  <span className="text-[0.6rem] text-gray-400">
                    {formatDate(day.date)}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-[0.55rem] text-gray-600">
                      {day.miles ? `${day.miles} mi` : ''}
                    </span>
                    <span className={`text-[0.65rem] font-bold ${
                      day.pay ? 'text-cyber-green' : 'text-gray-600'
                    }`}>
                      {day.pay ? formatPay(day.pay) : 'pending'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Source */}
        <div className="text-[0.5rem] text-gray-600 text-right tracking-wider mt-auto">
          SRC: DAILY ACTIVITY LOG
        </div>

      </div>
    </div>
  );
}
