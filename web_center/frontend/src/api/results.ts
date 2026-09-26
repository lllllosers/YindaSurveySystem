import { api } from "./http";

export interface PackageIssue {
  code: string;
  message: string;
  path: string | null;
}

export interface WorkflowIssue {
  severity: string;
  code: string;
  message: string;
  entity_uid: string;
}

export interface ResultSubmission {
  submission_uid: string;
  package_uid: string | null;
  result_uid: string | null;
  project_uid: string | null;
  project_name: string | null;
  survey_batch_uid: string | null;
  survey_batch_name: string | null;
  original_filename: string;
  file_sha256: string;
  file_size: number;
  package_format_version: string | null;
  desktop_app_version: string | null;
  desktop_app_version_label: string | null;
  result_name: string | null;
  source_task_uids: string[];
  submission_task_uid: string | null;
  submission_task_name: string | null;
  submission_unit_name: string | null;
  counts: Record<string, number>;
  status: string;
  inspection_error_count: number;
  inspection_issues: PackageIssue[];
  preflight_error_count: number;
  preflight_warning_count: number;
  preflight_issues: WorkflowIssue[];
  preflight_summary: Record<string, number>;
  preflight_checked_at: string | null;
  review_notes: string | null;
  reviewed_by_username: string | null;
  reviewed_at: string | null;
  imported_at: string | null;
  storage_status: string;
  storage_checked_at: string | null;
  uploader_user_uid: string;
  uploader_username: string;
  uploaded_at: string;
}

export interface ResultImportResult {
  submission_uid: string;
  status: string;
  assets: number;
  records: number;
  inspections: number;
  media: number;
  changed_records: number;
}

export interface ResultSubmissionSummary {
  total: number;
  awaiting_check: number;
  awaiting_review: number;
  needs_attention: number;
  accepted: number;
  imported: number;
}

export interface ResultSubmissionPage {
  items: ResultSubmission[];
  total: number;
  limit: number;
  offset: number;
  summary: ResultSubmissionSummary;
}

export interface ResultSubmissionQuery {
  status?: string;
  project_uid?: string;
  survey_batch_uid?: string;
  keyword?: string;
  limit?: number;
  offset?: number;
}

export interface ResultFileVerification {
  submission_uid: string;
  storage_status: string;
  checked_at: string;
  file_exists: boolean;
  expected_size: number;
  actual_size: number | null;
  size_match: boolean;
  expected_sha256: string;
  actual_sha256: string | null;
  sha256_match: boolean;
  package_structure_valid: boolean | null;
  package_structure_error_count: number | null;
  package_structure_issues: Record<string, unknown>[];
}

export async function listResultSubmissions(
  params: ResultSubmissionQuery = {},
): Promise<ResultSubmissionPage> {
  const response = await api.get<ResultSubmissionPage>(
    "/result-submissions",
    { params },
  );
  return response.data;
}

export async function getResultSubmission(
  submissionUid: string,
): Promise<ResultSubmission> {
  const response = await api.get<ResultSubmission>(
    `/result-submissions/${submissionUid}`,
  );
  return response.data;
}

export async function uploadResultPackage(
  file: File,
): Promise<ResultSubmission> {
  const form = new FormData();
  form.append("file", file);

  const response = await api.post<ResultSubmission>(
    "/result-submissions/upload",
    form,
    {
      timeout: 0,
    },
  );
  return response.data;
}

export async function verifyResultSubmission(
  submissionUid: string,
): Promise<ResultFileVerification> {
  const response = await api.post<ResultFileVerification>(
    `/result-submissions/${submissionUid}/verify`,
  );
  return response.data;
}

export async function preflightResultSubmission(
  submissionUid: string,
): Promise<ResultSubmission> {
  const response = await api.post<ResultSubmission>(
    `/result-submissions/${submissionUid}/preflight`,
  );
  return response.data;
}

export async function reviewResultSubmission(
  submissionUid: string,
  decision: "accepted" | "rejected",
  notes: string | null,
): Promise<ResultSubmission> {
  const response = await api.post<ResultSubmission>(
    `/result-submissions/${submissionUid}/review`,
    { decision, notes },
  );
  return response.data;
}

export async function importResultSubmission(
  submissionUid: string,
): Promise<ResultImportResult> {
  const response = await api.post<ResultImportResult>(
    `/result-submissions/${submissionUid}/import`,
  );
  return response.data;
}

export function resultDownloadUrl(
  submissionUid: string,
): string {
  return (
    `/api/v1/result-submissions/`
    + `${submissionUid}/download`
  );
}
