import { useEffect, useState } from 'react'
import { api } from '../api'
import type { EngineDetectionResult, Machine, MachineCreate, ScanResult, SSHKey, SSHKeyCreate } from '../types'

type Tab = 'sshkeys' | 'machines'

// ── SSH Keys ──────────────────────────────────────────────────────────────────

function SSHKeys() {
  const [items, setItems] = useState<SSHKey[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<SSHKeyCreate>({ name: '', username: '', private_key: '' })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = () => {
    setLoading(true)
    api.sshKeys.list().then(setItems).catch(e => setError(e.message)).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const set = (k: keyof SSHKeyCreate, v: string) => setForm(f => ({ ...f, [k]: v }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true); setError(''); setSuccess('')
    try {
      await api.sshKeys.create({ ...form, passphrase: form.passphrase || undefined })
      setSuccess('SSH key saved.')
      setShowForm(false)
      setForm({ name: '', username: '', private_key: '' })
      load()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setSubmitting(false) }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Delete SSH key "${name}"?`)) return
    try { await api.sshKeys.delete(id); load() }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
  }

  return (
    <div>
      <div className="row between mb-4" style={{ marginBottom: 16 }}>
        <div className="section-title" style={{ marginBottom: 0 }}>SSH Keys</div>
        <button className="btn btn-primary btn-sm" onClick={() => { setShowForm(s => !s); setError(''); setSuccess('') }}>
          {showForm ? 'Cancel' : '+ Add Key'}
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
                <input required value={form.name} onChange={e => set('name', e.target.value)} placeholder="prod-deploy-key" />
              </div>
              <div className="form-group">
                <label>SSH Username *</label>
                <input required value={form.username} onChange={e => set('username', e.target.value)} placeholder="ubuntu" />
              </div>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label>Private Key (PEM) * <span style={{ color: 'var(--muted)', fontSize: 11 }}>write-only — not shown after save</span></label>
                <textarea
                  required rows={6}
                  value={form.private_key}
                  onChange={e => set('private_key', e.target.value)}
                  placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;..."
                  style={{ fontFamily: 'monospace', fontSize: 12, width: '100%', resize: 'vertical' }}
                />
              </div>
              <div className="form-group">
                <label>Passphrase <span style={{ color: 'var(--muted)', fontSize: 11 }}>(optional)</span></label>
                <input type="password" value={form.passphrase ?? ''} onChange={e => set('passphrase', e.target.value)} />
              </div>
            </div>
            <div className="row gap-2 mt-4" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                {submitting ? 'Saving…' : 'Save Key'}
              </button>
            </div>
          </form>
        </div>
      )}
      {loading ? <div className="loading">Loading…</div> : items.length === 0 ? (
        <div className="empty">No SSH keys configured.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Username</th><th>Added</th><th></th></tr></thead>
            <tbody>
              {items.map(k => (
                <tr key={k.id}>
                  <td style={{ fontWeight: 500 }}>{k.name}</td>
                  <td><code>{k.username}</code></td>
                  <td style={{ color: 'var(--muted)', fontSize: 12 }}>{new Date(k.created_at).toLocaleDateString()}</td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => remove(k.id, k.name)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Machines ──────────────────────────────────────────────────────────────────

function Machines() {
  const [machines, setMachines] = useState<Machine[]>([])
  const [sshKeys, setSshKeys] = useState<SSHKey[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [showScan, setShowScan] = useState(false)
  const [form, setForm] = useState<MachineCreate>({ ip: '', ssh_port: 22, ssh_key_id: 0 })
  const [scanForm, setScanForm] = useState({ cidr: '', method: 'port22' })
  const [scanResults, setScanResults] = useState<ScanResult[] | null>(null)
  const [scanning, setScanning] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [checking, setChecking] = useState<number | null>(null)
  const [detecting, setDetecting] = useState<number | null>(null)
  const [detectResults, setDetectResults] = useState<{ machineId: number; results: EngineDetectionResult[] } | null>(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = () => {
    setLoading(true)
    Promise.all([api.machines.list(), api.sshKeys.list()])
      .then(([m, k]) => { setMachines(m.filter(x => !x.is_deleted)); setSshKeys(k) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const setF = (k: keyof MachineCreate, v: string | number) => setForm(f => ({ ...f, [k]: v }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true); setError(''); setSuccess('')
    try {
      await api.machines.create({ ...form, label: form.label || undefined })
      setSuccess('Machine registered.')
      setShowForm(false)
      setForm({ ip: '', ssh_port: 22, ssh_key_id: 0 })
      load()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setSubmitting(false) }
  }

  const check = async (id: number) => {
    setChecking(id); setError(''); setSuccess('')
    try {
      await api.machines.check(id)
      setSuccess('Connectivity check complete.')
      load()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setChecking(null) }
  }

  const detectEngines = async (id: number) => {
    setDetecting(id); setError('')
    try {
      const results = await api.machines.detectEngines(id)
      setDetectResults({ machineId: id, results })
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setDetecting(null) }
  }

  const remove = async (id: number) => {
    if (!confirm('Delete this machine?')) return
    try { await api.machines.delete(id); load() }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
  }

  const runScan = async (e: React.FormEvent) => {
    e.preventDefault()
    setScanning(true); setScanResults(null); setError('')
    try {
      const results = await api.machines.scan(scanForm)
      setScanResults(results)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setScanning(false) }
  }

  const STATUS_COLOR: Record<string, string> = {
    online: 'var(--green)', offline: 'var(--red)', unknown: 'var(--muted)'
  }

  return (
    <div>
      <div className="row between mb-4" style={{ marginBottom: 16 }}>
        <div className="section-title" style={{ marginBottom: 0 }}>Machines</div>
        <div className="row gap-2">
          <button className="btn btn-sm" onClick={() => { setShowScan(s => !s); setError('') }}>
            {showScan ? 'Close Scan' : 'Scan Network'}
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => { setShowForm(s => !s); setError('') }}>
            {showForm ? 'Cancel' : '+ Add Machine'}
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showScan && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="section-title" style={{ marginBottom: 12, fontSize: 14 }}>Network Scan</div>
          <form onSubmit={runScan}>
            <div className="grid-2">
              <div className="form-group">
                <label>CIDR Range *</label>
                <input required value={scanForm.cidr} onChange={e => setScanForm(f => ({ ...f, cidr: e.target.value }))}
                  placeholder="192.168.1.0/24" />
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>Private IP ranges only (RFC-1918)</div>
              </div>
              <div className="form-group">
                <label>Scan Method</label>
                <select value={scanForm.method} onChange={e => setScanForm(f => ({ ...f, method: e.target.value }))}>
                  <option value="port22">Port 22 only</option>
                  <option value="ping">Ping sweep only</option>
                  <option value="both">Ping + Port 22</option>
                </select>
              </div>
            </div>
            <button className="btn btn-primary btn-sm" type="submit" disabled={scanning}>
              {scanning ? 'Scanning…' : 'Start Scan'}
            </button>
          </form>
          {scanResults && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                {scanResults.filter(r => r.ssh_open || r.ping_ok).length} hosts found
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>IP</th><th>Ping</th><th>SSH (22)</th><th></th></tr></thead>
                  <tbody>
                    {scanResults.map(r => (
                      <tr key={r.ip}>
                        <td><code>{r.ip}</code></td>
                        <td style={{ color: r.ping_ok ? 'var(--green)' : 'var(--muted)' }}>{r.ping_ok ? '✓' : '—'}</td>
                        <td style={{ color: r.ssh_open ? 'var(--green)' : 'var(--muted)' }}>{r.ssh_open ? '✓' : '—'}</td>
                        <td>
                          {(r.ping_ok || r.ssh_open) && sshKeys.length > 0 && (
                            <button className="btn btn-sm" onClick={() => {
                              setForm(f => ({ ...f, ip: r.ip }))
                              setShowForm(true)
                            }}>Add</button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <form onSubmit={submit}>
            <div className="grid-2">
              <div className="form-group">
                <label>IP Address *</label>
                <input required value={form.ip} onChange={e => setF('ip', e.target.value)} placeholder="192.168.1.10" />
              </div>
              <div className="form-group">
                <label>SSH Port</label>
                <input type="number" value={form.ssh_port} onChange={e => setF('ssh_port', Number(e.target.value))} />
              </div>
              <div className="form-group">
                <label>SSH Key *</label>
                <select required value={form.ssh_key_id} onChange={e => setF('ssh_key_id', Number(e.target.value))}>
                  <option value={0}>— select key —</option>
                  {sshKeys.map(k => <option key={k.id} value={k.id}>{k.name} ({k.username})</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Label</label>
                <input value={form.label ?? ''} onChange={e => setF('label', e.target.value)} placeholder="dev-box" />
              </div>
            </div>
            <div className="row gap-2 mt-4" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" type="submit" disabled={submitting || form.ssh_key_id === 0}>
                {submitting ? 'Adding…' : 'Add Machine'}
              </button>
            </div>
          </form>
        </div>
      )}

      {detectResults && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="row between" style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>
              Detected engines on {machines.find(m => m.id === detectResults.machineId)?.ip}
            </div>
            <button className="btn btn-sm" onClick={() => setDetectResults(null)}>Close</button>
          </div>
          <table>
            <thead><tr><th>Port</th><th>Engine</th><th>Status</th></tr></thead>
            <tbody>
              {detectResults.results.map(r => (
                <tr key={r.port}>
                  <td><code>{r.port}</code></td>
                  <td>{r.engine}</td>
                  <td style={{ color: r.open ? 'var(--green)' : 'var(--muted)' }}>
                    {r.open ? 'Listening' : 'Not found'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {loading ? <div className="loading">Loading…</div> : machines.length === 0 ? (
        <div className="empty">No machines registered. Add one manually or use Scan Network.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>IP / Label</th><th>Hostname</th><th>Status</th>
                <th>SSH Key</th><th>Last Checked</th><th></th>
              </tr>
            </thead>
            <tbody>
              {machines.map(m => (
                <tr key={m.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{m.label ?? m.ip}</div>
                    {m.label && <div style={{ fontSize: 11, color: 'var(--muted)' }}>{m.ip}</div>}
                  </td>
                  <td style={{ color: 'var(--muted)' }}>{m.hostname ?? '—'}</td>
                  <td>
                    <span style={{ color: STATUS_COLOR[m.status] ?? 'var(--muted)', fontSize: 13 }}>
                      ● {m.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 12 }}>
                    {sshKeys.find(k => k.id === m.ssh_key_id)?.name ?? `#${m.ssh_key_id}`}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--muted)' }}>
                    {m.last_checked_at ? new Date(m.last_checked_at).toLocaleString() : '—'}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button
                      className="btn btn-sm"
                      style={{ marginRight: 4 }}
                      disabled={checking === m.id}
                      onClick={() => check(m.id)}
                    >
                      {checking === m.id ? 'Checking…' : 'Check'}
                    </button>
                    <button
                      className="btn btn-sm"
                      style={{ marginRight: 4 }}
                      disabled={detecting === m.id}
                      onClick={() => detectEngines(m.id)}
                    >
                      {detecting === m.id ? 'Detecting…' : 'Detect Engines'}
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => remove(m.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Systems root ──────────────────────────────────────────────────────────────

export default function Systems() {
  const [tab, setTab] = useState<Tab>('sshkeys')

  const TABS: { id: Tab; label: string }[] = [
    { id: 'sshkeys', label: 'SSH Keys' },
    { id: 'machines', label: 'Machines' },
  ]

  return (
    <>
      <h2 className="page-title">Systems</h2>
      <div className="row gap-2" style={{ marginBottom: 24, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            padding: '8px 16px', fontSize: 13, fontWeight: tab === t.id ? 600 : 400,
            color: tab === t.id ? 'var(--accent)' : 'var(--muted)',
            borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
            marginBottom: -1,
          }}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'sshkeys' && <SSHKeys />}
      {tab === 'machines' && <Machines />}
    </>
  )
}
