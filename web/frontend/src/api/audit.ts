import { api } from "./http";

export interface AuditEvent {
  audit_uid: string;
  occurred_at: string;
  actor_user_uid: string | null;
  actor_username: string | null;
  actor_role: string | null;
  action: string;
  resource_type: string;
  resource_path: string;
  http_method: string;
  status_code: number;
  outcome: "success" | "failure";
  client_ip: string | null;
  user_agent: string | null;
  summary: string | null;
  details_json: Record<string, unknown> | null;
}

export interface AuditEventPage {
  items: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export async function listAuditEvents(params: {
  actor_username?: string;
  resource_type?: string;
  action?: string;
  outcome?: "success" | "failure" | "";
  limit?: number;
  offset?: number;
}): Promise<AuditEventPage> {
  const response = await api.get<AuditEventPage>("/audit-events", {
    params: Object.fromEntries(
      Object.entries(params).filter(([, value]) => value !== "" && value != null),
    ),
  });
  return response.data;
}
