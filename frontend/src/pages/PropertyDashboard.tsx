import { useEffect, useState } from 'react';
import { api } from '../api';
import StatusPill from '../components/StatusPill';
import type { Call, Property, StaffTraining, User } from '../types';
import ScheduleCall from './ScheduleCall';

const milestoneItems = [
  { title: 'E-Learning', subtitle: 'Done', date: 'Sep 22, 2026', status: 'complete' },
  { title: 'Training Call', subtitle: 'Oct 6, 2026', status: 'current' },
  { title: 'Configuration Call', subtitle: 'Oct 15, 2026', status: 'upcoming' },
  { title: 'Go-Live', subtitle: 'Nov 4, 2026', status: 'upcoming' },
  { title: 'Hypercare', subtitle: 'Nov 4 – 30, 2026', status: 'upcoming' },
];

export default function PropertyDashboard({ user, onOpenChat }: { user: User; onOpenChat?: () => void }) {
  const [properties, setProperties] = useState<Property[]>([]);
  const [training, setTraining] = useState<Record<string, StaffTraining[]>>({});
  const [calls, setCalls] = useState<Call[]>([]);
  const [selectedRescheduleCall, setSelectedRescheduleCall] = useState<Call | null>(null);
  const [activeTab, setActiveTab] = useState<'learning' | 'calls'>('calls');
  const [callType, setCallType] = useState<'first_call' | 'follow_up'>('first_call');
  const [error, setError] = useState('');

  async function load() {
    try {
      const props = await api.properties(user.id);
      setProperties(props);
      const callRows = await api.calls(user.id);
      setCalls(callRows);
      const entries = await Promise.all(props.map(async (property) => [property.id, await api.training(user.id, property.id)] as const));
      setTraining(Object.fromEntries(entries));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load dashboard');
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

  useEffect(() => { load(); }, [user.id]);

  const primaryProperty = properties[0];
  const propertyCalls = primaryProperty ? calls.filter((call) => call.property_id === primaryProperty.id) : [];
  const scheduledCalls = propertyCalls.filter((call) => call.status === 'scheduled');
  const nextCall = scheduledCalls.sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())[0];
  const upcomingCount = propertyCalls.filter((call) => ['scheduled', 'pending'].includes(call.status)).length;
  const learningRows = primaryProperty ? training[primaryProperty.id] ?? [] : [];
  const progress = learningRows.length ? Math.round(learningRows.reduce((sum, row) => sum + (row.training?.progress_percent ?? 0), 0) / learningRows.length) : 0;

  return (
    <main className="dashboard-layout">
      <div className="dashboard-main">
        <section className="card milestone-card">
          <div className="section-header">
            <div>
              <p className="eyebrow">Go-Live Milestones</p>
              <h2>Implementation progress</h2>
            </div>
            <div className="milestone-summary">
              <span className="summary-label">Target cutover</span>
              <strong>Nov 4, 2026</strong>
              <span className="summary-meta">23 days</span>
            </div>
          </div>
          <div className="milestone-grid">
            {milestoneItems.map((item) => (
              <div key={item.title} className={`milestone-step milestone-${item.status}`}>
                <div className="step-title">{item.title}</div>
                <div className="step-subtitle">{item.subtitle}</div>
              </div>
            ))}
          </div>
        </section>

        {primaryProperty && (
          <section className="card overview-card">
            <div className="row between">
              <div>
                <h3>{primaryProperty.name}</h3>
                <p className="muted">{primaryProperty.address}</p>
              </div>
              <StatusPill value={primaryProperty.transition_status} />
            </div>
            <div className="grid-3 overview-stats">
              <div>
                <span className="stat-label">Old tool ID</span>
                <strong>{primaryProperty.old_tool_property_id ?? '-'}</strong>
              </div>
              <div>
                <span className="stat-label">New tool ID</span>
                <strong>{primaryProperty.new_tool_property_id ?? '-'}</strong>
              </div>
              <div>
                <span className="stat-label">Upcoming calls</span>
                <strong>{upcomingCount}</strong>
              </div>
            </div>
            <div className="progress-row">
              <span>Overall readiness</span>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <span>{progress}%</span>
            </div>
            {onOpenChat ? (
              <button type="button" className="primary-button" onClick={onOpenChat}>
                Open chat with CMC
              </button>
            ) : null}
          </section>
        )}

        {primaryProperty && (
          <section className="card training-card">
            <div className="card-title-row">
              <h3>Training status</h3>
              <span>{learningRows.length} staff tracked</span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Progress</th>
                </tr>
              </thead>
              <tbody>
                {learningRows.map((row) => (
                  <tr key={row.user.id}>
                    <td>{row.user.full_name}</td>
                    <td>{row.title}</td>
                    <td><StatusPill value={row.training?.status ?? 'unknown'} /></td>
                    <td>{row.training?.progress_percent ?? 0}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>

      <aside className="dashboard-sidebar">
        <section className="card sidebar-card">
          <div className="tabs">
            <button type="button" className={activeTab === 'learning' ? 'tab active' : 'tab'} onClick={() => setActiveTab('learning')}>Learning Status</button>
            <button type="button" className={activeTab === 'calls' ? 'tab active' : 'tab'} onClick={() => setActiveTab('calls')}>Calls</button>
          </div>

          {activeTab === 'learning' ? (
            <div className="panel-content">
              <p className="muted">Review upcoming training and completion progress for your staff.</p>
              <div className="summary-block">
                <strong>{progress}%</strong>
                <span>Average training completion</span>
              </div>
            </div>
          ) : (
            <div className="panel-content">
              <div className="row between call-header-row">
                <h3>Call type</h3>
                <select value={callType} onChange={(event) => setCallType(event.target.value as 'first_call' | 'follow_up')}>
                  <option value="first_call">Training Call</option>
                  <option value="follow_up">Follow-up Call</option>
                </select>
              </div>
              <div className="call-card">
                <p className="muted uppercase">Next training call</p>
                {nextCall ? (
                  <>
                    <div className="call-time">{new Date(nextCall.start_time).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })} · {new Date(nextCall.start_time).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}</div>
                    <div className="row between">
                      <button type="button">Reschedule</button>
                      <span className="muted">{nextCall.status === 'scheduled' ? 'Confirmed' : 'Pending'}</span>
                    </div>
                    <button type="button" className="primary-button" disabled={!nextCall.zoom_join_url}>Join</button>
                    <div className="call-action-footer">
                      <button type="button" className="secondary-button">Summary</button>
                      <button type="button" className="secondary-button">Recording</button>
                    </div>
                  </>
                ) : (
                  <p className="muted">No scheduled call available yet.</p>
                )}
              </div>
            </div>
          )}
        </section>
      </aside>
    </main>
  );
}
