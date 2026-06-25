import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Machine, Server, ServerCreate } from '../types'

const ENVS = ['development', 'staging', 'production']
const ENGINES = ['postgresql', 'pgvector', 'mysql', 'mongodb', 'qdrant']

const ENGINE_PORT: Record<string, number> = {
  postgresql: 5432, pgvector: 5432, mysql: 3306, mongodb: 27017, qdrant: 6333,
}

const ENGINE_DSN_PLACEHOLDER: Record<string, string> = {
  postgresql: 'postgresql://postgres:pass@host:5432/postgres',
  pgvector:   'postgresql://postgres:pass@host:5432/postgres',
  mysql:      'mysql://user:pass@host:3306/',
  mongodb:    'mongodb://admin:pass@host:27017/',
  qdrant:     'http://host:6333',
}

const ENGINE_DSN_LABEL: Record<string, string> = {
  qdrant: 'Connection URL',
}

const blank: ServerCreate = {
  name: '', host: '', port: 5432, engine: 'postgresql',
  environment: 'development', region: '', max_connections: 100, max_storage_gb: 100,
  warning_threshold_pct: 75, critical_threshold_pct: 90, machine_id: null,
}

export default function Servers() {
  const [servers, setServers] = useState<Server[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<ServerCreate>(blank)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [machines, setMachines] = useState<Machine[]>([])

  const load = () => {
    setLoading(true)
    Promise.all([
      api.servers.list(),
      api.machines.list(),
    ])
      .then(([data, mList]) => {
        setServers(data.filter(s => !s.is_deleted))
        setMachines(mList.filter(m => !m.is_deleted))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const set = (k: keyof ServerCreate, v: string | number) =>
    setForm(f => ({ ...f, [k]: v }))

  const onEngineChange = (engine: string) => {
    setForm(f => ({ ...f, engine, port: ENGINE_PORT[engine] ?? f.port }))
  }

  const openEdit = (s: Server) => {
    setEditingId(s.id)
    setForm({
      name: s.name, host: s.host, port: s.port, engine: s.engine,
      environment: s.environment, region: s.region ?? '',
      max_connections: s.max_connections, max_storage_gb: s.max_storage_gb,
      warning_threshold_pct: s.warning_threshold_pct,
      critical_threshold_pct: s.critical_threshold_pct,
      machine_id: s.machine_id ?? null,
    })
    setShowForm(true)
    setError('')
    setSuccess('')
  }

  const closeForm = () => {
    setShowForm(false); setEditingId(null); setForm(blank); setError(''); setSuccess('')
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const payload = { ...form, region: form.region || undefined }
      if (editingId !== null) {
        if (!payload.admin_dsn) delete payload.admin_dsn
        if (!payload.api_key) delete payload.api_key
        await api.servers.update(editingId, payload)
        setSuccess('Server updated.')
      } else {
        await api.servers.create(payload)
        setSuccess('Server registered.')
      }
      closeForm()
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSubmitting(false)
    }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Delete server "${name}"?`)) return
    try {
      await api.servers.remove(id)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const isQdrant = form.engine === 'qdrant'
  const dsnLabel = ENGINE_DSN_LABEL[form.engine] ?? 'Admin DSN'
  const dsnPlaceholder = editingId !== null
    ? 'Leave blank to keep current'
    : ENGINE_DSN_PLACEHOLDER[form.engine] ?? 'connection-string'

  return (
    <>
      <div className="row between mb-4">
        <h2 className="page-title" style={{ marginBottom: 0 }}>Servers</h2>
        <button className="btn btn-primary" onClick={() => showForm ? closeForm() : setShowForm(true)}>
          {showForm ? 'Cancel' : '+ Add Server'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showForm && (
        <div className="card mb-4">
          <div className="section-title mb-4" style={{ marginBottom: 16 }}>
            {editingId !== null ? 'Edit Server' : 'Register Server'}
          </div>
          <form onSubmit={submit}>
            <div className="grid-2">
              <div className="form-group">
                <label>Name *</label>
                <input required value={form.name} onChange={e => set('name', e.target.value)} placeholder="prod-pg-01" />
              </div>
              <div className="form-group">
                <label>Engine</label>
                <select value={form.engine} onChange={e => onEngineChange(e.target.value)}>
                  {ENGINES.map(eng => <option key={eng}>{eng}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Host *</label>
                <input required value={form.host} onChange={e => set('host', e.target.value)} placeholder="db.example.com" />
              </div>
              <div className="form-group">
                <label>Port</label>
                <input type="number" value={form.port} onChange={e => set('port', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>Environment *</label>
                <select value={form.environment} onChange={e => set('environment', e.target.value)}>
                  {ENVS.map(e => <option key={e}>{e}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Region</label>
                <input value={form.region ?? ''} onChange={e => set('region', e.target.value)} placeholder="us-east-1" />
              </div>
              <div className="form-group">
                <label>Max Connections</label>
                <input type="number" value={form.max_connections} onChange={e => set('max_connections', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>Max Storage (GB)</label>
                <input type="number" value={form.max_storage_gb} onChange={e => set('max_storage_gb', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>Warning threshold %</label>
                <input type="number" min={0} max={100} value={form.warning_threshold_pct} onChange={e => set('warning_threshold_pct', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>Critical threshold %</label>
                <input type="number" min={0} max={100} value={form.critical_threshold_pct} onChange={e => set('critical_threshold_pct', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>
                  {dsnLabel}
                  <span style={{ color: 'var(--muted)', fontSize: 11 }}> (required for provisioning)</span>
                </label>
                <input
                  type="password"
                  value={form.admin_dsn ?? ''}
                  onChange={e => set('admin_dsn', e.target.value)}
                  placeholder={dsnPlaceholder}
                />
              </div>
              {isQdrant && (
                <div className="form-group">
                  <label>
                    API Key
                    <span style={{ color: 'var(--muted)', fontSize: 11 }}> (optional — OSS Qdrant)</span>
                  </label>
                  <input
                    type="password"
                    value={form.api_key ?? ''}
                    onChange={e => set('api_key', e.target.value)}
                    placeholder={editingId !== null ? 'Leave blank to keep current' : 'qdrant-api-key'}
                  />
                </div>
              )}
              <div className="form-group">
                <label>
                  SSH Tunnel via Machine
                  <span style={{ color: 'var(--muted)', fontSize: 11 }}> (optional — host/port are as seen from the machine)</span>
                </label>
                <select
                  value={form.machine_id ?? ''}
                  onChange={e => setForm(f => ({ ...f, machine_id: e.target.value ? Number(e.target.value) : null }))}
                >
                  <option value="">— direct connection —</option>
                  {machines.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.label ?? m.ip} ({m.ip})
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="row gap-2 mt-4">
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                {submitting
                  ? (editingId !== null ? 'Saving…' : 'Registering…')
                  : (editingId !== null ? 'Save Changes' : 'Register Server')}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading servers…</div>
      ) : servers.length === 0 ? (
        <div className="empty">No servers registered yet.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Engine</th>
                <th>Host</th>
                <th>Environment</th>
                <th>Region</th>
                <th>Status</th>
                <th>Admin DSN</th>
                <th>Max Conn</th>
                <th>Warn / Crit %</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {servers.map(s => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 500 }}>{s.name}</td>
                  <td><span className="badge badge-inactive" style={{ fontSize: 11 }}>{s.engine}</span></td>
                  <td><code>{s.host}:{s.port}</code></td>
                  <td>{s.environment}</td>
                  <td>{s.region ?? '—'}</td>
                  <td>
                    <span className={`badge badge-${s.is_active ? 'active' : 'inactive'}`}>
                      {s.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    <span style={{ color: s.has_admin_dsn ? 'var(--green)' : 'var(--muted)', fontSize: 12 }}>
                      {s.has_admin_dsn ? 'Set' : 'Not set'}
                      {s.engine === 'qdrant' && s.has_api_key ? ' · key ✓' : ''}
                    </span>
                  </td>
                  <td>{s.max_connections}</td>
                  <td style={{ fontSize: 12 }}>{s.warning_threshold_pct}% / {s.critical_threshold_pct}%</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn btn-sm" style={{ marginRight: 6 }} onClick={() => openEdit(s)}>Edit</button>
                    <button className="btn btn-danger btn-sm" onClick={() => remove(s.id, s.name)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
