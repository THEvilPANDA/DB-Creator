import { useEffect, useState } from 'react'
import { api } from '../api'
import type { HealthCheck, Stats } from '../types'

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

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="card" style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--accent)', lineHeight: 1.1 }}>{value}</div>
      <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 6 }}>{label}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const [checks, setChecks] = useState<Checks>({ app: null, db: null, queue: null })
  const [stats, setStats] = useState<Stats | null>(null)
  const [statsErr, setStatsErr] = useState('')

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

  const loadStats = () => {
    setStatsErr('')
    api.stats()
      .then(setStats)
      .catch(e => setStatsErr(e.message))
  }

  const refresh = () => { runChecks(); loadStats() }

  useEffect(() => { runChecks(); loadStats() }, [])

  const envBreakdown = stats
    ? Object.entries(stats.jobs.by_environment)
        .sort(([, a], [, b]) => b - a)
        .map(([env, count]) => `${env}: ${count}`)
        .join(' · ')
    : null

  return (
    <>
      <div className="row between mb-4">
        <h2 className="page-title" style={{ marginBottom: 0 }}>Dashboard</h2>
        <button className="btn btn-secondary btn-sm" onClick={refresh}>Refresh</button>
      </div>

      {/* Service health */}
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Service Health</div>
      <div className="grid-3">
        <HealthCard name="API" check={checks.app} />
        <HealthCard name="Database" check={checks.db} />
        <HealthCard name="Queue (Redis)" check={checks.queue} />
      </div>

      {/* Platform stats */}
      <div style={{ fontSize: 12, color: 'var(--muted)', margin: '24px 0 8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Platform Stats</div>
      {statsErr ? (
        <div className="alert alert-error">{statsErr}</div>
      ) : (
        <div className="grid-3" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <StatCard
            label="Databases Provisioned"
            value={stats ? stats.history.total_provisioned : '…'}
          />
          <StatCard
            label="Total Jobs"
            value={stats ? stats.jobs.total : '…'}
            sub={envBreakdown ?? undefined}
          />
          <StatCard
            label="Success Rate"
            value={stats ? `${stats.jobs.success_rate_pct}%` : '…'}
            sub={stats ? `${stats.jobs.by_status['succeeded'] ?? 0} succeeded · ${stats.jobs.by_status['failed'] ?? 0} failed` : undefined}
          />
          <StatCard
            label="Active Servers"
            value={stats ? `${stats.servers.active} / ${stats.servers.total}` : '…'}
          />
        </div>
      )}

      {/* Status breakdown */}
      {stats && stats.jobs.total > 0 && (
        <div className="card mt-6" style={{ marginTop: 20 }}>
          <div className="section-title" style={{ marginBottom: 12 }}>Jobs by Status</div>
          <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
            {Object.entries(stats.jobs.by_status).map(([s, n]) => (
              <span key={s} className={`badge badge-${s}`} style={{ fontSize: 13 }}>
                {s} {n}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-6" style={{ color: 'var(--muted)', fontSize: 13, marginTop: 20 }}>
        <p>OpenAPI docs at <code>/docs</code> · Prometheus metrics at <code>/metrics</code></p>
        <p style={{ marginTop: 8 }}>Start the monitoring stack with <code>docker compose --profile monitoring up</code> to enable Grafana (port 3001) and Prometheus (port 9090).</p>
      </div>
    </>
  )
}
