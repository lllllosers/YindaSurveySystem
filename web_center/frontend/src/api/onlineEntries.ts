import { api } from "./http";

export type OnlineEntryStatus = "draft" | "submitted" | "accepted" | "rejected" | "imported";

export interface FormField {
  key: string;
  label: string;
  display_label: string;
  input_type: string;
  required: boolean;
  unit: string | null;
  placeholder: string | null;
  maximum: number | null;
  choices: string[];
}

export interface FormSection {
  title: string;
  rows: Array<{ field_keys: string[]; label: string | null; separator: string | null }>;
}

export interface OnlineFormDefinition {
  form_code: string;
  form_number: string;
  form_name: string;
  asset_type: string;
  asset_name_field: string;
  fields: FormField[];
  sections: FormSection[];
  evaluation_items: Array<{
    item_code: string;
    category: string;
    item_name: string;
    standards: Record<string, string>;
  }>;
  grade_options: string[];
  evaluation_title: string;
  evaluation_note: string | null;
  conclusion_title: string;
}

export interface OnlineEntry {
  entry_uid: string;
  task_uid: string;
  task_name: string;
  project_uid: string;
  project_name: string;
  survey_batch_uid: string;
  batch_name: string;
  management_scope_uid: string;
  organization_unit_uid: string;
  organization_name: string;
  canal_unit_uid: string;
  canal_name: string;
  form_code: string;
  form_name: string;
  asset_name: string | null;
  form_data: Record<string, unknown>;
  evaluations: Array<Record<string, unknown>>;
  conclusion: Record<string, unknown>;
  status: OnlineEntryStatus;
  revision_no: number;
  review_notes: string | null;
  created_by_username: string;
  submitted_at: string | null;
  reviewed_by_username: string | null;
  reviewed_at: string | null;
  imported_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OnlineEntryPage {
  items: OnlineEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface EntryContent {
  form_data: Record<string, unknown>;
  evaluations: Array<Record<string, unknown>>;
  conclusion: Record<string, unknown>;
}

export async function getOnlineFormDefinitions(): Promise<OnlineFormDefinition[]> {
  return (await api.get<OnlineFormDefinition[]>("/online-entries/form-definitions")).data;
}

export async function listOnlineEntries(params?: { status?: string; mine?: boolean }): Promise<OnlineEntryPage> {
  return (await api.get<OnlineEntryPage>("/online-entries", { params })).data;
}

export async function createOnlineEntry(
  payload: EntryContent & { task_uid: string; management_scope_uid: string; form_code: string },
): Promise<OnlineEntry> {
  return (await api.post<OnlineEntry>("/online-entries", payload)).data;
}

export async function updateOnlineEntry(entryUid: string, payload: EntryContent): Promise<OnlineEntry> {
  return (await api.put<OnlineEntry>(`/online-entries/${entryUid}`, payload)).data;
}

export async function submitOnlineEntry(entryUid: string): Promise<OnlineEntry> {
  return (await api.post<OnlineEntry>(`/online-entries/${entryUid}/submit`)).data;
}

export async function reviewOnlineEntry(
  entryUid: string,
  decision: "accept" | "reject",
  notes: string | null,
): Promise<OnlineEntry> {
  return (await api.post<OnlineEntry>(`/online-entries/${entryUid}/review`, { decision, notes })).data;
}
