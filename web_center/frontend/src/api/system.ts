import { api } from "./http";

export interface HealthResponse {
  status: string;
  service: string;
  api_generation: string;
}

export interface DatabaseHealthResponse {
  status: string;
  database: string;
  user: string;
  engine: string;
}

export interface OverviewResponse {
  product_version: string;
  web_stage: string;
  task_protocol: string;
  result_protocol: string;
  project_count: number;
  active_batch_count: number;
  result_submission_count: number;
  survey_task_count: number;
  central_record_count: number;
  pending_review_count: number;
  active_user_count: number;
  official_department_count: number;
  official_office_count: number;
  official_canal_count: number;
  official_scope_count: number;
  unassigned_backbone_canal_count: number;
  master_data_version: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await api.get<HealthResponse>("/health");
  return response.data;
}

export async function getDatabaseHealth(): Promise<DatabaseHealthResponse> {
  const response = await api.get<DatabaseHealthResponse>("/health/database");
  return response.data;
}

export async function getOverview(): Promise<OverviewResponse> {
  const response = await api.get<OverviewResponse>("/overview");
  return response.data;
}
