import { api } from "./http";

export interface PackageIssue {
  code: string;
  message: string;
  path: string | null;
}

export interface ResultSubmission {
  submission_uid: string;
  package_uid: string | null;
  result_uid: string | null;
  project_uid: string | null;
  survey_batch_uid: string | null;
  original_filename: string;
  file_sha256: string;
  file_size: number;
  package_format_version: string | null;
  desktop_app_version: string | null;
  desktop_app_version_label: string | null;
  result_name: string | null;
  source_task_uids: string[];
  counts: Record<string, number>;
  status: string;
  inspection_error_count: number;
  inspection_issues: PackageIssue[];
  storage_status: string;
  storage_checked_at: string | null;
  uploader_user_uid: string;
  uploader_username: string;
  uploaded_at: string;
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
  status = "",
) {
  const response = await api.get(
    "/result-submissions",
    {
      params: status
        ? { status }
        : undefined,
    },
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

export function resultDownloadUrl(
  submissionUid: string,
): string {
  return (
    `/api/v1/result-submissions/`
    + `${submissionUid}/download`
  );
}
