import type { CreationLog, HealthCheck, Job, JobCreate, Paginated, Server, ServerCreate, Stats } from './types'

const BASE = import.meta.env.VITE_API_URL ?? '/api/v1'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
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
}
