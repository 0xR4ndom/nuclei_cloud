export type UserRole = "ADMIN" | "ANALYST" | "VIEWER";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  api_key: string | null;
  created_at: string;
}

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export type TargetType = "URL" | "IP" | "CIDR" | "DOMAIN";

export interface Target {
  id: string;
  value: string;
  type: TargetType;
  tags: string[];
  owner_id: string;
  created_at: string;
}

export interface TargetList {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  target_count: number;
  created_at: string;
  updated_at: string;
  targets?: Target[];
}

export type ScanStatus =
  | "PENDING"
  | "QUEUED"
  | "RUNNING"
  | "DONE"
  | "FAILED"
  | "CANCELLED";

export interface ScanConfig {
  severity: string[];
  tags: string[];
  templates: string[];
  exclude_tags: string[];
  rate_limit: number;
  bulk_size: number;
  concurrency: number;
  timeout: number;
  retries: number;
  extra_flags: string[];
}

export interface Scan {
  id: string;
  name: string;
  status: ScanStatus;
  owner_id: string;
  config: ScanConfig;
  total_targets: number;
  total_findings: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
  celery_task_id: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  scheduled_at: string | null;
  updated_at: string;
}

export type FindingSeverity =
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "info"
  | "unknown";

export interface Finding {
  id: string;
  scan_id: string;
  template_id: string | null;
  template_name: string | null;
  severity: FindingSeverity;
  matched_at: string;
  target: string;
  host: string | null;
  description: string | null;
  matched_line: string | null;
  extracted_results: string[];
  curl_command: string | null;
  reference: string[];
  tags: string[];
  created_at: string;
}

export interface FindingList {
  items: Finding[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface FindingStats {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
  by_template: Array<{ template: string; count: number }>;
}

export interface GlobalStats {
  total_scans: number;
  total_findings: number;
  running_scans: number;
  findings_by_severity: Record<string, number>;
}

export type WebhookType = "DISCORD" | "SLACK" | "JIRA" | "GENERIC";

export interface Webhook {
  id: string;
  name: string;
  url: string;
  type: WebhookType;
  events: string[];
  severity_filter: string[];
  is_active: boolean;
  owner_id: string;
  created_at: string;
}
