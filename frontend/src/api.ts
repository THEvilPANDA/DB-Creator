import type {
  ApprovalPolicy, CreationLog, DBTemplate, DBTemplateCreate,
  EngineDetectionResult, HealthCheck, Job, JobCreate, Machine, MachineCreate,
  NamingProfile, NamingProfileCreate,
  Paginated, QueryResult, RequestTemplate, RequestTemplateCreate,
  ScanResult, Server, ServerCreate, SSHKey, SSHKeyCreate, Stats,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? '/api/v1'
const ADMIN_KEY = import.meta.env.VITE_ADMIN_KEY ?? ''

const TOKEN_KEY = 'dbcreator_access_token'
const REFRESH_KEY = 'dbcreator_refresh_token'

export const auth = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setTokens: (access: string, refresh: string) => {
    localStorage.setItem(TOKEN_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },
  clearTokens: () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
  isAuthenticated: () => !!localStorage.getItem(TOKEN_KEY),
}

// Deduplicated refresh: if multiple requests fail with 401 concurrently,
// only one refresh call goes out and all waiters share the result.
let _refreshPromise: Promise<boolean> | null = null

async function _tryRefresh(): Promise<boolean> {
  const refreshToken = localStorage.getItem(REFRESH_KEY)
  if (!refreshToken) return false
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) return false
    const data = await res.json() as { access_token: string; refresh_token: string }
    auth.setTokens(data.access_token, data.refresh_token)
    return true
  } catch {
    return false
  }
}

function _buildHeaders(token: string | null): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (ADMIN_KEY) h['X-Admin-Key'] = ADMIN_KEY
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ..._buildHeaders(auth.getToken()), ...init?.headers },
  })

  if (res.status === 401) {
    // Refresh once, deduped across concurrent calls
    if (!_refreshPromise) {
      _refreshPromise = _tryRefresh().finally(() => { _refreshPromise = null })
    }
    const ok = await _refreshPromise
    if (!ok) {
      auth.clearTokens()
      throw new Error('Session expired — please log in again')
    }
    // Retry with the new token
    const retry = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { ..._buildHeaders(auth.getToken()), ...init?.headers },
    })
    if (!retry.ok) {
      const body = await retry.text().catch(() => retry.statusText)
      throw new Error(`${retry.status}: ${body}`)
    }
    return retry.json() as Promise<T>
  }

  if (!res.ok) {
    const body = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: {
    app: () => fetch('/health').then(r => r.json()) as Promise<HealthCheck>,
    db: () => fetch('/health/database').then(r => r.json()) as Promise<HealthCheck>,
    queue: () => fetch('/health/queue').then(r => r.json()) as Promise<HealthCheck>,
  },
  servers: {
    list: () => req<Server[]>('/servers'),
    create: (data: ServerCreate) => req<Server>('/servers', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: Partial<ServerCreate>) => req<Server>(`/servers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    remove: (id: number) => req<Server>(`/servers/${id}`, { method: 'DELETE' }),
  },
  jobs: {
    submit: (data: JobCreate) => req<Job>('/jobs', { method: 'POST', body: JSON.stringify(data) }),
    list: (status?: string) => req<Job[]>(`/jobs${status ? `?status=${status}` : ''}`),
    get: (id: number) => req<Job>(`/jobs/${id}`),
    cancel: (id: number) => req<Job>(`/jobs/${id}`, { method: 'DELETE' }),
    approve: (id: number, status: 'approved' | 'rejected', comments?: string) =>
      req<unknown>(`/jobs/${id}/approve`, { method: 'POST', body: JSON.stringify({ status, comments }) }),
  },
  history: (page = 1, pageSize = 20, environment?: string, status?: string) => {
    const p = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    if (environment) p.set('environment', environment)
    if (status) p.set('status', status)
    return req<Paginated<CreationLog>>(`/history?${p}`)
  },
  stats: () => req<Stats>('/stats'),
  search: (q: string, type = 'all') =>
    req<Record<string, unknown[]>>(`/search?q=${encodeURIComponent(q)}&type=${type}`),
  naming: {
    list: () => req<NamingProfile[]>('/naming-profiles'),
    create: (data: NamingProfileCreate) =>
      req<NamingProfile>('/naming-profiles', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: number) =>
      req<NamingProfile>(`/naming-profiles/${id}`, { method: 'DELETE' }),
    preview: (id: number, ctx: Record<string, string>) => {
      const p = new URLSearchParams(ctx)
      return req<{ resolved_name: string; valid: boolean; errors: string[]; pattern: string }>(
        `/naming-profiles/${id}/preview?${p}`
      )
    },
  },
  dbTemplates: {
    list: () => req<DBTemplate[]>('/database-templates'),
    create: (data: DBTemplateCreate) =>
      req<DBTemplate>('/database-templates', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: number) =>
      req<DBTemplate>(`/database-templates/${id}`, { method: 'DELETE' }),
  },
  requestTemplates: {
    list: () => req<RequestTemplate[]>('/request-templates'),
    create: (data: RequestTemplateCreate) =>
      req<RequestTemplate>('/request-templates', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: number) =>
      req<RequestTemplate>(`/request-templates/${id}`, { method: 'DELETE' }),
  },
  databases: {
    query: (logId: number, sql: string) =>
      req<QueryResult>(`/databases/${logId}/query`, { method: 'POST', body: JSON.stringify({ sql }) }),
  },
  admin: {
    seed: () => req<unknown>('/admin/seed', { method: 'POST' }),
    getApprovalPolicy: () => req<ApprovalPolicy>('/admin/approval-policy'),
    setApprovalPolicy: (envs: string[]) =>
      req<ApprovalPolicy>('/admin/approval-policy', {
        method: 'PUT',
        body: JSON.stringify({ auto_approved_environments: envs }),
      }),
  },
  authApi: {
    login: (username: string, password: string) =>
      req<{ access_token: string; refresh_token: string; token_type: string }>(
        '/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }
      ),
    register: (username: string, email: string, password: string) =>
      req<{ id: number; username: string; email: string; is_admin: boolean; is_active: boolean }>(
        '/auth/register', { method: 'POST', body: JSON.stringify({ username, email, password }) }
      ),
    me: () => req<{ id: number; username: string; email: string; is_admin: boolean; is_active: boolean }>('/auth/me'),
  },
  sshKeys: {
    list: () => req<SSHKey[]>('/ssh-keys'),
    create: (data: SSHKeyCreate) =>
      req<SSHKey>('/ssh-keys', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: number) =>
      req<SSHKey>(`/ssh-keys/${id}`, { method: 'DELETE' }),
  },
  machines: {
    list: () => req<Machine[]>('/machines'),
    create: (data: MachineCreate) =>
      req<Machine>('/machines', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: Partial<MachineCreate>) =>
      req<Machine>(`/machines/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number) =>
      req<Machine>(`/machines/${id}`, { method: 'DELETE' }),
    check: (id: number) =>
      req<Machine>(`/machines/${id}/check`, { method: 'POST' }),
    detectEngines: (id: number) =>
      req<EngineDetectionResult[]>(`/machines/${id}/detect-engines`, { method: 'POST' }),
    scan: (data: { cidr: string; method: string }) =>
      req<ScanResult[]>('/machines/scan', { method: 'POST', body: JSON.stringify(data) }),
  },
}
