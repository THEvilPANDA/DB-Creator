import { useEffect, useState } from 'react'
import { api } from '../api'
import type { CreationLog, Job, JobCreate, Server } from '../types'

const ENVS = ['development', 'staging', 'production']
const blank: JobCreate = { db_name: '', environment: 'development', owner: '', team: '', cost_center: '' }

function statusBadge(status: string) {
  return <span className={`badge badge-${status}`}>{status}</span>
}

export default function Jobs() {
  const [servers, setServers] = useState<Server[]>([])
  const [history, setHistory] = useState<CreationLog[]>([])
  const [histTotal, setHistTotal] = useState(0)
  const [form, setForm] = useState<JobCreate & { server_id_str: string }>({ ...blank, server_id_str: '' })
  const [submitting, setSubmitting] = useState(false)
  const [lastJob, setLastJob] = useState<Job | null>(null)
  const [error, setError] = useState('')
  const [histError, setHistError] = useState('')
  const [histLoading, setHistLoading] = useState(true)

  const loadHistory = () => {
    setHistLoading(true)
    api.history()
      .then(r => { setHistory(r.items); setHistTotal(r.total) })
      .catch(e => setHistError(e.message))
      .finally(() => setHistLoading(false))
  }

  useEffect(() => {
    api.servers.list().then(s => setServers(s.filter(x => !x.is_deleted))).catch(() => {})
    loadHistory()
  }, [])

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setLastJob(null)
    try {
      const payload: JobCreate = {
        environment: form.environment,
        owner: form.owner,
        db_name: form.db_name || undefined,
        team: form.team || undefined,
        cost_center: form.cost_center || undefined,
        server_id: form.server_id_str ? Number(form.server_id_str) : undefined,
      }
      const job = await api.jobs.submit(payload)
      setLastJob(job)
      setForm({ ...blank, server_id_str: '' })
      loadHistory()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <h2 className="page-title">Jobs</h2>

      {/* Submit form */}
      <div className="card mb-4" style={{ marginBottom: 24 }}>
        <div className="section-title" style={{ marginBottom: 16 }}>Submit Provisioning Request</div>

        {error && <div className="alert alert-error">{error}</div>}
        {lastJob && (
          <div className="alert alert-success">
            Job #{lastJob.id} submitted — status: <strong>{lastJob.status}</strong>
            {lastJob.status === 'queued' ? ' (auto-approved, worker will provision)' : ' (awaiting approval)'}
          </div>
        )}

        <form onSubmit={submit}>
          <div className="grid-2">
            <div className="form-group">
              <label>DB Name (optional — auto-generated if blank)</label>
              <input value={form.db_name ?? ''} onChange={e => set('db_name', e.target.value)} placeholder="my_app_db" />
            </div>
            <div className="form-group">
              <label>Environment *</label>
              <select value={form.environment} onChange={e => set('environment', e.target.value)}>
                {ENVS.map(e => <option key={e}>{e}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Owner *</label>
              <input required value={form.owner} onChange={e => set('owner', e.target.value)} placeholder="alice" />
            </div>
            <div className="form-group">
              <label>Team</label>
              <input value={form.team ?? ''} onChange={e => set('team', e.target.value)} placeholder="platform" />
            </div>
            <div className="form-group">
              <label>Cost Center</label>
              <input value={form.cost_center ?? ''} onChange={e => set('cost_center', e.target.value)} placeholder="CC-4200" />
            </div>
            <div className="form-group">
              <label>Target Server (optional)</label>
              <select value={form.server_id_str} onChange={e => set('server_id_str', e.target.value)}>
                <option value="">— any —</option>
                {servers.map(s => (
                  <option key={s.id} value={String(s.id)}>{s.name} ({s.environment})</option>
                ))}
              </select>
            </div>
          </div>
          <div className="mt-4">
            <button className="btn btn-primary" type="submit" disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit Request'}
            </button>
            <span style={{ marginLeft: 12, fontSize: 12, color: 'var(--muted)' }}>
              dev/staging = auto-approved · production = requires approval
            </span>
          </div>
        </form>
      </div>

      {/* History */}
      <div className="row between mb-4">
        <div className="section-title">Provisioning History {histTotal > 0 && <span style={{ color: 'var(--muted)', fontWeight: 400, fontSize: 13 }}>({histTotal})</span>}</div>
        <button className="btn btn-secondary btn-sm" onClick={loadHistory}>Refresh</button>
      </div>

      {histError && <div className="alert alert-error">{histError}</div>}

      {histLoading ? (
        <div className="loading">Loading history…</div>
      ) : history.length === 0 ? (
        <div className="empty">No provisioned databases yet.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>DB Name</th>
                <th>Job ID</th>
                <th>User</th>
                <th>Server ID</th>
                <th>Connection URI</th>
                <th>Provisioned</th>
              </tr>
            </thead>
            <tbody>
              {history.map(log => (
                <tr key={log.id}>
                  <td style={{ fontWeight: 500 }}>{log.db_name}</td>
                  <td><code>#{log.job_id}</code></td>
                  <td>{log.db_user ?? '—'}</td>
                  <td>{log.server_id}</td>
                  <td style={{ maxWidth: 260 }}>
                    {log.connection_uri ? <code>{log.connection_uri}</code> : '—'}
                  </td>
                  <td style={{ color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                    {new Date(log.provisioned_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Live job lookup */}
      <JobLookup />
    </>
  )
}

function JobLookup() {
  const [jobId, setJobId] = useState('')
  const [job, setJob] = useState<Job | null>(null)
  const [err, setErr] = useState('')

  const lookup = async () => {
    const id = Number(jobId)
    if (!id) return
    setErr('')
    setJob(null)
    api.jobs.get(id).then(setJob).catch(e => setErr(e.message))
  }

  return (
    <div className="card mt-6" style={{ marginTop: 24 }}>
      <div className="section-title" style={{ marginBottom: 12 }}>Look Up Job</div>
      <div className="row gap-2">
        <input
          style={{ maxWidth: 120 }}
          type="number"
          placeholder="Job ID"
          value={jobId}
          onChange={e => setJobId(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && lookup()}
        />
        <button className="btn btn-secondary btn-sm" onClick={lookup}>Look up</button>
      </div>
      {err && <div className="alert alert-error mt-4" style={{ marginTop: 12 }}>{err}</div>}
      {job && (
        <div style={{ marginTop: 12, fontSize: 13 }}>
          <div className="row gap-2" style={{ marginBottom: 6 }}>
            <strong>#{job.id}</strong>
            {statusBadge(job.status)}
            <span style={{ color: 'var(--muted)' }}>{job.environment}</span>
          </div>
          <div>DB: <code>{job.db_name}</code> · Owner: {job.owner}</div>
          {job.error_message && <div style={{ color: 'var(--red)', marginTop: 4 }}>{job.error_message}</div>}
        </div>
      )}
    </div>
  )
}
