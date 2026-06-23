import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import Servers from './pages/Servers'
import Settings from './pages/Settings'

type Page = 'dashboard' | 'servers' | 'jobs' | 'settings'

const NAV: { id: Page; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: '⬡' },
  { id: 'servers', label: 'Servers', icon: '◫' },
  { id: 'jobs', label: 'Jobs', icon: '⟳' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')

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
      </nav>
      <main className="main">
        {page === 'dashboard' && <Dashboard />}
        {page === 'servers' && <Servers />}
        {page === 'jobs' && <Jobs />}
        {page === 'settings' && <Settings />}
      </main>
    </>
  )
}
