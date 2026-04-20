import { useData } from './hooks/useData';
import TopBar from './components/TopBar';
import ActivitySummary from './components/ActivitySummary';
import WeeklyChart from './components/WeeklyChart';
import TrackedTimePanel from './components/TrackedTimePanel';
import StoreIntel from './components/StoreIntel';
import CongestionMemory from './components/CongestionMemory';
import AuditLog from './components/AuditLog';
import GovernanceStatus from './components/GovernanceStatus';
import TripMemoryPanel from './components/TripMemoryPanel';
import TripMemoryControls from './components/TripMemoryControls';
import HazmatPanel from './components/HazmatPanel';
import HazmatControls from './components/HazmatControls';

function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center grid-bg">
      <div className="text-center">
        <div className="text-2xl font-bold tracking-[0.4em] text-cyber-cyan glow-cyan mb-3">
          FREIGHTMIND
        </div>
        <div className="text-[0.6rem] tracking-[0.3em] text-gray-500 mb-8">
          INITIALIZING SYSTEMS
        </div>
        <div className="flex items-center justify-center gap-1">
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="w-2 h-6 bg-cyber-cyan/40 rounded-sm animate-pulse-glow"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function App() {
  const { data, loading, error, refreshing, refresh } = useData();

  if (loading) return <LoadingScreen />;

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center grid-bg">
        <div className="text-center text-cyber-red">
          <div className="text-lg font-bold mb-2">SYSTEM ERROR</div>
          <div className="text-xs text-gray-400">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen grid-bg">
      <div className="scanlines" />

      <div style={{ width: '100%', maxWidth: 1920, margin: '0 auto', padding: 16, boxSizing: 'border-box' }}>
        <TopBar heartbeat={data.heartbeat} onRefresh={refresh} refreshing={refreshing} />

        {/* Row 1: Activity Summary + Trip Activity + Tracked Time */}
        <div className="dashboard-row" style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 16 }}>
          <div style={{ flex: '1 1 320px', minWidth: 0 }}>
            <ActivitySummary tripMemory={data.tripMemory} />
          </div>
          <div style={{ flex: '1.4 1 400px', minWidth: 0 }}>
            <WeeklyChart activityLog={data.activityLog} />
          </div>
          <div style={{ flex: '0.8 1 280px', minWidth: 0 }}>
            <TrackedTimePanel activityLog={data.activityLog} />
          </div>
        </div>

        {/* Row 2: Store Intel + Congestion Memory + Audit Log + Trip Memory */}
        <div className="dashboard-row" style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 16 }}>
          <div style={{ flex: '1 1 280px', minWidth: 0 }}>
            <StoreIntel stores={data.stores} vendors={data.vendors} tripMemory={data.tripMemory} />
          </div>
          <div style={{ flex: '1 1 280px', minWidth: 0 }}>
            <CongestionMemory congestion={data.congestion} />
          </div>
          <div style={{ flex: '1 1 280px', minWidth: 0 }}>
            <AuditLog tripMemory={data.tripMemory} />
          </div>
          <div style={{ flex: '1.2 1 340px', minWidth: 0 }}>
            <TripMemoryPanel tripMemory={data.tripMemory} />
          </div>
        </div>

        <div className="dashboard-row" style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 16 }}>
          <div style={{ flex: '1 1 420px', minWidth: 0 }}>
            <TripMemoryControls onSaved={refresh} />
          </div>
          <div style={{ flex: '1.2 1 420px', minWidth: 0 }}>
            <HazmatControls onSaved={refresh} />
          </div>
        </div>

        <div className="dashboard-row" style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 16 }}>
          <div style={{ flex: '1 1 460px', minWidth: 0 }}>
            <HazmatPanel hazmatMemory={data.hazmatMemory} />
          </div>
        </div>

        {/* Row 3: Governance Status (full width) */}
        <div style={{ marginBottom: 16 }}>
          <GovernanceStatus />
        </div>

        {/* Bottom bar */}
        <div className="panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, padding: '8px 16px', fontSize: '0.5rem', color: '#6b7280', letterSpacing: '0.1em' }}>
          <span>FREIGHTMIND v1.0.0 — OPENCLAW RUNTIME</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span>HOST: HANNIBAL</span>
            <span>NODE: EDGE</span>
            <span className="text-cyber-green">● OPERATIONAL</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
