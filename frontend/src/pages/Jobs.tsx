import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { CreationLog, Job, JobCreate, QueryResult, Server } from '../types'

const ENVS = ['development', 'staging', 'production']
const STATUSES = ['pending', 'queued', 'running', 'succeeded', 'failed', 'cancelled']
const blank: JobCreate = { db_name: '', environment: 'development', owner: '', team: '', cost_center: '' }

function statusBadge(status: string) {
  return <span className={`badge badge-${status}`}>{status}</span>
}

export default function Jobs() {
  const [servers, setServers] = useState<Server[]>([])
  const [history, setHistory] = useState<CreationLog[]>([])
  const [histTotal, setHistTotal] = useState(0)
  const [consoleLog, setConsoleLog] = useState<CreationLog | null>(null)
  const consoleRef = useRef<HTMLDivElement>(null)
  const [form, setForm] = useState<JobCreate & { server_id_str: string }>({ ...blank, server_id_str: '' })
  const [submitting, setSubmitting] = useState(false)
  const [lastJob, setLastJob] = useState<Job | null>(null)
  const [error, setError] = useState('')
  const [histError, setHistError] = useState('')
  const [histLoading, setHistLoading] = useState(true)
  const [filterEnv, setFilterEnv] = useState('')
  const [filterStatus, setFilterStatus] = useState('')

  const loadHistory = (env = filterEnv, status = filterStatus) => {
    setHistLoading(true)
    api.history(1, 20, env || undefined, status || undefined)
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
          <div className="alert alert-success" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div className="row gap-2" style={{ alignItems: 'center' }}>
              <strong>Job #{lastJob.id}</strong>
              {statusBadge(lastJob.status)}
              <span style={{ color: 'var(--muted)', fontSize: 12 }}>{lastJob.environment}</span>
              <button
                className="btn btn-secondary btn-sm"
                style={{ marginLeft: 'auto' }}
                onClick={() => api.jobs.get(lastJob.id).then(setLastJob).catch(() => {})}
              >
                Refresh
              </button>
            </div>
            <div style={{ fontSize: 13 }}>DB: <code>{lastJob.db_name}</code> · Owner: {lastJob.owner}</div>
            {lastJob.error_message && <div style={{ color: 'var(--red)', fontSize: 13 }}>{lastJob.error_message}</div>}
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
      <div className="row between mb-4" style={{ flexWrap: 'wrap', gap: 8 }}>
        <div className="section-title" style={{ marginBottom: 0 }}>
          Provisioning History {histTotal > 0 && <span style={{ color: 'var(--muted)', fontWeight: 400, fontSize: 13 }}>({histTotal})</span>}
        </div>
        <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
          <select
            value={filterEnv}
            style={{ fontSize: 12, padding: '4px 8px' }}
            onChange={e => { setFilterEnv(e.target.value); loadHistory(e.target.value, filterStatus) }}
          >
            <option value="">All environments</option>
            {ENVS.map(e => <option key={e}>{e}</option>)}
          </select>
          <select
            value={filterStatus}
            style={{ fontSize: 12, padding: '4px 8px' }}
            onChange={e => { setFilterStatus(e.target.value); loadHistory(filterEnv, e.target.value) }}
          >
            <option value="">All statuses</option>
            {STATUSES.map(s => <option key={s}>{s}</option>)}
          </select>
          <button className="btn btn-secondary btn-sm" onClick={() => loadHistory()}>Refresh</button>
        </div>
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
                <th>Server</th>
                <th>Connection URI</th>
                <th>Provisioned</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {history.map(log => (
                <tr key={log.id} style={consoleLog?.id === log.id ? { background: 'var(--surface-2, #1e2030)' } : {}}>
                  <td style={{ fontWeight: 500 }}>{log.db_name}</td>
                  <td><code>#{log.job_id}</code></td>
                  <td>{log.db_user ?? '—'}</td>
                  <td>{servers.find(s => s.id === log.server_id)?.name ?? `#${log.server_id}`}</td>
                  <td style={{ maxWidth: 260 }}>
                    {log.connection_uri ? <code>{log.connection_uri}</code> : '—'}
                  </td>
                  <td style={{ color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                    {new Date(log.provisioned_at).toLocaleString()}
                  </td>
                  <td>
                    <button
                      className="btn btn-sm"
                      style={consoleLog?.id === log.id ? { opacity: 0.5 } : {}}
                      onClick={() => {
                        setConsoleLog(l => l?.id === log.id ? null : log)
                        setTimeout(() => consoleRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
                      }}
                    >
                      {consoleLog?.id === log.id ? 'Close' : 'Console'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* DB Console */}
      {consoleLog && (
        <div ref={consoleRef}>
          <DbConsole log={consoleLog} servers={servers} onClose={() => setConsoleLog(null)} />
        </div>
      )}

      {/* Live job lookup */}
      <JobLookup />
    </>
  )
}

const PG_INSPECT = [
  { label: 'List tables',  sql: "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name" },
  { label: 'List columns', sql: "SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'public' ORDER BY table_name, ordinal_position" },
  { label: 'Row counts',   sql: "SELECT relname AS table, n_live_tup AS rows FROM pg_stat_user_tables ORDER BY n_live_tup DESC" },
  { label: 'List indexes', sql: "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname" },
  { label: 'Constraints',  sql: "SELECT tc.table_name, tc.constraint_name, tc.constraint_type, kcu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu USING (constraint_name, table_schema) WHERE tc.table_schema = 'public' ORDER BY tc.table_name" },
]
const PG_TEMPLATES = [
  { label: 'CREATE TABLE', sql: "CREATE TABLE example (\n  id      SERIAL PRIMARY KEY,\n  name    TEXT NOT NULL,\n  created_at TIMESTAMP DEFAULT NOW()\n);" },
  { label: 'SELECT',       sql: "SELECT * FROM example\nLIMIT 100;" },
  { label: 'INSERT',       sql: "INSERT INTO example (name)\nVALUES ('hello');" },
  { label: 'UPDATE',       sql: "UPDATE example\nSET name = 'world'\nWHERE id = 1;" },
  { label: 'DELETE',       sql: "DELETE FROM example\nWHERE id = 1;" },
  { label: 'ALTER',        sql: "ALTER TABLE example\n  ADD COLUMN email TEXT;" },
  { label: 'DROP TABLE',   sql: "DROP TABLE example;" },
]
const PGVECTOR_TEMPLATES = [
  ...PG_TEMPLATES,
  { label: 'CREATE vector table', sql: "CREATE TABLE embeddings (\n  id      SERIAL PRIMARY KEY,\n  content TEXT,\n  embedding vector(1536)\n);" },
  { label: 'Vector search',       sql: "SELECT id, content,\n       embedding <-> '[0.1,0.2,...]'::vector AS distance\nFROM embeddings\nORDER BY distance\nLIMIT 10;" },
  { label: 'Create HNSW index',   sql: "CREATE INDEX ON embeddings\n  USING hnsw (embedding vector_cosine_ops);" },
]

const MYSQL_INSPECT = [
  { label: 'List tables',   sql: 'SHOW TABLES;' },
  { label: 'List columns',  sql: 'SHOW COLUMNS FROM example;' },
  { label: 'Table info',    sql: 'SHOW CREATE TABLE example;' },
  { label: 'Table sizes',   sql: "SELECT table_name, ROUND((data_length + index_length)/1024/1024,2) AS size_mb FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY size_mb DESC;" },
  { label: 'Active queries', sql: 'SHOW PROCESSLIST;' },
]
const MYSQL_TEMPLATES = [
  { label: 'CREATE TABLE', sql: "CREATE TABLE example (\n  id   INT AUTO_INCREMENT PRIMARY KEY,\n  name VARCHAR(255) NOT NULL,\n  created_at DATETIME DEFAULT CURRENT_TIMESTAMP\n);" },
  { label: 'SELECT',       sql: "SELECT * FROM example\nLIMIT 100;" },
  { label: 'INSERT',       sql: "INSERT INTO example (name)\nVALUES ('hello');" },
  { label: 'UPDATE',       sql: "UPDATE example\nSET name = 'world'\nWHERE id = 1;" },
  { label: 'DELETE',       sql: "DELETE FROM example\nWHERE id = 1;" },
  { label: 'ALTER',        sql: "ALTER TABLE example\n  ADD COLUMN email VARCHAR(255);" },
  { label: 'DROP TABLE',   sql: "DROP TABLE example;" },
]

const MONGO_INSPECT = [
  { label: 'List collections', sql: JSON.stringify({ op: 'list_collections' }, null, 0) },
  { label: 'Count docs',       sql: JSON.stringify({ op: 'count', coll: 'mycol', filter: {} }, null, 0) },
]
const MONGO_TEMPLATES = [
  { label: 'Find all',    sql: JSON.stringify({ op: 'find', coll: 'mycol', filter: {}, limit: 100 }, null, 2) },
  { label: 'Find filter', sql: JSON.stringify({ op: 'find', coll: 'mycol', filter: { status: 'active' }, limit: 50 }, null, 2) },
  { label: 'Count',       sql: JSON.stringify({ op: 'count', coll: 'mycol', filter: {} }, null, 2) },
]

const QDRANT_INSPECT = [
  { label: 'List collections', sql: JSON.stringify({ op: 'list' }, null, 0) },
  { label: 'Collection info',  sql: JSON.stringify({ op: 'info', coll: 'mycol' }, null, 0) },
]
const QDRANT_TEMPLATES = [
  { label: 'List',   sql: JSON.stringify({ op: 'list' }, null, 2) },
  { label: 'Info',   sql: JSON.stringify({ op: 'info', coll: 'mycol' }, null, 2) },
  { label: 'Scroll', sql: JSON.stringify({ op: 'scroll', coll: 'mycol', limit: 10 }, null, 2) },
]

const ENGINE_PLACEHOLDER: Record<string, string> = {
  postgresql: 'SELECT * FROM my_table;  — Ctrl+Enter to run',
  pgvector:   'SELECT * FROM embeddings LIMIT 10;  — Ctrl+Enter to run',
  mysql:      'SELECT * FROM my_table;  — Ctrl+Enter to run',
  mongodb:    '{"op":"find","coll":"users","filter":{},"limit":100}  — Ctrl+Enter to run',
  qdrant:     '{"op":"list"}  — Ctrl+Enter to run',
}

function _inspectTemplates(engine: string): { label: string; sql: string }[] {
  switch (engine) {
    case 'pgvector': return PG_INSPECT
    case 'mysql':    return MYSQL_INSPECT
    case 'mongodb':  return MONGO_INSPECT
    case 'qdrant':   return QDRANT_INSPECT
    default:         return PG_INSPECT
  }
}

function _queryTemplates(engine: string): { label: string; sql: string }[] {
  switch (engine) {
    case 'pgvector': return PGVECTOR_TEMPLATES
    case 'mysql':    return MYSQL_TEMPLATES
    case 'mongodb':  return MONGO_TEMPLATES
    case 'qdrant':   return QDRANT_TEMPLATES
    default:         return PG_TEMPLATES
  }
}

function DbConsole({ log, servers, onClose }: { log: CreationLog; servers: Server[]; onClose: () => void }) {
  const server = servers.find(s => s.id === log.server_id)
  const engine = server?.engine ?? 'postgresql'
  const [sql, setSql] = useState('')
  const [result, setResult] = useState<QueryResult | null>(null)
  const [running, setRunning] = useState(false)

  const run = async (query = sql) => {
    if (!query.trim()) return
    setRunning(true)
    setResult(null)
    try {
      const r = await api.databases.query(log.id, query.trim())
      setResult(r)
    } catch (e: unknown) {
      setResult({ columns: [], rows: [], row_count: 0, error: e instanceof Error ? e.message : String(e), status: null })
    } finally {
      setRunning(false)
    }
  }

  const INSPECT = _inspectTemplates(engine)
  const TEMPLATES = _queryTemplates(engine)
  const placeholder = ENGINE_PLACEHOLDER[engine] ?? 'Enter query — Ctrl+Enter to run'

  return (
    <div className="card mt-6" style={{ marginTop: 24 }}>
      <div className="row between" style={{ marginBottom: 12 }}>
        <div>
          <span className="section-title" style={{ marginRight: 8 }}>Console</span>
          <code style={{ fontSize: 13 }}>{log.db_name}</code>
          <span style={{ color: 'var(--muted)', fontSize: 12, marginLeft: 8 }}>
            {server?.name ?? `server #${log.server_id}`}
          </span>
          <span style={{ color: 'var(--muted)', fontSize: 11, marginLeft: 6 }}>({engine})</span>
        </div>
        <button className="btn btn-sm" onClick={onClose}>✕ Close</button>
      </div>

      <div style={{ marginBottom: 8 }}>
        <div className="row gap-2" style={{ flexWrap: 'wrap', alignItems: 'center', marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Inspect</span>
          {INSPECT.map(q => (
            <button key={q.label} className="btn btn-secondary btn-sm" onClick={() => { setSql(q.sql); run(q.sql) }}>
              {q.label}
            </button>
          ))}
        </div>
        <div className="row gap-2" style={{ flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Templates</span>
          {TEMPLATES.map(q => (
            <button key={q.label} className="btn btn-sm" onClick={() => setSql(q.sql)}>
              {q.label}
            </button>
          ))}
        </div>
      </div>

      <textarea
        value={sql}
        onChange={e => setSql(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) run() }}
        placeholder={placeholder}
        style={{ width: '100%', minHeight: 80, fontFamily: 'monospace', fontSize: 13,
                 background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)',
                 borderRadius: 4, padding: 8, resize: 'vertical', boxSizing: 'border-box' }}
      />
      <div className="row gap-2 mt-2" style={{ marginTop: 8 }}>
        <button className="btn btn-primary btn-sm" onClick={() => run()} disabled={running}>
          {running ? 'Running…' : '▶ Run'}
        </button>
        {result && !result.error && (
          <span style={{ fontSize: 12, color: 'var(--muted)', alignSelf: 'center' }}>
            {result.status ?? `${result.row_count} row${result.row_count !== 1 ? 's' : ''}`}
          </span>
        )}
      </div>

      {result && (
        <div style={{ marginTop: 12 }}>
          {result.error ? (
            <div className="alert alert-error" style={{ fontFamily: 'monospace', fontSize: 12 }}>{result.error}</div>
          ) : result.columns.length === 0 ? (
            <div style={{ color: 'var(--muted)', fontSize: 13 }}>No rows returned.</div>
          ) : (
            <div className="table-wrap" style={{ maxHeight: 400, overflowY: 'auto' }}>
              <table style={{ fontSize: 12 }}>
                <thead>
                  <tr>{result.columns.map(c => <th key={c}>{c}</th>)}</tr>
                </thead>
                <tbody>
                  {result.rows.map((row, i) => (
                    <tr key={i}>{row.map((v, j) => (
                      <td key={j} style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {v === null ? <span style={{ color: 'var(--muted)' }}>NULL</span> : String(v)}
                      </td>
                    ))}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
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
