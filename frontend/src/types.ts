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
  has_admin_dsn: boolean
  has_api_key: boolean
  machine_id: number | null
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
  warning_threshold_pct: number
  critical_threshold_pct: number
  admin_dsn?: string
  api_key?: string
  machine_id?: number | null
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

export interface NamingProfile {
  id: number
  name: string
  pattern: string
  prefix: string | null
  suffix: string | null
  separator: string
  reserved_names: string[]
  allow_collision: boolean
  description: string | null
  is_deleted: boolean
}

export interface NamingProfileCreate {
  name: string
  pattern: string
  prefix?: string
  suffix?: string
  separator?: string
  reserved_names?: string[]
  allow_collision?: boolean
  description?: string
}

export interface DBTemplate {
  id: number
  name: string
  description: string | null
  extensions: string[]
  permissions: Record<string, string[]>
  is_deleted: boolean
}

export interface DBTemplateCreate {
  name: string
  description?: string
  extensions: string[]
  permissions: Record<string, string[]>
}

export interface RequestTemplate {
  id: number
  name: string
  description: string | null
  environment: string
  db_template_id: number | null
  naming_profile_id: number | null
  expiration_days: number
  cost_center: string | null
  team: string | null
  is_deleted: boolean
}

export interface RequestTemplateCreate {
  name: string
  description?: string
  environment: string
  db_template_id?: number
  naming_profile_id?: number
  expiration_days?: number
  cost_center?: string
  team?: string
}

export interface QueryResult {
  columns: string[]
  rows: unknown[][]
  row_count: number
  error: string | null
  status: string | null
}

export interface ApprovalPolicy {
  auto_approved_environments: string[]
}

export interface Stats {
  jobs: {
    total: number
    by_status: Record<string, number>
    by_environment: Record<string, number>
    success_rate_pct: number
  }
  servers: { total: number; active: number }
  history: { total_provisioned: number }
}

export interface SSHKey {
  id: number
  name: string
  username: string
  created_at: string
}

export interface SSHKeyCreate {
  name: string
  username: string
  private_key: string
  passphrase?: string
}

export interface Machine {
  id: number
  ip: string
  hostname: string | null
  label: string | null
  ssh_port: number
  ssh_key_id: number
  os_info: string | null
  host_fingerprint: string | null
  status: string
  last_checked_at: string | null
  created_at: string
  is_deleted: boolean
}

export interface MachineCreate {
  ip: string
  ssh_port?: number
  ssh_key_id: number
  label?: string
}

export interface ScanResult {
  ip: string
  ping_ok: boolean
  ssh_open: boolean
}

export interface EngineDetectionResult {
  port: number
  engine: string
  open: boolean
}

export interface Site {
  id: number
  name: string
  template: string
  subdomain: string
  domain: string
  prefix: string | null
  routing_mode: string
  app_port: number | null
  web_root: string
  directory: string | null
  web_server: string
  notes: string | null
  created_at: string
  is_deleted: boolean
}

export interface SiteCreate {
  name: string
  template: string
  subdomain: string
  domain: string
  prefix?: string
  routing_mode: string
  app_port?: number
  web_root?: string
  directory?: string
  web_server?: string
  notes?: string
}

export interface SiteDeployment {
  id: number
  site_id: number
  server_id: number
  status: string
  port: number | null
  directory: string | null
  created_at: string
  retired_at: string | null
}

export interface Migration {
  id: number
  site_id: number
  source_deployment_id: number | null
  target_server_id: number
  status: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  log: string | null
  created_at: string
}
