import { useEffect, useState } from 'react'
import { api } from '../api'
import type { HealthCheck } from '../types'

interface Checks {
  app: HealthCheck | null
  db: HealthCheck | null
  queue: HealthCheck | null
}

function HealthCard({ name, check }: { name: string; check: HealthCheck | null }) {
  const ok = check?.status === 'ok'
  const loading = check === null
  return (
    <div className="card">
      <div className="health-name">{name}</div>
      {loading ? (
        <div style={{ color: 'var(--muted)', fontSize: 13 }}>Checking…</div>
      ) : (
        <>
          <div className="row gap-2">
            <span className={`dot dot-${ok ? 'ok' : 'error'}`} />
            <span className="health-status" style={{ color: ok ? 'var(--green)' : 'var(--red)' }}>
              {check.status.toUpperCase()}
            </span>
          </div>
          {check.environment && (
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 6 }}>
              env: {check.environment}
            </div>
          )}
          {check.detail && (
            <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 6 }}>{check.detail}</div>
          )}
        </>
      )}
    </div>
  )
}

export default function Dashboard() {
  const [checks, setChecks] = useState<Checks>({ app: null, db: null, queue: null })

  const runChecks = () => {
    setChecks({ app: null, db: null, queue: null })
    api.health.app().then(app => setChecks(c => ({ ...c, app }))).catch(() =>
      setChecks(c => ({ ...c, app: { status: 'error', detail: 'unreachable' } }))
    )
    api.health.db().then(db => setChecks(c => ({ ...c, db }))).catch(() =>
      setChecks(c => ({ ...c, db: { status: 'error', detail: 'unreachable' } }))
    )
    api.health.queue().then(queue => setChecks(c => ({ ...c, queue }))).catch(() =>
      setChecks(c => ({ ...c, queue: { status: 'error', detail: 'unreachable' } }))
    )
  }

  useEffect(() => { runChecks() }, [])

  return (
    <>
      <div className="row between mb-4">
        <h2 className="page-title" style={{ marginBottom: 0 }}>Dashboard</h2>
        <button className="btn btn-secondary btn-sm" onClick={runChecks}>Refresh</button>
      </div>

      <div className="grid-3">
        <HealthCard name="API" check={checks.app} />
        <HealthCard name="Database" check={checks.db} />
        <HealthCard name="Queue (Redis)" check={checks.queue} />
      </div>

      <div className="mt-6" style={{ color: 'var(--muted)', fontSize: 13 }}>
        <p>OpenAPI docs available at <code>/docs</code> when the backend is running.</p>
        <p style={{ marginTop: 8 }}>Use the <strong>Servers</strong> tab to register target PostgreSQL servers, then <strong>Jobs</strong> to provision a new database.</p>
      </div>
    </>
  )
}
