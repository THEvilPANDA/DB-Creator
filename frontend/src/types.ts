export interface Server {
  id: number
  name: string
  host: string
  port: number
  engine: string
  environment: string
  region: string | null
  is_active: boolean
  max_connections: number
  max_storage_gb: number
  warning_threshold_pct: number
  critical_threshold_pct: number
  created_at: string
  is_deleted: boolean
}

export interface ServerCreate {
  name: string
  host: string
  port: number
  engine: string
  environment: string
  region?: string
  max_connections: number
  max_storage_gb: number
}

export interface Job {
  id: number
  db_name: string
  environment: string
  status: string
  owner: string
  team: string | null
  cost_center: string | null
  server_id: number | null
  error_message: string | null
  created_at: string
  completed_at: string | null
  is_deleted: boolean
}

export interface JobCreate {
  db_name?: string
  environment: string
  owner: string
  team?: string
  cost_center?: string
  server_id?: number
}

export interface CreationLog {
  id: number
  job_id: number
  server_id: number
  db_name: string
  db_user: string | null
  connection_uri: string | null
  provisioned_at: string
  created_at: string
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface HealthCheck {
  status: string
  environment?: string
  detail?: string
}
