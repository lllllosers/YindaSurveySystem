import { api } from "./http";

export interface CentralRecord {
  survey_record_uid: string;
  engineering_asset_uid: string;
  asset_name: string | null;
  asset_type: string | null;
  business_code: string | null;
  project_uid: string;
  survey_batch_uid: string;
  form_code: string;
  organization_unit_uid: string;
  organization_name: string;
  canal_unit_uid: string;
  canal_name: string;
  source_task_uid: string | null;
  source_management_scope_uid: string | null;
  record_status: string | null;
  revision_no: number;
  current_submission_uid: string;
  imported_at: string;
  updated_at: string;
}

export interface CentralRecordDetail extends CentralRecord {
  record_payload: Record<string, unknown>;
  asset_payload: Record<string, unknown>;
  inspections: Record<string, unknown>[];
  media: Record<string, unknown>[];
}

export interface NamedCount {
  key: string;
  name: string;
  count: number;
}

export interface CentralRecordSummary {
  asset_count: number;
  record_count: number;
  inspection_count: number;
  media_count: number;
  by_form: NamedCount[];
  by_organization: NamedCount[];
  by_canal: NamedCount[];
}

export interface CentralRecordFilters {
  search?: string;
  form_code?: string;
  organization_unit_uid?: string;
  canal_unit_uid?: string;
  limit?: number;
  offset?: number;
}

export async function listCentralRecords(filters: CentralRecordFilters = {}) {
  const response = await api.get("/central-records", { params: filters });
  return response.data;
}

export async function getCentralRecord(uid: string): Promise<CentralRecordDetail> {
  const response = await api.get<CentralRecordDetail>(`/central-records/${uid}`);
  return response.data;
}

export async function getCentralRecordSummary(): Promise<CentralRecordSummary> {
  const response = await api.get<CentralRecordSummary>("/central-records/summary");
  return response.data;
}

export function centralRecordMediaUrl(recordUid: string, mediaUid: string): string {
  return `/api/v1/central-records/${recordUid}/media/${mediaUid}`;
}

export function centralRecordExportUrl(filters: CentralRecordFilters = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return `/api/v1/central-records/export.csv${query ? `?${query}` : ""}`;
}
