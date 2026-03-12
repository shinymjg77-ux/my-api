export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
export type DBType = "sqlite" | "postgresql";
export type LogType = "auth" | "api" | "db" | "system";
export type LogLevel = "info" | "warning" | "error";


export interface Admin {
  id: number;
  username: string;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}


export interface ManagedApi {
  id: number;
  name: string;
  url: string;
  method: HttpMethod;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}


export interface ManagedApiInput {
  name: string;
  url: string;
  method: HttpMethod;
  description: string;
  is_active: boolean;
}


export interface DbConnection {
  id: number;
  name: string;
  db_type: DBType;
  host: string | null;
  port: number | null;
  db_name: string | null;
  username: string | null;
  description: string | null;
  is_active: boolean;
  has_password: boolean;
  password_masked: string;
  last_tested_at: string | null;
  last_test_status: string | null;
  last_test_message: string | null;
  created_at: string;
  updated_at: string;
}


export interface DbConnectionInput {
  name: string;
  db_type: DBType;
  host: string;
  port: string;
  db_name: string;
  username: string;
  password: string;
  description: string;
  is_active: boolean;
}


export interface DbConnectionTestResponse {
  success: boolean;
  message: string;
  latency_ms: number | null;
}


export interface ActivityLog {
  id: number;
  log_type: LogType;
  api_id: number | null;
  api_name: string | null;
  db_connection_id: number | null;
  db_connection_name: string | null;
  level: LogLevel;
  status_code: number | null;
  is_success: boolean;
  message: string;
  detail: string | null;
  created_at: string;
}


export interface ActivityLogListResponse {
  items: ActivityLog[];
  total: number;
  page: number;
  page_size: number;
}


export interface DashboardSummary {
  recent_success_count: number;
  recent_failure_count: number;
  api_count: number;
  db_connection_count: number;
  recent_error_logs: ActivityLog[];
}


export type OpsOverallStatus = "healthy" | "warning" | "critical";
export type OpsProcessAttentionLevel = "healthy" | "warning" | "critical";


export interface OpsServiceStatus {
  name: string;
  description: string;
  active_state: string;
  sub_state: string;
  is_healthy: boolean;
}


export interface OpsProcessStatus {
  name: string;
  status: string;
  is_healthy: boolean;
  attention_level: OpsProcessAttentionLevel;
  group_key: string;
  group_label: string;
  pid: number | null;
  restart_count: number;
  cpu_percent: number;
  memory_bytes: number;
  uptime_seconds: number | null;
  cwd: string | null;
}


export interface OpsDashboardSummary {
  systemd_total: number;
  systemd_healthy: number;
  pm2_total: number;
  pm2_online: number;
  pm2_unhealthy: number;
}


export interface OpsDashboard {
  generated_at: string;
  overall_status: OpsOverallStatus;
  systemd_services: OpsServiceStatus[];
  pm2_processes: OpsProcessStatus[];
  summary: OpsDashboardSummary;
  warnings: string[];
}
