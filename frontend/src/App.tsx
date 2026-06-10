import { useEffect, useMemo, useState } from 'react';
import { api } from './api';
import type { User } from './types';
import AdminDashboard from './pages/AdminDashboard';
import ChatPage from './pages/ChatPage';
import CmcDashboard from './pages/CmcDashboard';
import PropertyDashboard from './pages/PropertyDashboard';

export default function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [activePage, setActivePage] = useState<'dashboard' | 'chat'>('dashboard');
  const selectedUser = useMemo(() => users.find((user) => user.id === selectedUserId), [users, selectedUserId]);

  useEffect(() => {
    api.users().then((seedUsers) => {
      setUsers(seedUsers);
      setSelectedUserId(seedUsers[0]?.id ?? '');
    });
  }, []);

  function renderContent() {
    if (!selectedUser) return <p>Select a user persona.</p>;
    if (activePage === 'chat') return <ChatPage user={selectedUser} />;
    if (selectedUser.is_admin || selectedUser.role === 'admin') return <AdminDashboard user={selectedUser} />;
    if (selectedUser.role === 'cmc') return <CmcDashboard user={selectedUser} onOpenChat={() => setActivePage('chat')} />;
    return <PropertyDashboard user={selectedUser} onOpenChat={() => setActivePage('chat')} />;
  }

  return (
    <div className="app-shell">
      <header className="portal-header">
        <div className="brand">
          <div className="brand-badge">Transition Hub</div>
        </div>
        <nav className="portal-nav" aria-label="Primary navigation">
          <button type="button" className={activePage === 'dashboard' ? 'nav-active' : ''} onClick={() => setActivePage('dashboard')}>Dashboard</button>
          <button type="button">Checklist</button>
          <button type="button">CMC Assignment</button>
          <button type="button">CMC Portfolio</button>
          <button type="button" className={activePage === 'chat' ? 'nav-active' : ''} onClick={() => setActivePage('chat')}>Chat</button>
        </nav>
        <div className="profile-panel">
          <span className="profile-name">{selectedUser?.full_name ?? 'Guest'}</span>
          <span className="profile-title">Your Change Management Coach</span>
        </div>
      </header>

      <section className="page-header">
        <div>
          <h1>Transition App</h1>
        </div>
        <label className="persona-label">
          Persona
          <select value={selectedUserId} onChange={(event) => setSelectedUserId(event.target.value)}>
            {users.map((user) => (
              <option key={user.id} value={user.id}>{user.full_name} - {user.role}{user.is_admin ? ' admin' : ''}</option>
            ))}
          </select>
        </label>
      </section>

      {renderContent()}
    </div>
  );
}
