import { useState } from 'react';

const initialTripForm = {
  date: '',
  tripNumber: '',
  stops: '',
};

export default function TripMemoryControls({ onSaved }) {
  const [tripForm, setTripForm] = useState(initialTripForm);
  const [eventForm, setEventForm] = useState({ date: '', tripNumber: '', rawMessage: '' });
  const [status, setStatus] = useState('');
  const [saving, setSaving] = useState(false);

  async function createTrip(e) {
    e.preventDefault();
    setSaving(true);
    setStatus('Saving trip...');
    try {
      const payload = {
        date: tripForm.date,
        trip_number: tripForm.tripNumber,
        stops: tripForm.stops.split('->').map((s) => s.trim()).filter(Boolean),
        raw_message: `Trip ${tripForm.tripNumber}: ${tripForm.stops}`,
      };
      const res = await fetch('/api/trips', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Failed to save trip');
      setStatus('Trip saved');
      setTripForm(initialTripForm);
      onSaved?.();
    } catch (err) {
      setStatus(err.message || 'Trip save failed');
    } finally {
      setSaving(false);
    }
  }

  async function appendEvent(e) {
    e.preventDefault();
    setSaving(true);
    setStatus('Appending event...');
    try {
      const res = await fetch(`/api/trips/${encodeURIComponent(eventForm.tripNumber)}/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: eventForm.date,
          raw_message: eventForm.rawMessage,
        }),
      });
      if (!res.ok) throw new Error('Failed to append event');
      setStatus('Event saved');
      setEventForm({ date: '', tripNumber: '', rawMessage: '' });
      onSaved?.();
    } catch (err) {
      setStatus(err.message || 'Event save failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="panel corner-accents h-full flex flex-col">
      <div className="panel-title">Trip Memory Controls</div>
      <div className="p-4 space-y-4">
        <form onSubmit={createTrip} className="space-y-2">
          <div className="text-[0.55rem] text-gray-500 tracking-wider">CREATE / UPDATE TRIP</div>
          <input className="trip-input" placeholder="Date (optional — defaults to today ET)" value={tripForm.date} onChange={(e) => setTripForm((f) => ({ ...f, date: e.target.value }))} />
          <input className="trip-input" placeholder="Trip Number" value={tripForm.tripNumber} onChange={(e) => setTripForm((f) => ({ ...f, tripNumber: e.target.value }))} required />
          <input className="trip-input" placeholder="Stops: S1001 -> DC2002 -> S3003" value={tripForm.stops} onChange={(e) => setTripForm((f) => ({ ...f, stops: e.target.value }))} required />
          <button className="trip-button" disabled={saving} type="submit">Save Trip</button>
        </form>

        <form onSubmit={appendEvent} className="space-y-2">
          <div className="text-[0.55rem] text-gray-500 tracking-wider">APPEND SHORTHAND EVENT</div>
          <input className="trip-input" placeholder="Date (optional — defaults to today ET)" value={eventForm.date} onChange={(e) => setEventForm((f) => ({ ...f, date: e.target.value }))} />
          <input className="trip-input" placeholder="Trip Number" value={eventForm.tripNumber} onChange={(e) => setEventForm((f) => ({ ...f, tripNumber: e.target.value }))} required />
          <input className="trip-input" placeholder="AD 1 / HK 1 / Miles 372 / $414.13" value={eventForm.rawMessage} onChange={(e) => setEventForm((f) => ({ ...f, rawMessage: e.target.value }))} required />
          <button className="trip-button" disabled={saving} type="submit">Append Event</button>
        </form>

        <div className="text-[0.6rem] text-gray-400 min-h-[1rem]">{status}</div>
      </div>
    </div>
  );
}
