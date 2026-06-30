import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import Login from './pages/Login'
import Servers from './pages/Servers'
import Settings from './pages/Settings'
import Sites from './pages/Sites'
import Systems from './pages/Systems'
import { auth } from './api'

type Page = 'dashboard' | 'servers' | 'jobs' | 'sites' | 'systems' | 'settings'

const NAV: { id: Page; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: '⬡' },
  { id: 'servers', label: 'Servers', icon: '◫' },
  { id: 'jobs', label: 'Jobs', icon: '⟳' },
  { id: 'sites', label: 'Sites', icon: '◍' },
  { id: 'systems', label: 'Systems', icon: '⬕' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]

export default function App() {
  const [authenticated, setAuthenticated] = useState(auth.isAuthenticated())
  const [page, setPage] = useState<Page>('dashboard')

  if (!authenticated) {
    return <Login onAuthenticated={() => setAuthenticated(true)} />
  }

  function handleLogout() {
    auth.clearTokens()
    setAuthenticated(false)
  }

  return (
    <>
      <nav className="sidebar">
        <div className="sidebar-logo">
          <h1>DB Creator</h1>
          <span>Enterprise Provisioning</span>
        </div>
        <div className="sidebar-nav">
          {NAV.map(n => (
            <button
              key={n.id}
              className={`nav-item${page === n.id ? ' active' : ''}`}
              onClick={() => setPage(n.id)}
            >
              <span style={{ fontSize: 16, lineHeight: 1 }}>{n.icon}</span>
              {n.label}
            </button>
          ))}
        </div>
        <div style={{ padding: '1rem 0.75rem', borderTop: '1px solid var(--border)' }}>
          <button
            onClick={handleLogout}
            style={{
              width: '100%', padding: '6px 10px', borderRadius: 4, border: '1px solid var(--border)',
              background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 12,
            }}
          >
            Sign Out
          </button>
        </div>
      </nav>
      <main className="main">
        {page === 'dashboard' && <Dashboard />}
        {page === 'servers' && <Servers />}
        {page === 'jobs' && <Jobs />}
        {page === 'sites' && <Sites />}
        {page === 'systems' && <Systems />}
        {page === 'settings' && <Settings />}
      </main>
    </>
  )
}
