import { api } from "./http";

export interface HealthResponse {
  status: string;
  service: string;
}

export interface DatabaseHealthResponse {
  status: string;
  database: string;
  user: string;
  engine: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await api.get<HealthResponse>("/health");
  return response.data;
}

export async function getDatabaseHealth(): Promise<DatabaseHealthResponse> {
  const response = await api.get<DatabaseHealthResponse>("/health/database");
  return response.data;
}
