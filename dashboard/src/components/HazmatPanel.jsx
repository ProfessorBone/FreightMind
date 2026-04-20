export default function HazmatPanel({ hazmatMemory }) {
  const activeCase = hazmatMemory?.activeCase;
  const recentCases = hazmatMemory?.recentCases || [];

  return (
    <div className="panel corner-accents h-full flex flex-col">
      <div className="panel-title flex items-center justify-between">
        <span>Hazmat Intelligence</span>
        <span className="text-[0.55rem] text-gray-500 tracking-normal normal-case font-normal">
          {activeCase ? activeCase.case_id : 'No active case'}
        </span>
      </div>

      <div className="p-4 flex flex-col gap-4">
        {activeCase ? (
          <>
            <div className="bg-surface-light/40 border border-panel-border rounded p-3">
              <div className="text-[0.55rem] text-gray-500 tracking-wider mb-1">ACTIVE CASE</div>
              <div className="text-cyber-cyan text-sm font-bold">{activeCase.case_id}</div>
              <div className="text-[0.65rem] text-gray-400 mt-1">
                {activeCase.document_assessed?.source_name || 'Unknown source'}
              </div>
              <div className="text-[0.6rem] text-gray-500 mt-2">
                Hazmat: <span className="text-gray-300">{activeCase.hazmat_detected}</span>
                {' · '}
                Placard: <span className="text-gray-300">{activeCase.placard_required}</span>
                {' · '}
                Confidence: <span className="text-gray-300">{activeCase.confidence_level}</span>
              </div>
            </div>

            <div>
              <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">EXTRACTED IDENTIFIERS</div>
              <div className="space-y-2">
                {(activeCase.extracted_fields?.commodity_lines || []).length ? activeCase.extracted_fields.commodity_lines.map((line, idx) => (
                  <div key={`${activeCase.case_id}-${idx}`} className="bg-surface-light/30 border border-panel-border rounded px-3 py-2 text-xs">
                    <div className="text-gray-200 font-semibold">{line.un_na_number || 'No UN/NA'} · {line.hazard_class_division || 'No class'}</div>
                    <div className="text-gray-400 mt-1">{line.proper_shipping_name || line.description}</div>
                    <div className="text-[0.55rem] text-gray-500 mt-1">
                      PG: {line.packing_group || '—'} · Qty: {line.quantity || '—'}
                    </div>
                  </div>
                )) : (
                  <div className="text-xs text-gray-500">No extraction stored.</div>
                )}
              </div>
            </div>

            <div>
              <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">PLACARD SUPPORT</div>
              <div className="space-y-2">
                {(activeCase.indicated_placards || []).length ? activeCase.indicated_placards.map((placard, idx) => (
                  <div key={`${activeCase.case_id}-placard-${idx}`} className="bg-surface-light/20 border border-panel-border rounded px-3 py-2 text-xs">
                    <div className="text-cyber-amber font-semibold">{placard.placard_name}</div>
                    <div className="text-gray-400 mt-1">{placard.basis}</div>
                  </div>
                )) : (
                  <div className="text-xs text-gray-500">No placard indication stored.</div>
                )}
              </div>
            </div>

            <div>
              <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">RETRIEVAL EVIDENCE</div>
              <div className="space-y-2">
                {(activeCase.retrieval_evidence?.context1_reasoning?.selected_documents || []).length ? activeCase.retrieval_evidence.context1_reasoning.selected_documents.map((doc, idx) => (
                  <div key={`${activeCase.case_id}-doc-${idx}`} className="bg-surface-light/20 border border-panel-border rounded px-3 py-2 text-xs">
                    <div className="text-gray-200 font-semibold">{doc.file_name}</div>
                    <div className="text-gray-500 mt-1">{doc.title}</div>
                    <div className="text-[0.55rem] text-gray-400 mt-1">Citations: {(doc.citations || []).join(', ') || '—'}</div>
                  </div>
                )) : (
                  <div className="text-xs text-gray-500">No retrieval evidence stored.</div>
                )}
              </div>
            </div>

            <div>
              <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">HARNESS TRACE</div>
              <div className="space-y-3">
                {(activeCase.retrieval_evidence?.hannibal_retrieval_harness?.turns || []).length ? activeCase.retrieval_evidence.hannibal_retrieval_harness.turns.map((turn, idx) => (
                  <div key={`${activeCase.case_id}-turn-${idx}`} className="bg-surface-light/20 border border-panel-border rounded px-3 py-2 text-xs">
                    <div className="text-cyber-cyan font-semibold">Turn {idx + 1}</div>
                    <div className="text-gray-400 mt-1">Query: {turn.query}</div>
                    <div className="mt-2 space-y-1">
                      {(turn.selected_docs || []).map((doc, docIdx) => (
                        <div key={`${activeCase.case_id}-turn-${idx}-doc-${docIdx}`} className="text-[0.65rem] text-gray-300">
                          • {doc.file_name} {doc.citations?.length ? `(${doc.citations.join(', ')})` : ''}
                        </div>
                      ))}
                      {!(turn.selected_docs || []).length && <div className="text-[0.65rem] text-gray-500">No selected docs.</div>}
                    </div>
                    {(turn.dropped_docs || []).length ? (
                      <div className="text-[0.6rem] text-gray-500 mt-2">Pruned: {turn.dropped_docs.join(', ')}</div>
                    ) : null}
                    {(turn.notes || []).length ? (
                      <div className="text-[0.6rem] text-gray-500 mt-1">{turn.notes.join(' ')}</div>
                    ) : null}
                  </div>
                )) : (
                  <div className="text-xs text-gray-500">No harness trace stored.</div>
                )}
              </div>
            </div>

            <div>
              <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">UNCERTAINTY</div>
              <div className="space-y-1">
                {(activeCase.uncertainty || []).length ? activeCase.uncertainty.map((item, idx) => (
                  <div key={`${activeCase.case_id}-unc-${idx}`} className="text-xs text-gray-400">• {item}</div>
                )) : (
                  <div className="text-xs text-gray-500">No uncertainty recorded.</div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="text-xs text-gray-500">No hazmat case loaded yet.</div>
        )}

        <div>
          <div className="text-[0.55rem] text-gray-500 tracking-wider mb-2">RECENT CASES</div>
          <div className="space-y-2">
            {recentCases.length ? recentCases.slice(0, 5).map((item) => (
              <div key={item.case_id} className="bg-surface-light/20 border border-panel-border rounded px-3 py-2 text-xs flex items-center justify-between gap-2">
                <div>
                  <div className="text-gray-200 font-semibold">{item.case_id}</div>
                  <div className="text-[0.55rem] text-gray-500">{item.source_name || 'Unknown source'}</div>
                </div>
                <div className="text-[0.55rem] text-gray-400">{item.confidence_level || '—'}</div>
              </div>
            )) : (
              <div className="text-xs text-gray-500">No recent hazmat cases found.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
