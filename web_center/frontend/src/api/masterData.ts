import { api } from "./http";


export interface MasterDataSummary {
  contract_schema_version: string;
  master_data_version: string;
  management_scope_version: string;
  source_description: string;
  contract_sha256: string;
  department_count: number;
  office_count: number;
  canal_count: number;
  management_scope_count: number;
}

export interface Department {
  master_key: string;
  stable_uid: string;
  name: string;
  business_code: string;
  sort_order: number;
  description: string | null;
}

export interface Office extends Department {
  parent_master_key: string;
  parent_name: string;
}

export interface Canal {
  master_key: string;
  stable_uid: string;
  name: string;
  canal_level: string;
  parent_master_key: string | null;
  parent_name: string | null;
  sort_order: number;
  description: string | null;
}

export interface ManagementScope {
  master_key: string;
  stable_uid: string;
  canal_master_key: string;
  canal_name: string;
  organization_master_key: string;
  organization_name: string;
  range_mode: "whole" | "segment_known" | "segment_unknown";
  start_stake_text: string | null;
  start_stake_value: number | null;
  end_stake_text: string | null;
  end_stake_value: number | null;
  sort_order: number;
  status: string;
  description: string | null;
}

export interface MasterDataSnapshot {
  summary: MasterDataSummary;
  departments: Department[];
  offices: Office[];
  canals: Canal[];
  management_scopes: ManagementScope[];
}

export async function getMasterDataSnapshot(): Promise<MasterDataSnapshot> {
  const response = await api.get<MasterDataSnapshot>("/master-data/snapshot");
  return response.data;
}
