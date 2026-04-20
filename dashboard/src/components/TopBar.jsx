import { useState, useEffect } from 'react';

export default function TopBar({ heartbeat, onRefresh, refreshing }) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const statusColor = heartbeat?.status === 'ACTIVE' ? 'online' : 'online';
  const statusText = heartbeat?.status || 'STANDBY';

  return (
    <div className="panel animate-border-glow" style={{ marginBottom: 16, width: '100%', boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', padding: '12px 16px', gap: '8px 24px' }}>
        {/* Left: Status indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className={`status-dot ${statusColor}`} />
            <span className="text-xs text-gray-400" style={{ letterSpacing: '0.1em' }}>SYSTEM</span>
            <span className="badge bg-cyber-green/20 text-cyber-green border border-cyber-green/30">
              {statusText}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="text-xs text-gray-500" style={{ letterSpacing: '0.1em' }}>GOVERNANCE</span>
            <span className="badge bg-cyber-cyan/20 text-cyber-cyan border border-cyber-cyan/30">
              STRICT
            </span>
          </div>
        </div>

        {/* Center: Title */}
        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <h1 className="text-cyber-cyan glow-cyan" style={{ fontSize: '1.15rem', fontWeight: 700, letterSpacing: '0.35em', margin: 0, lineHeight: 1 }}>
            FREIGHTMIND
          </h1>
          <div style={{ fontSize: '0.55rem', letterSpacing: '0.3em', color: '#6b7280', marginTop: 4 }}>
            GOVERNED ROUTING INTELLIGENCE
          </div>
        </div>

        {/* Right: Refresh + Sovereign + Time */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexShrink: 0 }}>
          <button
            onClick={onRefresh}
            disabled={refreshing}
            title="Refresh live data"
            style={{
              background: 'transparent',
              border: '1px solid rgba(0, 255, 255, 0.25)',
              borderRadius: 4,
              padding: '4px 8px',
              cursor: refreshing ? 'default' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              opacity: refreshing ? 0.6 : 1,
              transition: 'border-color 0.2s, opacity 0.2s',
            }}
            onMouseEnter={(e) => { if (!refreshing) e.currentTarget.style.borderColor = 'rgba(0, 255, 255, 0.6)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(0, 255, 255, 0.25)'; }}
          >
            <svg
              width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              className="text-cyber-cyan"
              style={{
                animation: refreshing ? 'spin 0.8s linear infinite' : 'none',
              }}
            >
              <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3" />
            </svg>
            <span className="text-cyber-cyan" style={{ fontSize: '0.6rem', letterSpacing: '0.1em', fontWeight: 600 }}>
              {refreshing ? 'SYNCING' : 'REFRESH'}
            </span>
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="text-xs text-gray-500" style={{ letterSpacing: '0.1em' }}>SOVEREIGN</span>
            <span className="text-cyber-amber glow-amber" style={{ fontSize: '0.875rem', fontWeight: 700, letterSpacing: '0.1em' }}>
              FAHEEM
            </span>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="text-cyber-cyan" style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.1em' }}>
              {time.toLocaleTimeString('en-US', { hour12: false })}
            </div>
            <div style={{ fontSize: '0.55rem', color: '#6b7280', letterSpacing: '0.1em' }}>
              {time.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
