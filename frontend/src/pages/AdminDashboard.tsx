import { useEffect, useState } from 'react';
import { api } from '../api';
import StatusPill from '../components/StatusPill';
import type { AdminDashboard as AdminDashboardType, User } from '../types';

export default function AdminDashboard({ user }: { user: User }) {
  const [dashboard, setDashboard] = useState<AdminDashboardType | null>(null);
  const [selectedCmc, setSelectedCmc] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');

  async function load() {
    setDashboard(await api.adminDashboard(user.id));
  }

  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [user.id]);

  async function reassign(propertyId: string) {
    const newCmcUserId = selectedCmc[propertyId];
    if (!newCmcUserId) return;
    try {
      const result = await api.reassign(user.id, propertyId, newCmcUserId);
      setMessage(`Reassigned. Future calls transferred: ${result.future_calls_transferred}`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to reassign');
    }
  }

  if (!dashboard) return <main><p>Loading...</p>{message && <p className="message">{message}</p>}</main>;

  return (
    <main>
      <h2>Admin dashboard</h2>
      {message && <p className="message">{message}</p>}
      <section className="stats">
        <div><strong>{dashboard.counts.properties}</strong><span>Properties</span></div>
        <div><strong>{dashboard.counts.staff_users}</strong><span>Staff/owners</span></div>
        <div><strong>{dashboard.counts.cmcs}</strong><span>CMCs</span></div>
        <div><strong>{dashboard.counts.scheduled_calls}</strong><span>Scheduled calls</span></div>
      </section>
      <section className="card">
        <h3>Properties and CMC reassignment</h3>
        <table>
          <thead><tr><th>Property</th><th>Status</th><th>Assign to</th><th>Action</th></tr></thead>
          <tbody>
            {dashboard.properties.map((property) => (
              <tr key={property.id}>
                <td>{property.name}</td>
                <td><StatusPill value={property.transition_status} /></td>
                <td>
                  <select value={selectedCmc[property.id] ?? ''} onChange={(event) => setSelectedCmc({ ...selectedCmc, [property.id]: event.target.value })}>
                    <option value="">Select CMC</option>
                    {dashboard.cmcs.map((cmc) => <option key={cmc.id} value={cmc.id}>{cmc.full_name}</option>)}
                  </select>
                </td>
                <td><button onClick={() => reassign(property.id)}>Reassign</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
