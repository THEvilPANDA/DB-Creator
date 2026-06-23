import { useEffect, useState } from 'react'
import { api } from '../api'
import type {
  ApprovalPolicy, DBTemplate, DBTemplateCreate,
  NamingProfile, NamingProfileCreate,
  RequestTemplate, RequestTemplateCreate,
} from '../types'

type Tab = 'naming' | 'dbtemplates' | 'reqtemplates' | 'policy'

const TABS: { id: Tab; label: string }[] = [
  { id: 'naming', label: 'Naming Profiles' },
  { id: 'dbtemplates', label: 'DB Templates' },
  { id: 'reqtemplates', label: 'Request Templates' },
  { id: 'policy', label: 'Approval Policy' },
]

const ENVS = ['development', 'staging', 'production']
const ALLOWED_EXTENSIONS = [
  'uuid-ossp', 'pgcrypto', 'hstore', 'pg_trgm', 'btree_gin', 'btree_gist',
  'postgis', 'citext', 'ltree', 'tablefunc', 'unaccent', 'pg_stat_statements',
  'vector', 'intarray', 'lo',
]

// ── Naming Profiles ───────────────────────────────────────────────────────────

function NamingProfiles() {
  const [items, setItems] = useState<NamingProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<NamingProfileCreate & { reserved_str: string }>({
    name: '', pattern: '{environment}_{owner}_{db_name}', separator: '_',
    allow_collision: false, reserved_str: 'postgres,template0,template1',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = () => {
    setLoading(true)
    api.naming.list().then(setItems).catch(e => setError(e.message)).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const set = (k: string, v: string | boolean) => setForm(f => ({ ...f, [k]: v }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true); setError(''); setSuccess('')
    try {
      await api.naming.create({
        name: form.name,
        pattern: form.pattern,
        prefix: form.prefix || undefined,
        suffix: form.suffix || undefined,
        separator: form.separator ?? '_',
        reserved_names: form.reserved_str ? form.reserved_str.split(',').map(s => s.trim()).filter(Boolean) : [],
        allow_collision: form.allow_collision,
        description: form.description || undefined,
      })
      setSuccess('Profile created.')
      setShowForm(false)
      setForm({ name: '', pattern: '{environment}_{owner}_{db_name}', separator: '_', allow_collision: false, reserved_str: 'postgres,template0,template1' })
      load()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setSubmitting(false) }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Delete naming profile "${name}"?`)) return
    try { await api.naming.delete(id); load() }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
  }

  return (
    <div>
      <div className="row between mb-4" style={{ marginBottom: 16 }}>
        <div className="section-title" style={{ marginBottom: 0 }}>Naming Profiles</div>
        <button className="btn btn-primary btn-sm" onClick={() => { setShowForm(s => !s); setError(''); setSuccess('') }}>
          {showForm ? 'Cancel' : '+ New Profile'}
        </button>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <form onSubmit={submit}>
            <div className="grid-2">
              <div className="form-group">
                <label>Name *</label>
                <input required value={form.name} onChange={e => set('name', e.target.value)} placeholder="my-profile" />
              </div>
              <div className="form-group">
                <label>Pattern * <span style={{ color: 'var(--muted)', fontSize: 11 }}>vars: {'{owner} {team} {environment} {db_name}'}</span></label>
                <input required value={form.pattern} onChange={e => set('pattern', e.target.value)} />
              </div>
              <div className="form-group">
                <label>Prefix</label>
                <input value={form.prefix ?? ''} onChange={e => set('prefix', e.target.value)} placeholder="optional" />
              </div>
              <div className="form-group">
                <label>Suffix</label>
                <input value={form.suffix ?? ''} onChange={e => set('suffix', e.target.value)} placeholder="optional" />
              </div>
              <div className="form-group">
                <label>Separator</label>
                <input value={form.separator ?? '_'} onChange={e => set('separator', e.target.value)} placeholder="_" style={{ maxWidth: 60 }} />
              </div>
              <div className="form-group">
                <label>Reserved names <span style={{ color: 'var(--muted)', fontSize: 11 }}>(comma-separated)</span></label>
                <input value={form.reserved_str} onChange={e => set('reserved_str', e.target.value)} />
              </div>
              <div className="form-group">
                <label>Description</label>
                <input value={form.description ?? ''} onChange={e => set('description', e.target.value)} />
              </div>
              <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 24 }}>
                <input type="checkbox" id="np-collision" checked={!!form.allow_collision}
                  onChange={e => set('allow_collision', e.target.checked)} />
                <label htmlFor="np-collision" style={{ marginBottom: 0 }}>Allow name collision</label>
              </div>
            </div>
            <div className="row gap-2 mt-4" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                {submitting ? 'Creating…' : 'Create Profile'}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? <div className="loading">Loading…</div> : items.length === 0 ? (
        <div className="empty">No naming profiles. Create one or run <code>POST /api/v1/admin/seed</code>.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr>
              <th>Name</th><th>Pattern</th><th>Separator</th><th>Collision</th><th>Description</th><th></th>
            </tr></thead>
            <tbody>
              {items.map(p => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 500 }}>{p.name}</td>
                  <td><code>{p.pattern}</code></td>
                  <td><code>{JSON.stringify(p.separator)}</code></td>
                  <td>{p.allow_collision ? 'Yes' : 'No'}</td>
                  <td style={{ color: 'var(--muted)' }}>{p.description ?? '—'}</td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => remove(p.id, p.name)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Database Templates ────────────────────────────────────────────────────────

function DatabaseTemplates() {
  const [items, setItems] = useState<DBTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<DBTemplateCreate & { ext_str: string; privs_str: string }>({
    name: '', extensions: [], permissions: {}, ext_str: '', privs_str: 'CONNECT,USAGE,CREATE',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = () => {
    setLoading(true)
    api.dbTemplates.list().then(setItems).catch(e => setError(e.message)).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true); setError(''); setSuccess('')
    const exts = form.ext_str ? form.ext_str.split(',').map(s => s.trim()).filter(Boolean) : []
    const privs = form.privs_str ? form.privs_str.split(',').map(s => s.trim()).filter(Boolean) : []
    try {
      await api.dbTemplates.create({
        name: form.name,
        description: form.description || undefined,
        extensions: exts,
        permissions: privs.length ? { app_user: privs } : {},
      })
      setSuccess('Template created.')
      setShowForm(false)
      setForm({ name: '', extensions: [], permissions: {}, ext_str: '', privs_str: 'CONNECT,USAGE,CREATE' })
      load()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setSubmitting(false) }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Delete template "${name}"?`)) return
    try { await api.dbTemplates.delete(id); load() }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
  }

  return (
    <div>
      <div className="row between mb-4" style={{ marginBottom: 16 }}>
        <div className="section-title" style={{ marginBottom: 0 }}>Database Templates</div>
        <button className="btn btn-primary btn-sm" onClick={() => { setShowForm(s => !s); setError(''); setSuccess('') }}>
          {showForm ? 'Cancel' : '+ New Template'}
        </button>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <form onSubmit={submit}>
            <div className="grid-2">
              <div className="form-group">
                <label>Name *</label>
                <input required value={form.name} onChange={e => set('name', e.target.value)} placeholder="my-template" />
              </div>
              <div className="form-group">
                <label>Description</label>
                <input value={form.description ?? ''} onChange={e => set('description', e.target.value)} />
              </div>
              <div className="form-group">
                <label>Extensions <span style={{ color: 'var(--muted)', fontSize: 11 }}>(comma-separated)</span></label>
                <input value={form.ext_str} onChange={e => set('ext_str', e.target.value)}
                  placeholder="uuid-ossp, vector, pg_trgm" />
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
                  Allowed: {ALLOWED_EXTENSIONS.join(', ')}
                </div>
              </div>
              <div className="form-group">
                <label>App User Privileges <span style={{ color: 'var(--muted)', fontSize: 11 }}>(comma-separated)</span></label>
                <input value={form.privs_str} onChange={e => set('privs_str', e.target.value)}
                  placeholder="CONNECT,USAGE,CREATE" />
              </div>
            </div>
            <div className="row gap-2 mt-4" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                {submitting ? 'Creating…' : 'Create Template'}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? <div className="loading">Loading…</div> : items.length === 0 ? (
        <div className="empty">No database templates. Run <code>POST /api/v1/admin/seed</code> to load defaults.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr>
              <th>Name</th><th>Description</th><th>Extensions</th><th>App User Privileges</th><th></th>
            </tr></thead>
            <tbody>
              {items.map(t => (
                <tr key={t.id}>
                  <td style={{ fontWeight: 500 }}>{t.name}</td>
                  <td style={{ color: 'var(--muted)' }}>{t.description ?? '—'}</td>
                  <td><code style={{ fontSize: 11 }}>{t.extensions.join(', ') || '—'}</code></td>
                  <td><code style={{ fontSize: 11 }}>{(t.permissions?.app_user ?? []).join(', ') || '—'}</code></td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => remove(t.id, t.name)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Request Templates ─────────────────────────────────────────────────────────

function RequestTemplates() {
  const [items, setItems] = useState<RequestTemplate[]>([])
  const [dbTemplates, setDbTemplates] = useState<DBTemplate[]>([])
  const [namingProfiles, setNamingProfiles] = useState<NamingProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const blankForm: RequestTemplateCreate & { db_tmpl_str: string; np_str: string } = {
    name: '', environment: 'development', expiration_days: 90, db_tmpl_str: '', np_str: '',
  }
  const [form, setForm] = useState(blankForm)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = () => {
    setLoading(true)
    Promise.all([
      api.requestTemplates.list(),
      api.dbTemplates.list(),
      api.naming.list(),
    ])
      .then(([rt, dt, np]) => { setItems(rt); setDbTemplates(dt); setNamingProfiles(np) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const set = (k: string, v: string | number) => setForm(f => ({ ...f, [k]: v }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true); setError(''); setSuccess('')
    try {
      await api.requestTemplates.create({
        name: form.name,
        description: form.description || undefined,
        environment: form.environment,
        db_template_id: form.db_tmpl_str ? Number(form.db_tmpl_str) : undefined,
        naming_profile_id: form.np_str ? Number(form.np_str) : undefined,
        expiration_days: Number(form.expiration_days) || 90,
        team: form.team || undefined,
        cost_center: form.cost_center || undefined,
      })
      setSuccess('Request template created.')
      setShowForm(false)
      setForm(blankForm)
      load()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setSubmitting(false) }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Delete request template "${name}"?`)) return
    try { await api.requestTemplates.delete(id); load() }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
  }

  const tmplName = (id: number | null) => dbTemplates.find(t => t.id === id)?.name ?? '—'
  const npName = (id: number | null) => namingProfiles.find(p => p.id === id)?.name ?? '—'

  return (
    <div>
      <div className="row between mb-4" style={{ marginBottom: 16 }}>
        <div className="section-title" style={{ marginBottom: 0 }}>Request Templates</div>
        <button className="btn btn-primary btn-sm" onClick={() => { setShowForm(s => !s); setError(''); setSuccess('') }}>
          {showForm ? 'Cancel' : '+ New Template'}
        </button>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <form onSubmit={submit}>
            <div className="grid-2">
              <div className="form-group">
                <label>Name *</label>
                <input required value={form.name} onChange={e => set('name', e.target.value)} placeholder="team-dev-standard" />
              </div>
              <div className="form-group">
                <label>Environment *</label>
                <select value={form.environment} onChange={e => set('environment', e.target.value)}>
                  {ENVS.map(e => <option key={e}>{e}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>DB Template</label>
                <select value={form.db_tmpl_str} onChange={e => set('db_tmpl_str', e.target.value)}>
                  <option value="">— none —</option>
                  {dbTemplates.map(t => <option key={t.id} value={String(t.id)}>{t.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Naming Profile</label>
                <select value={form.np_str} onChange={e => set('np_str', e.target.value)}>
                  <option value="">— none —</option>
                  {namingProfiles.map(p => <option key={p.id} value={String(p.id)}>{p.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Expiry (days)</label>
                <input type="number" value={form.expiration_days} onChange={e => set('expiration_days', e.target.value)} />
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
                <label>Description</label>
                <input value={form.description ?? ''} onChange={e => set('description', e.target.value)} />
              </div>
            </div>
            <div className="row gap-2 mt-4" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                {submitting ? 'Creating…' : 'Create Request Template'}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? <div className="loading">Loading…</div> : items.length === 0 ? (
        <div className="empty">No request templates yet. Create one to pre-fill job submissions.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr>
              <th>Name</th><th>Env</th><th>DB Template</th><th>Naming Profile</th><th>Expiry</th><th>Team</th><th></th>
            </tr></thead>
            <tbody>
              {items.map(t => (
                <tr key={t.id}>
                  <td style={{ fontWeight: 500 }}>{t.name}</td>
                  <td>{t.environment}</td>
                  <td>{tmplName(t.db_template_id)}</td>
                  <td>{npName(t.naming_profile_id)}</td>
                  <td>{t.expiration_days}d</td>
                  <td style={{ color: 'var(--muted)' }}>{t.team ?? '—'}</td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => remove(t.id, t.name)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Approval Policy ───────────────────────────────────────────────────────────

function ApprovalPolicySection() {
  const [policy, setPolicy] = useState<ApprovalPolicy | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    api.admin.getApprovalPolicy()
      .then(p => { setPolicy(p); setSelected(new Set(p.auto_approved_environments)) })
      .catch(e => setError(e.message))
  }, [])

  const toggle = (env: string) =>
    setSelected(s => { const n = new Set(s); n.has(env) ? n.delete(env) : n.add(env); return n })

  const save = async () => {
    setSaving(true); setError(''); setSuccess('')
    try {
      const updated = await api.admin.setApprovalPolicy([...selected])
      setPolicy(updated)
      setSuccess('Policy saved. Takes effect immediately for new job submissions.')
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setSaving(false) }
  }

  return (
    <div>
      <div className="section-title" style={{ marginBottom: 16 }}>Approval Policy</div>
      <div style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 20 }}>
        Jobs submitted for auto-approved environments skip the manual approval queue and are enqueued immediately.
        Changes apply in-process only and reset on API restart (Phase 7 will persist to DB).
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {!policy ? (
        <div className="loading">Loading policy…</div>
      ) : (
        <div className="card" style={{ maxWidth: 400 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Auto-approved environments</div>
          {ENVS.map(env => (
            <div key={env} className="row gap-2" style={{ marginBottom: 10 }}>
              <input type="checkbox" id={`env-${env}`} checked={selected.has(env)} onChange={() => toggle(env)} />
              <label htmlFor={`env-${env}`} style={{ marginBottom: 0, cursor: 'pointer' }}>
                {env}
                {env === 'production' && (
                  <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--red)' }}>caution — skips approval</span>
                )}
              </label>
            </div>
          ))}
          <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save Policy'}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Settings root ─────────────────────────────────────────────────────────────

export default function Settings() {
  const [tab, setTab] = useState<Tab>('naming')

  return (
    <>
      <h2 className="page-title">Settings</h2>

      <div className="row gap-2" style={{ marginBottom: 24, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: '8px 16px', fontSize: 13, fontWeight: tab === t.id ? 600 : 400,
              color: tab === t.id ? 'var(--accent)' : 'var(--muted)',
              borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'naming' && <NamingProfiles />}
      {tab === 'dbtemplates' && <DatabaseTemplates />}
      {tab === 'reqtemplates' && <RequestTemplates />}
      {tab === 'policy' && <ApprovalPolicySection />}
    </>
  )
}
