import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Server, ServerCreate } from '../types'

const ENVS = ['development', 'staging', 'production']
const blank: ServerCreate = {
  name: '', host: '', port: 5432, engine: 'postgresql',
  environment: 'development', region: '', max_connections: 100, max_storage_gb: 100,
}

export default function Servers() {
  const [servers, setServers] = useState<Server[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<ServerCreate>(blank)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = () => {
    setLoading(true)
    api.servers.list()
      .then(data => setServers(data.filter(s => !s.is_deleted)))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const set = (k: keyof ServerCreate, v: string | number) =>
    setForm(f => ({ ...f, [k]: v }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      await api.servers.create({ ...form, region: form.region || undefined })
      setSuccess('Server registered.')
      setShowForm(false)
      setForm(blank)
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

  return (
    <>
      <div className="row between mb-4">
        <h2 className="page-title" style={{ marginBottom: 0 }}>Servers</h2>
        <button className="btn btn-primary" onClick={() => { setShowForm(s => !s); setError(''); setSuccess('') }}>
          {showForm ? 'Cancel' : '+ Add Server'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showForm && (
        <div className="card mb-4">
          <div className="section-title mb-4" style={{ marginBottom: 16 }}>Register Server</div>
          <form onSubmit={submit}>
            <div className="grid-2">
              <div className="form-group">
                <label>Name *</label>
                <input required value={form.name} onChange={e => set('name', e.target.value)} placeholder="prod-pg-01" />
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
            </div>
            <div className="row gap-2 mt-4">
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                {submitting ? 'Registering…' : 'Register Server'}
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
                <th>Host</th>
                <th>Environment</th>
                <th>Region</th>
                <th>Status</th>
                <th>Max Conn</th>
                <th>Max GB</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {servers.map(s => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 500 }}>{s.name}</td>
                  <td><code>{s.host}:{s.port}</code></td>
                  <td>{s.environment}</td>
                  <td>{s.region ?? '—'}</td>
                  <td>
                    <span className={`badge badge-${s.is_active ? 'active' : 'inactive'}`}>
                      {s.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>{s.max_connections}</td>
                  <td>{s.max_storage_gb}</td>
                  <td>
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
