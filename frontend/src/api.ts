import type {
  ApprovalPolicy, CreationLog, DBTemplate, DBTemplateCreate,
  HealthCheck, Job, JobCreate, NamingProfile, NamingProfileCreate,
  Paginated, RequestTemplate, RequestTemplateCreate, Server, ServerCreate, Stats,
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

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = auth.getToken()
  const adminHeaders: Record<string, string> = ADMIN_KEY ? { 'X-Admin-Key': ADMIN_KEY } : {}
  const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...adminHeaders, ...authHeaders, ...init?.headers },
    ...init,
  })
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
    remove: (id: number) => req<Server>(`/servers/${id}`, { method: 'DELETE' }),
  },
  jobs: {
    submit: (data: JobCreate) => req<Job>('/jobs', { method: 'POST', body: JSON.stringify(data) }),
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
}
