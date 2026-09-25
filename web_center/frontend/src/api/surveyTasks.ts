import { api } from "./http";


export type TaskTargetType = "department" | "water_office";
export type TaskStatus = "issued" | "downloaded" | "result_received" | "closed" | "cancelled";

export interface SurveyTask {
  task_uid: string;
  package_uid: string;
  project_uid: string;
  project_name: string;
  survey_batch_uid: string;
  batch_name: string;
  batch_code: string;
  task_name: string;
  notes: string | null;
  target_unit_type: TaskTargetType;
  department_uid: string;
  department_name: string;
  organization_unit_uid: string;
  organization_name: string;
  parent_task_uid: string | null;
  root_task_uid: string;
  task_depth: number;
  selected_scope_count: number;
  reference_canal_count: number;
  reference_organization_count: number;
  form_count: number;
  file_sha256: string;
  file_size: number;
  status: TaskStatus;
  download_count: number;
  first_downloaded_at: string | null;
  last_downloaded_at: string | null;
  created_by_username: string;
  created_at: string;
}

export interface FrozenScope {
  management_scope_uid: string;
  canal_uid: string;
  canal_name: string;
  organization_unit_uid: string;
  organization_name: string;
  range_mode: string;
  start_stake_text: string | null;
  end_stake_text: string | null;
  description: string | null;
}

export interface SurveyTaskDetail extends SurveyTask {
  selected_management_scope_uids: string[];
  frozen_scopes: FrozenScope[];
  master_data_version: string;
  master_contract_sha256: string;
  form_contract_version: string;
}

export interface SurveyTaskPayload {
  project_uid: string;
  survey_batch_uid: string;
  task_name: string;
  notes?: string | null;
  target_unit_type: TaskTargetType;
  target_master_key: string;
  selected_management_scope_uids: string[];
}

export interface SurveyTaskPage {
  items: SurveyTask[];
  total: number;
  limit: number;
  offset: number;
}

export async function listSurveyTasks(): Promise<SurveyTaskPage> {
  const response = await api.get<SurveyTaskPage>("/survey-tasks");
  return response.data;
}

export async function getSurveyTask(taskUid: string): Promise<SurveyTaskDetail> {
  const response = await api.get<SurveyTaskDetail>(`/survey-tasks/${taskUid}`);
  return response.data;
}

export async function createSurveyTask(payload: SurveyTaskPayload): Promise<SurveyTaskDetail> {
  const response = await api.post<SurveyTaskDetail>("/survey-tasks", payload);
  return response.data;
}

export async function cancelSurveyTask(taskUid: string): Promise<SurveyTask> {
  const response = await api.post<SurveyTask>(`/survey-tasks/${taskUid}/cancel`);
  return response.data;
}

export async function downloadSurveyTask(task: SurveyTask): Promise<void> {
  const response = await api.get<Blob>(`/survey-tasks/${task.task_uid}/download`, {
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${task.batch_code}_${task.organization_name}_${task.task_name}_${task.task_uid.slice(0, 8)}.ydtask`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
