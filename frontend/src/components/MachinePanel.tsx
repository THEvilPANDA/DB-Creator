import { useState, useEffect } from 'react'
import { api, auth, BASE } from '../api'
import type { EngineDetectionResult, Machine, Server, SSHKey } from '../types'
import Terminal from './Terminal'

interface Props {
  machine: Machine
  sshKeys: SSHKey[]
  onClose: () => void
  onServerRegistered: () => void
}

type Tab = 'engines' | 'terminal' | 'install' | 'sql'

const ENGINE_COLORS: Record<string, string> = {
  postgresql: '#336791',
  mysql: '#4479a1',
  mongodb: '#47a248',
  qdrant: '#dc244c',
  chroma: '#e16a2d',
}

const INSTALLABLE_ENGINES = ['postgresql', 'mysql', 'mongodb', 'qdrant', 'chroma']

export default function MachinePanel({ machine, sshKeys: _sshKeys, onClose, onServerRegistered }: Props) {
  const [tab, setTab] = useState<Tab>('engines')
  const [engines, setEngines] = useState<EngineDetectionResult[] | null>(null)
  const [detecting, setDetecting] = useState(false)
  const [detectError, setDetectError] = useState('')

  const [installing, setInstalling] = useState<string | null>(null)
  const [installLog, setInstallLog] = useState<{ type: string; data: string }[]>([])

  const [registering, setRegistering] = useState<string | null>(null)
  const [registerError, setRegisterError] = useState('')
  const [registerSuccess, setRegisterSuccess] = useState('')
  const [registerForm, setRegisterForm] = useState<string | null>(null) // engine key of open form
  const [regEnv, setRegEnv] = useState('production')
  const [regRegion, setRegRegion] = useState('')
  const [regName, setRegName] = useState('')

  const [sqlEnabled, setSqlEnabled] = useState(false)
  const [linkedServers, setLinkedServers] = useState<Server[]>([])
  const [selectedServer, setSelectedServer] = useState<number | null>(null)
  const [sqlQuery, setSqlQuery] = useState('')
  const [sqlRunning, setSqlRunning] = useState(false)
  const [sqlResult, setSqlResult] = useState<{ columns: string[]; rows: unknown[][] } | null>(null)
  const [sqlError, setSqlError] = useState('')

  useEffect(() => {
    detectEngines()
    api.servers.list().then(servers => {
      const linked = servers.filter(s => !s.is_deleted && s.machine_id === machine.id)
      setLinkedServers(linked)
      if (linked.length > 0 && !selectedServer) setSelectedServer(linked[0].id)
    }).catch(() => {})
  }, [machine.id])

  useEffect(() => {
    if (tab === 'sql') {
      api.servers.list().then(servers => {
        const linked = servers.filter(s => !s.is_deleted && s.machine_id === machine.id)
        setLinkedServers(linked)
        if (linked.length > 0 && !selectedServer) setSelectedServer(linked[0].id)
      }).catch(() => {})
    }
  }, [tab, machine.id])

  const detectEngines = async () => {
    setDetecting(true); setDetectError('')
    try {
      const result = await api.machines.detectEngines(machine.id)
      setEngines(result)
    } catch (e: unknown) {
      setDetectError(e instanceof Error ? e.message : String(e))
    } finally {
      setDetecting(false)
    }
  }

  const registerAsServer = async (eng: EngineDetectionResult, name: string, environment: string, region: string) => {
    const portMap: Record<string, number> = { postgresql: 5432, mysql: 3306, mongodb: 27017, qdrant: 6333, chroma: 8001 }
    setRegistering(eng.engine); setRegisterError(''); setRegisterSuccess('')
    try {
      await api.servers.create({
        name,
        host: 'localhost',
        port: portMap[eng.engine] ?? eng.port,
        engine: eng.engine,
        environment,
        ...(region ? { region } : {}),
        max_connections: 100,
        max_storage_gb: 100,
        warning_threshold_pct: 75,
        critical_threshold_pct: 90,
        machine_id: machine.id,
      })
      setRegisterSuccess(`${eng.engine} registered as server`)
      setRegisterForm(null)
      onServerRegistered()
      const updated = await api.servers.list()
      setLinkedServers(updated.filter(s => !s.is_deleted && s.machine_id === machine.id))
    } catch (e: unknown) {
      setRegisterError(e instanceof Error ? e.message : String(e))
    } finally {
      setRegistering(null)
    }
  }

  const openRegisterForm = (eng: EngineDetectionResult) => {
    setRegisterForm(eng.engine)
    setRegName(`${machine.label ?? machine.ip}-${eng.engine}`)
    setRegEnv('production')
    setRegRegion('')
    setRegisterError('')
    setRegisterSuccess('')
  }

  const installDb = async (engine: string, action: 'install' | 'uninstall' = 'install') => {
    setInstalling(action === 'install' ? engine : `uninstall-${engine}`); setInstallLog([])
    const token = auth.getToken()
    const url = `${BASE}/machines/${machine.id}/install-db?engine=${encodeURIComponent(engine)}&action=${action}`
    try {
      const response = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!response.ok) throw new Error(`${response.status}`)
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const msg = JSON.parse(line.slice(6)) as { type: string; data: string }
          setInstallLog(prev => [...prev, msg])
          if (msg.type === 'done' || msg.type === 'error') { setInstalling(null); return }
        }
      }
    } catch (e: unknown) {
      setInstallLog(prev => [...prev, { type: 'error', data: e instanceof Error ? e.message : String(e) }])
    } finally {
      setInstalling(null)
    }
  }

  const runSql = async () => {
    if (!selectedServer || !sqlQuery.trim()) return
    setSqlRunning(true); setSqlError(''); setSqlResult(null)
    try {
      const result = await api.sql.query(selectedServer, sqlQuery)
      if (result.error) setSqlError(result.error)
      else setSqlResult({ columns: result.columns, rows: result.rows })
    } catch (e: unknown) {
      setSqlError(e instanceof Error ? e.message : String(e))
    } finally {
      setSqlRunning(false)
    }
  }

  const token = auth.getToken() ?? ''
  const wsUrl = `${BASE.replace(/^http/, 'ws')}/machines/${machine.id}/terminal?token=${encodeURIComponent(token)}`

  const TABS: { id: Tab; label: string }[] = [
    { id: 'engines', label: 'Engines' },
    { id: 'terminal', label: 'Terminal' },
    { id: 'install', label: 'Install DB' },
    { id: 'sql', label: 'SQL' },
  ]

  const Spinner = ({ size = 18 }: { size?: number }) => (
    <div style={{
      width: size, height: size, borderRadius: '50%', flexShrink: 0,
      border: `${size <= 18 ? 2 : 3}px solid var(--border)`,
      borderTop: `${size <= 18 ? 2 : 3}px solid var(--green)`,
      animation: 'panel-spin 0.7s linear infinite',
    }} />
  )

  const SkeletonCard = ({ delay = 0 }: { delay?: number }) => (
    <div style={{
      height: 72, borderRadius: 6, marginBottom: 8,
      background: 'linear-gradient(90deg, var(--surface) 0%, var(--border) 50%, var(--surface) 100%)',
      backgroundSize: '400px 100%',
      animation: `panel-shimmer 1.4s ease-in-out ${delay}s infinite`,
    }} />
  )

  return (
    <div style={{
      position: 'fixed', right: 0, top: 0, bottom: 0, width: '70vw', minWidth: 700,
      background: 'var(--bg)', borderLeft: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', zIndex: 200,
      boxShadow: '-4px 0 24px rgba(0,0,0,0.4)',
    }}>
      <style>{`
        @keyframes panel-spin { to { transform: rotate(360deg); } }
        @keyframes panel-shimmer {
          0% { background-position: -400px 0; }
          100% { background-position: 400px 0; }
        }
      `}</style>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid var(--border)', gap: 12, flexShrink: 0 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{machine.label ?? machine.ip}</div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>{machine.ip} · port {machine.ssh_port} · {machine.status}</div>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: 20, cursor: 'pointer', padding: '0 4px', lineHeight: 1 }}>×</button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            style={{ padding: '8px 16px', fontSize: 13, border: 'none', borderBottom: tab === t.id ? '2px solid var(--green)' : '2px solid transparent', background: 'none', color: tab === t.id ? 'var(--green)' : 'var(--muted)', cursor: 'pointer' }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: tab === 'terminal' ? 'hidden' : 'auto', display: 'flex', flexDirection: 'column' }}>

        {/* ENGINES */}
        {tab === 'engines' && (
          <div style={{ padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ fontWeight: 600 }}>Detected Database Engines</div>
              <button className="btn btn-primary btn-sm" onClick={detectEngines} disabled={detecting}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {detecting ? <><Spinner size={12} /> Detecting…</> : 'Re-detect'}
              </button>
            </div>
            {detectError && <div className="alert alert-error" style={{ marginBottom: 12 }}>{detectError}</div>}
            {registerError && <div className="alert alert-error" style={{ marginBottom: 12 }}>{registerError}</div>}
            {registerSuccess && <div className="alert alert-success" style={{ marginBottom: 12 }}>{registerSuccess}</div>}
            {detecting && engines === null && (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, color: 'var(--muted)', fontSize: 13 }}>
                  <Spinner size={16} />
                  Scanning for database engines via SSH…
                </div>
                {[0, 0.1, 0.2, 0.3].map((delay, i) => <SkeletonCard key={i} delay={delay} />)}
              </>
            )}
            {!detecting && engines === null && (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>Detection failed. Click Re-detect to try again.</div>
            )}
            {engines !== null && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {engines.map(eng => (
                  <div key={eng.engine} style={{ border: '1px solid var(--border)', borderRadius: 6, background: 'var(--surface)', overflow: 'hidden' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: 12 }}>
                      <div style={{ width: 10, height: 10, borderRadius: '50%', background: eng.open ? (ENGINE_COLORS[eng.engine] ?? 'var(--green)') : 'var(--muted)', marginTop: 4, flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>
                          {eng.engine} <span style={{ fontSize: 11, color: 'var(--muted)' }}>:{eng.port}</span>
                        </div>
                        {eng.version && <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{eng.version}</div>}
                        {eng.databases.length > 0 && (
                          <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                            {eng.databases.map(db => (
                              <span key={db} style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, background: 'var(--bg)', border: '1px solid var(--border)' }}>{db}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div style={{ fontSize: 11, color: eng.open ? 'var(--green)' : 'var(--muted)', marginTop: 4, whiteSpace: 'nowrap' }}>
                        {eng.open ? 'Running' : 'Not running'}
                      </div>
                      {eng.open && !linkedServers.some(s => s.engine === eng.engine) && registerForm !== eng.engine && (
                        <button className="btn btn-sm" onClick={() => openRegisterForm(eng)}>
                          Register as Server
                        </button>
                      )}
                      {eng.open && linkedServers.some(s => s.engine === eng.engine) && (
                        <span style={{ fontSize: 11, color: 'var(--green)', marginTop: 4 }}>✓ Registered</span>
                      )}
                    </div>
                    {registerForm === eng.engine && (
                      <div style={{ borderTop: '1px solid var(--border)', padding: '12px 12px 14px 34px', background: 'var(--bg)', display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', marginBottom: 2 }}>Register as Server</div>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <div style={{ flex: 2, minWidth: 160 }}>
                            <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 3 }}>Server name</label>
                            <input
                              value={regName}
                              onChange={e => setRegName(e.target.value)}
                              style={{ width: '100%', fontSize: 12, padding: '5px 8px' }}
                            />
                          </div>
                          <div style={{ flex: 1, minWidth: 120 }}>
                            <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 3 }}>Environment</label>
                            <select value={regEnv} onChange={e => setRegEnv(e.target.value)} style={{ width: '100%', fontSize: 12, padding: '5px 8px' }}>
                              <option value="production">Production</option>
                              <option value="staging">Staging</option>
                              <option value="development">Development</option>
                              <option value="test">Test</option>
                            </select>
                          </div>
                          <div style={{ flex: 1, minWidth: 120 }}>
                            <label style={{ fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 3 }}>Region <span style={{ fontStyle: 'italic' }}>(optional)</span></label>
                            <input
                              value={regRegion}
                              onChange={e => setRegRegion(e.target.value)}
                              placeholder="e.g. us-east-1"
                              style={{ width: '100%', fontSize: 12, padding: '5px 8px' }}
                            />
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => registerAsServer(eng, regName.trim() || `${machine.label ?? machine.ip}-${eng.engine}`, regEnv, regRegion.trim())}
                            disabled={registering === eng.engine}
                          >
                            {registering === eng.engine ? <><Spinner size={12} /> Registering…</> : 'Register'}
                          </button>
                          <button className="btn btn-sm" onClick={() => setRegisterForm(null)} disabled={registering === eng.engine}>
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TERMINAL */}
        {tab === 'terminal' && <Terminal wsUrl={wsUrl} onClose={onClose} />}

        {/* INSTALL DB */}
        {tab === 'install' && (
          <div style={{ padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ fontWeight: 600 }}>Install / Uninstall Database Engines</div>
              {detecting && engines !== null && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--muted)' }}>
                  <Spinner size={12} /> Re-detecting…
                </div>
              )}
            </div>
            {detecting && engines === null && (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, color: 'var(--muted)', fontSize: 13 }}>
                  <Spinner size={16} />
                  Scanning engines via SSH…
                </div>
                {[0, 0.1, 0.2, 0.3].map((delay, i) => <SkeletonCard key={i} delay={delay} />)}
              </>
            )}
            {!detecting && engines === null && (
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>Detection failed. Switch to Engines tab and Re-detect first.</div>
            )}
            {engines !== null && (
            <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
              {INSTALLABLE_ENGINES.map(eng => {
                const detected = engines?.find(e => e.engine === eng)
                const isRunning = detected?.open === true
                const isInstalling = installing === eng
                const isUninstalling = installing === `uninstall-${eng}`
                return (
                  <div key={eng} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                    <span style={{ fontSize: 10, color: isRunning ? 'var(--green)' : 'var(--muted)' }}>
                      {isRunning ? '● running' : '○ not running'}
                    </span>
                    {isRunning ? (
                      <button className="btn btn-sm btn-danger" onClick={() => installDb(eng, 'uninstall')} disabled={!!installing}>
                        {isUninstalling ? 'Removing…' : `Uninstall ${eng}`}
                      </button>
                    ) : (
                      <button className="btn btn-sm" onClick={() => installDb(eng, 'install')} disabled={!!installing || detecting}>
                        {isInstalling ? `Installing…` : `Install ${eng}`}
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
            )}
            {installLog.length > 0 && (
              <div style={{ background: '#0d1117', border: '1px solid var(--border)', borderRadius: 6, padding: 12, fontFamily: 'monospace', fontSize: 12, maxHeight: 400, overflowY: 'auto' }}>
                {installLog.map((entry, i) => (
                  <div key={i} style={{ marginBottom: 2, color: entry.type === 'error' ? 'var(--red)' : entry.type === 'done' ? 'var(--green)' : entry.type === 'cmd' ? '#58a6ff' : '#c9d1d9' }}>
                    {entry.type === 'cmd' ? `$ ${entry.data}` : entry.data}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* SQL */}
        {tab === 'sql' && (
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {linkedServers.length === 0 ? (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>
                No servers registered for this machine. Go to the <strong>Engines</strong> tab, detect running databases, then click "Register as Server".
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <select value={selectedServer ?? ''} onChange={e => setSelectedServer(Number(e.target.value))} style={{ flex: 1 }}>
                    {linkedServers.map(s => <option key={s.id} value={s.id}>{s.name} ({s.engine})</option>)}
                  </select>
                  {!sqlEnabled
                    ? <button className="btn btn-sm" onClick={() => setSqlEnabled(true)}>Enable SQL</button>
                    : <button className="btn btn-danger btn-sm" onClick={() => setSqlEnabled(false)}>Disable SQL</button>
                  }
                </div>
                {sqlEnabled && (
                  <>
                    <textarea
                      value={sqlQuery}
                      onChange={e => setSqlQuery(e.target.value)}
                      placeholder="SELECT * FROM ..."
                      rows={5}
                      style={{ fontFamily: 'monospace', fontSize: 12, resize: 'vertical' }}
                    />
                    <div>
                      <button className="btn btn-primary btn-sm" onClick={runSql} disabled={sqlRunning || !sqlQuery.trim()}>
                        {sqlRunning ? 'Running…' : 'Run Query'}
                      </button>
                    </div>
                    {sqlError && <div className="alert alert-error">{sqlError}</div>}
                    {sqlResult && (
                      <div className="table-wrap" style={{ maxHeight: 400, overflowY: 'auto' }}>
                        <table>
                          <thead>
                            <tr>{sqlResult.columns.map(c => <th key={c}>{c}</th>)}</tr>
                          </thead>
                          <tbody>
                            {sqlResult.rows.map((row, i) => (
                              <tr key={i}>{(row as unknown[]).map((cell, j) => <td key={j}>{String(cell ?? '')}</td>)}</tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
