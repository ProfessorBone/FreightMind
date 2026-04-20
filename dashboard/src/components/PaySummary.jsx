export default function PaySummary({ tripMemory }) {
  const previousDayPay = tripMemory?.previousDayPay || null;
  const tripPay = tripMemory?.tripPay || 0;

  const formatPay = (amount) => {
    if (amount == null || amount === 0) return '—';
    return `$${Number(amount).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  return (
    <div className="panel corner-accents h-full">
      <div className="panel-title">Pay Summary</div>

      <div className="p-4 flex flex-col gap-3">

        {/* Previous Day Pay */}
        <div className="flex items-center justify-between bg-surface-light/40 border border-panel-border rounded p-3">
          <span className="text-xs text-gray-400 tracking-wider">PREVIOUS DAY PAY</span>
          <span className="text-xl font-bold text-cyber-green glow-green">
            {formatPay(previousDayPay)}
          </span>
        </div>

        {/* Work Week Pay */}
        <div className="flex items-center justify-between bg-surface-light/40 border border-panel-border rounded p-3">
          <span className="text-xs text-gray-400 tracking-wider">WORK WEEK PAY</span>
          <span className="text-xl font-bold text-cyber-cyan glow-cyan">
            {formatPay(tripPay)}
          </span>
        </div>

        <div className="mt-auto text-[0.5rem] text-gray-600 text-right tracking-wider">
          SRC: DAILY ACTIVITY LOG
        </div>

      </div>
    </div>
  );
}
