import { useEffect, useState } from 'react';
import { api } from '../api';
import StatusPill from '../components/StatusPill';
import type { Assignment, Call, ChatThread, User } from '../types';
import ScheduleCall from './ScheduleCall';

export default function CmcDashboard({ user, onOpenChat }: { user: User; onOpenChat?: () => void }) {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [calls, setCalls] = useState<Call[]>([]);
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [error, setError] = useState('');

  async function handleAccept(callId: string) {
    try {
      await api.acceptCall(user.id, callId);
      await load();
    } catch (acceptError) {
      setError(acceptError instanceof Error ? acceptError.message : 'Failed to accept call');
    }
  }

  async function handleDelete(callId: string) {
    try {
      await api.deleteCall(user.id, callId);
      await load();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete call');
    }
  }

  async function handleMarkMissed(callId: string) {
    try {
      await api.markMissed(user.id, callId);
      await load();
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to mark call as missed');
    }
  }

  async function load() {
    try {
      setAssignments(await api.cmcAssignments(user.id));
      setCalls(await api.calls(user.id));
      setThreads(await api.chatThreads(user.id));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load CMC dashboard');
    }
  }

  useEffect(() => { load(); }, [user.id]);

  return (
    <main>
      <h2>CMC dashboard</h2>
      {error && <p className="error">{error}</p>}
      <section className="card">
        <h3>Assigned properties</h3>
        <table>
          <thead><tr><th>Property</th><th>Transition</th><th>First call due</th><th>First call</th></tr></thead>
          <tbody>
            {assignments.map((assignment) => (
              <tr key={assignment.id}>
                <td>{assignment.property.name}</td>
                <td><StatusPill value={assignment.property.transition_status} /></td>
                <td>{assignment.first_call_due_at ? new Date(assignment.first_call_due_at).toLocaleString() : '-'}</td>
                <td><StatusPill value={assignment.first_call_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {assignments.map((assignment) => (
        <ScheduleCall key={assignment.id} user={user} property={assignment.property} callType="first_call" onBooked={load} />
      ))}
      <section className="card">
        <h3>My scheduled calls</h3>
        <table>
          <thead><tr><th>Type</th><th>Time</th><th>Status</th><th>Zoom</th><th>Actions</th></tr></thead>
          <tbody>
            {calls.map((call) => (
              <tr key={call.id}>
                <td>{call.call_type}</td>
                <td>{new Date(call.start_time).toLocaleString()}</td>
                <td><StatusPill value={call.status} /></td>
                <td>{call.zoom_join_url ? <a href={call.zoom_join_url}>Open</a> : '-'}</td>
                <td>
                  {call.status === 'pending' && call.call_type === 'follow_up' && (
                    <button type="button" onClick={() => handleAccept(call.id)}>Accept</button>
                  )}
                  {call.status === 'scheduled' && (
                    <button type="button" onClick={() => handleMarkMissed(call.id)}>Mark missed</button>
                  )}
                  <button type="button" onClick={() => handleDelete(call.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="card">
        <div className="row between">
          <div>
            <h3>Messages</h3>
            <p className="muted">Unread conversations: {threads.reduce((count, thread) => count + thread.unread_count, 0)}</p>
          </div>
          {onOpenChat ? <button type="button" onClick={onOpenChat}>Open Chat</button> : null}
        </div>
        <table>
          <thead><tr><th>Property</th><th>Last message</th><th>Unread</th></tr></thead>
          <tbody>
            {threads.map((thread) => (
              <tr key={thread.id}>
                <td>{thread.property.name}</td>
                <td>{thread.last_message ?? 'No messages yet'}</td>
                <td>{thread.unread_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
