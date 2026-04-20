import { useState } from 'react';

export default function HazmatControls({ onSaved }) {
  const [form, setForm] = useState({ sourceName: '', sourceText: '', fileReference: '' });
  const [status, setStatus] = useState('');
  const [saving, setSaving] = useState(false);

  async function submitCase(e) {
    e.preventDefault();
    setSaving(true);
    setStatus('Saving hazmat case...');
    try {
      const res = await fetch('/api/hazmat/cases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_summary: 'Assess supplied BOL text for hazmat status and placard-support reasoning.',
          source_name: form.sourceName,
          source_text: form.sourceText,
          file_reference: form.fileReference || null,
        }),
      });
      if (!res.ok) throw new Error('Failed to save hazmat case');
      setStatus('Hazmat case saved');
      setForm({ sourceName: '', sourceText: '', fileReference: '' });
      onSaved?.();
    } catch (err) {
      setStatus(err.message || 'Hazmat case save failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="panel corner-accents h-full flex flex-col">
      <div className="panel-title">Hazmat Case Intake</div>
      <div className="p-4 space-y-4">
        <form onSubmit={submitCase} className="space-y-2">
          <div className="text-[0.55rem] text-gray-500 tracking-wider">TEXT-FIRST BOL INTAKE</div>
          <input
            className="trip-input"
            placeholder="Source Name (ex: HMT-001-manual-text)"
            value={form.sourceName}
            onChange={(e) => setForm((f) => ({ ...f, sourceName: e.target.value }))}
            required
          />
          <input
            className="trip-input"
            placeholder="Optional local file path for OCR/PDF intake"
            value={form.fileReference}
            onChange={(e) => setForm((f) => ({ ...f, fileReference: e.target.value }))}
          />
          <textarea
            className="trip-input"
            placeholder="Paste BOL text here (or leave blank if using file path above)"
            value={form.sourceText}
            onChange={(e) => setForm((f) => ({ ...f, sourceText: e.target.value }))}
            rows={8}
          />
          <button className="trip-button" disabled={saving} type="submit">Create Hazmat Case</button>
        </form>

        <div className="text-[0.6rem] text-gray-400 min-h-[1rem]">{status}</div>
      </div>
    </div>
  );
}
