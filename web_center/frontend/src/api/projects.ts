import { api } from "./http";

export type ProjectStatus = "active" | "archived";
export type SurveyBatchStatus = "planned" | "active" | "closed";

export interface Project {
  project_uid: string;
  name: string;
  short_name: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectPayload {
  name: string;
  short_name?: string | null;
  status: ProjectStatus;
}

export interface SurveyBatch {
  survey_batch_uid: string;
  batch_name: string;
  batch_code: string;
  start_date: string | null;
  end_date: string | null;
  status: SurveyBatchStatus;
  created_at: string;
  updated_at: string;
}

export interface SurveyBatchPayload {
  batch_name: string;
  batch_code: string;
  start_date?: string | null;
  end_date?: string | null;
  status: SurveyBatchStatus;
}

export async function listProjects(): Promise<Project[]> {
  const response = await api.get<Project[]>("/projects");
  return response.data;
}

export async function createProject(
  payload: ProjectPayload,
): Promise<Project> {
  const response = await api.post<Project>("/projects", payload);
  return response.data;
}

export async function updateProject(
  projectUid: string,
  payload: Partial<ProjectPayload>,
): Promise<Project> {
  const response = await api.patch<Project>(
    `/projects/${projectUid}`,
    payload,
  );
  return response.data;
}

export async function deleteProject(projectUid: string): Promise<void> {
  await api.delete(`/projects/${projectUid}`);
}

export async function listSurveyBatches(
  projectUid: string,
): Promise<SurveyBatch[]> {
  const response = await api.get<SurveyBatch[]>(
    `/projects/${projectUid}/batches`,
  );
  return response.data;
}

export async function createSurveyBatch(
  projectUid: string,
  payload: SurveyBatchPayload,
): Promise<SurveyBatch> {
  const response = await api.post<SurveyBatch>(
    `/projects/${projectUid}/batches`,
    payload,
  );
  return response.data;
}

export async function updateSurveyBatch(
  batchUid: string,
  payload: Partial<SurveyBatchPayload>,
): Promise<SurveyBatch> {
  const response = await api.patch<SurveyBatch>(
    `/survey-batches/${batchUid}`,
    payload,
  );
  return response.data;
}

export async function deleteSurveyBatch(
  batchUid: string,
): Promise<void> {
  await api.delete(`/survey-batches/${batchUid}`);
}
