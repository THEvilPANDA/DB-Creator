import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Migration, Server, Site, SiteCreate, SiteDeployment } from '../types'

const EMPTY_FORM: SiteCreate = {
  name: '',
  template: '',
  subdomain: '',
  domain: '',
  prefix: '',
  routing_mode: 'port',
  app_port: undefined,
  web_root: '/var/www',
  directory: '',
  web_server: 'apache',
  notes: '',
}

export default function Sites() {
  const [sites, setSites] = useState<Site[]>([])
  const [servers, setServers] = useState<Server[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [form, setForm] = useState<SiteCreate>(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)

  // Migration panel state
  const [migrateSiteId, setMigrateSiteId] = useState<number | null>(null)
  const [deployments, setDeployments] = useState<SiteDeployment[]>([])
  const [targetServerId, setTargetServerId] = useState<number | ''>('')
  const [migration, setMigration] = useState<Migration | null>(null)
  const [migrating, setMigrating] = useState(false)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = () => {
    setLoading(true)
    Promise.all([api.sites.list(), api.servers.list()])
      .then(([s, srv]) => {
        setSites(s.filter(x => !x.is_deleted))
        setServers(srv.filter(x => !x.is_deleted))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const setF = <K extends keyof SiteCreate>(k: K, v: SiteCreate[K]) =>
    setForm(f => ({ ...f, [k]: v }))

  const openCreate = () => {
    setEditId(null)
    setForm(EMPTY_FORM)
    setShowForm(true)
    setError('')
    setSuccess('')
  }

  const openEdit = (s: Site) => {
    setEditId(s.id)
    setForm({
      name: s.name,
      template: s.template,
      subdomain: s.subdomain,
      domain: s.domain,
      prefix: s.prefix ?? '',
      routing_mode: s.routing_mode,
      app_port: s.app_port ?? undefined,
      web_root: s.web_root,
      directory: s.directory ?? '',
      web_server: s.web_server,
      notes: s.notes ?? '',
    })
    setShowForm(true)
    setError('')
    setSuccess('')
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true); setError(''); setSuccess('')
    const payload: SiteCreate = {
      ...form,
      prefix: form.prefix || undefined,
      directory: form.directory || undefined,
      notes: form.notes || undefined,
      app_port: form.routing_mode === 'port' ? form.app_port : undefined,
    }
    try {
      if (editId !== null) {
        await api.sites.update(editId, payload)
        setSuccess('Site updated.')
      } else {
        await api.sites.create(payload)
        setSuccess('Site created.')
      }
      setShowForm(false)
      setEditId(null)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSubmitting(false)
    }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Delete site "${name}"?`)) return
    try {
      await api.sites.remove(id)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const openMigrate = async (site: Site) => {
    setMigrateSiteId(site.id)
    setTargetServerId('')
    setMigration(null)
    setError('')
    try {
      const deps = await api.sites.deployments(site.id)
      setDeployments(deps)
    } catch {
      setDeployments([])
    }
  }

  const runMigrate = async () => {
    if (!migrateSiteId || targetServerId === '') return
    setMigrating(true); setError(''); setMigration(null)
    try {
      const result = await api.sites.migrate(migrateSiteId, targetServerId as number)
      setMigration(result)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setMigrating(false)
    }
  }

  const serverName = (id: number) =>
    servers.find(s => s.id === id)?.name ?? `Server #${id}`

  const STATUS_COLOR: Record<string, string> = {
    succeeded: 'var(--green)',
    failed: 'var(--red)',
    running: 'var(--accent)',
    pending: 'var(--muted)',
  }

  return (
    <>
      <h2 className="page-title">Sites</h2>

      <div className="row between mb-4" style={{ marginBottom: 16 }}>
        <div />
        <button
          className="btn btn-primary btn-sm"
          onClick={showForm && editId === null ? () => setShowForm(false) : openCreate}
        >
          {showForm && editId === null ? 'Cancel' : '+ New Site'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="section-title" style={{ marginBottom: 12 }}>
            {editId !== null ? 'Edit Site' : 'Create Site'}
          </div>
          <form onSubmit={submit}>
            <div className="grid-2">
              <div className="form-group">
                <label>Name *</label>
                <input required value={form.name} onChange={e => setF('name', e.target.value)} placeholder="My App" />
              </div>
              <div className="form-group">
                <label>Template *</label>
                <input required value={form.template} onChange={e => setF('template', e.target.value)} placeholder="laravel" />
              </div>
              <div className="form-group">
                <label>Subdomain *</label>
                <input required value={form.subdomain} onChange={e => setF('subdomain', e.target.value)} placeholder="app" />
              </div>
              <div className="form-group">
                <label>Domain *</label>
                <input required value={form.domain} onChange={e => setF('domain', e.target.value)} placeholder="example.com" />
              </div>
              <div className="form-group">
                <label>URL Prefix</label>
                <input value={form.prefix ?? ''} onChange={e => setF('prefix', e.target.value)} placeholder="/api" />
              </div>
              <div className="form-group">
                <label>Web Server</label>
                <select value={form.web_server ?? 'apache'} onChange={e => setF('web_server', e.target.value)}>
                  <option value="apache">Apache</option>
                  <option value="haproxy">HAProxy</option>
                </select>
              </div>
              <div className="form-group">
                <label>Routing Mode</label>
                <select value={form.routing_mode} onChange={e => setF('routing_mode', e.target.value)}>
                  <option value="port">Port proxy</option>
                  <option value="directory">Directory</option>
                </select>
              </div>
              {form.routing_mode === 'port' ? (
                <div className="form-group">
                  <label>App Port *</label>
                  <input
                    required
                    type="number"
                    value={form.app_port ?? ''}
                    onChange={e => setF('app_port', e.target.value ? Number(e.target.value) : undefined)}
                    placeholder="4007"
                  />
                </div>
              ) : (
                <div className="form-group">
                  <label>Directory *</label>
                  <input
                    required
                    value={form.directory ?? ''}
                    onChange={e => setF('directory', e.target.value)}
                    placeholder="myapp"
                  />
                </div>
              )}
              <div className="form-group">
                <label>Web Root</label>
                <input value={form.web_root ?? '/var/www'} onChange={e => setF('web_root', e.target.value)} />
              </div>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label>Notes</label>
                <textarea rows={2} value={form.notes ?? ''} onChange={e => setF('notes', e.target.value)}
                  style={{ width: '100%', resize: 'vertical' }} />
              </div>
            </div>
            <div className="row gap-2" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                {submitting ? 'Saving…' : editId !== null ? 'Update Site' : 'Create Site'}
              </button>
              <button className="btn" type="button" onClick={() => { setShowForm(false); setEditId(null) }}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {migrateSiteId !== null && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="row between" style={{ marginBottom: 12 }}>
            <div className="section-title" style={{ marginBottom: 0 }}>
              Migrate: {sites.find(s => s.id === migrateSiteId)?.name}
            </div>
            <button className="btn btn-sm" onClick={() => { setMigrateSiteId(null); setMigration(null) }}>
              Close
            </button>
          </div>
          {deployments.filter(d => d.status === 'active').length > 0 && (
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>
              Current server: <strong>{serverName(deployments.find(d => d.status === 'active')!.server_id)}</strong>
            </div>
          )}
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label>Target Server *</label>
            <select
              value={targetServerId}
              onChange={e => setTargetServerId(e.target.value ? Number(e.target.value) : '')}
            >
              <option value="">— select a server —</option>
              {servers.map(s => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.environment} · {s.host})
                </option>
              ))}
            </select>
          </div>
          <button
            className="btn btn-primary btn-sm"
            disabled={migrating || targetServerId === ''}
            onClick={runMigrate}
          >
            {migrating ? 'Migrating…' : 'Run Migration'}
          </button>
          {migration && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                Status:{' '}
                <span style={{ color: STATUS_COLOR[migration.status] ?? 'var(--muted)' }}>
                  {migration.status}
                </span>
              </div>
              {migration.error_message && (
                <div className="alert alert-error" style={{ marginBottom: 8 }}>
                  {migration.error_message}
                </div>
              )}
              {migration.log && (
                <pre style={{
                  background: 'var(--surface)', border: '1px solid var(--border)',
                  borderRadius: 4, padding: 10, fontSize: 11,
                  overflowX: 'auto', whiteSpace: 'pre-wrap', maxHeight: 240,
                }}>
                  {migration.log}
                </pre>
              )}
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="loading">Loading…</div>
      ) : sites.length === 0 ? (
        <div className="empty">No sites defined. Create one above.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name / URL</th>
                <th>Template</th>
                <th>Web Server</th>
                <th>Routing</th>
                <th>Notes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sites.map(s => (
                <tr key={s.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{s.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                      {s.subdomain}.{s.domain}
                      {s.prefix && <span> {s.prefix}</span>}
                    </div>
                  </td>
                  <td style={{ fontSize: 12 }}>{s.template}</td>
                  <td style={{ fontSize: 12 }}>{s.web_server}</td>
                  <td style={{ fontSize: 12 }}>
                    {s.routing_mode === 'port' ? `port:${s.app_port}` : `dir:${s.directory}`}
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--muted)', maxWidth: 160 }}>
                    {s.notes ?? '—'}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn btn-sm" style={{ marginRight: 4 }} onClick={() => openEdit(s)}>
                      Edit
                    </button>
                    <button
                      className="btn btn-sm"
                      style={{ marginRight: 4 }}
                      onClick={() => migrateSiteId === s.id ? setMigrateSiteId(null) : openMigrate(s)}
                    >
                      {migrateSiteId === s.id ? 'Close' : 'Migrate'}
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => remove(s.id, s.name)}>
                      Delete
                    </button>
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
