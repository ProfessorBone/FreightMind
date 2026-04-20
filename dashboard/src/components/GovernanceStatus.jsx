export default function GovernanceStatus() {
  const agents = [
    { name: 'Will Graham', role: 'Field Operations', status: 'ACTIVE', color: 'cyber-green' },
    { name: 'Jack Crawford', role: 'Governance', status: 'GOVERNING', color: 'cyber-amber' },
  ];

  return (
    <div className="panel corner-accents h-full">
      <div className="panel-title">Governance Status</div>
      <div className="p-4 space-y-4">
        {/* Governance indicators */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-surface-light/40 border border-panel-border rounded p-3 text-center">
            <div className="text-[0.55rem] text-gray-500 tracking-wider mb-1">MODE</div>
            <div className="text-sm font-bold text-cyber-red glow-red">STRICT</div>
          </div>
          <div className="bg-surface-light/40 border border-panel-border rounded p-3 text-center">
            <div className="text-[0.55rem] text-gray-500 tracking-wider mb-1">SOVEREIGN</div>
            <div className="text-sm font-bold text-cyber-amber glow-amber">FAHEEM</div>
          </div>
          <div className="bg-surface-light/40 border border-panel-border rounded p-3 text-center">
            <div className="text-[0.55rem] text-gray-500 tracking-wider mb-1">OVERRIDE</div>
            <div className="text-sm font-bold text-cyber-green glow-green">ENABLED</div>
          </div>
        </div>

        {/* Agent roster */}
        <div>
          <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">AGENT ROSTER</div>
          <div className="space-y-2">
            {agents.map((agent) => (
              <div
                key={agent.name}
                className="flex items-center justify-between bg-surface-light/40 border border-panel-border rounded px-3 py-2"
              >
                <div>
                  <div className="text-xs text-gray-200 font-medium">{agent.name}</div>
                  <div className="text-[0.55rem] text-gray-500">{agent.role}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`status-dot online`} style={{
                    background: agent.color === 'cyber-amber' ? '#ffbf00' : '#39ff14',
                    boxShadow: `0 0 8px ${agent.color === 'cyber-amber' ? '#ffbf00' : '#39ff14'}`,
                  }} />
                  <span className={`badge bg-${agent.color}/20 text-${agent.color} border border-${agent.color}/30`}
                    style={{
                      background: agent.color === 'cyber-amber' ? 'rgba(255,191,0,0.15)' : 'rgba(57,255,20,0.15)',
                      color: agent.color === 'cyber-amber' ? '#ffbf00' : '#39ff14',
                      borderColor: agent.color === 'cyber-amber' ? 'rgba(255,191,0,0.3)' : 'rgba(57,255,20,0.3)',
                    }}
                  >
                    {agent.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Escalation chain */}
        <div>
          <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">ESCALATION CHAIN</div>
          <div className="flex items-center gap-1 text-[0.6rem]">
            <span className="bg-cyber-cyan/15 text-cyber-cyan border border-cyber-cyan/30 px-2 py-1 rounded">
              Will Graham
            </span>
            <span className="text-gray-600">→</span>
            <span className="bg-cyber-amber/15 text-cyber-amber border border-cyber-amber/30 px-2 py-1 rounded">
              Jack Crawford
            </span>
            <span className="text-gray-600">→</span>
            <span className="bg-cyber-green/15 text-cyber-green border border-cyber-green/30 px-2 py-1 rounded font-bold">
              FAHEEM
            </span>
          </div>
        </div>

        {/* Global status bar */}
        <div className="border-t border-panel-border pt-3 flex items-center justify-center gap-4 text-[0.55rem] tracking-wider">
          <span className="text-cyber-green glow-green">● GOVERNED</span>
          <span className="text-cyber-cyan glow-cyan">● SECURE</span>
          <span className="text-cyber-amber glow-amber">● AUDITABLE</span>
        </div>
      </div>
    </div>
  );
}
