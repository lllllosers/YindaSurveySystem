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
  result_name: string | null;
  counts: Record<string, number>;
  status: string;
  inspection_error_count: number;
  inspection_issues: PackageIssue[];
  uploader_username: string;
  uploaded_at: string;
}

export async function listResultSubmissions(status = "") {
  const response = await api.get("/result-submissions", {
    params: status ? { status } : undefined,
  });
  return response.data;
}

export async function uploadResultPackage(file: File): Promise<ResultSubmission> {
  const form = new FormData();
  form.append("file", file);
  const response = await api.post<ResultSubmission>(
    "/result-submissions/upload",
    form,
    { timeout: 0 },
  );
  return response.data;
}

export function resultDownloadUrl(submissionUid: string): string {
  return `/api/v1/result-submissions/${submissionUid}/download`;
}
