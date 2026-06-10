import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Call, Property, Slot, User } from '../types';

interface Props {
  user: User;
  property: Property;
  callType: 'first_call' | 'follow_up';
  existingCall?: Call;
  onBooked?: () => void;
}

export default function ScheduleCall({ user, property, callType, existingCall, onBooked }: Props) {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<Slot | null>(null);
  const [message, setMessage] = useState<string>('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const start = new Date();
    const end = new Date();
    end.setDate(end.getDate() + 7);
    api.slots(user.id, property.id, start.toISOString(), end.toISOString())
      .then(setSlots)
      .catch((error) => setMessage(error.message));
  }, [property.id, user.id]);

  const isReschedule = Boolean(existingCall);

  async function book() {
    if (!selectedSlot) return;
    setLoading(true);
    setMessage('');
    try {
      const payload = {
        property_id: property.id,
        call_type: callType,
        start_time: selectedSlot.start_time,
        end_time: selectedSlot.end_time,
        timezone: selectedSlot.timezone,
        attendee_user_ids: [],
      };
      const call = isReschedule
        ? await api.rescheduleCall(user.id, existingCall!.id, {
            start_time: selectedSlot.start_time,
            end_time: selectedSlot.end_time,
            timezone: selectedSlot.timezone,
          })
        : await api.book(user.id, payload);
      if (call.status === 'pending') {
        setMessage('Follow-up request created. Waiting for CMC approval.');
      } else if (isReschedule) {
        setMessage('Call rescheduled. Zoom: ' + (call.zoom_join_url ?? 'available after confirmation'));
      } else {
        setMessage(`Call booked. Zoom: ${call.zoom_join_url}`);
      }
      onBooked?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to book call');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card">
      <h3>{isReschedule ? 'Reschedule call' : callType === 'first_call' ? 'Schedule mandatory first call' : 'Schedule follow-up call'}</h3>
      <p className="muted">Slots are generated from the assigned CMC calendar and locally scheduled calls.</p>
      <div className="slot-grid">
        {slots.slice(0, 12).map((slot) => (
          <button
            className={selectedSlot?.start_time === slot.start_time ? 'slot selected' : 'slot'}
            key={slot.start_time}
            onClick={() => setSelectedSlot(slot)}
          >
            {new Date(slot.start_time).toLocaleString()}
          </button>
        ))}
      </div>
      <button disabled={!selectedSlot || loading} onClick={book}>{loading ? 'Booking...' : 'Book selected slot'}</button>
      {message && <p className="message">{message}</p>}
    </section>
  );
}
